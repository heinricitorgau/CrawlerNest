"""University admission crawler — real HTML → extract → AdmissionRecord pipeline.

Fetch strategy
--------------
1. Iterate ``candidate_urls`` in order.
2. For each URL, call ``BaseCrawler.fetch_text()``.
3. Map HTTP / network exceptions to a ``CrawlStatus`` value.
4. On success, run ``admission_text_extractor.extract()`` → structured fields.
5. Call ``build_admission_record()`` which attaches the ``ExtractionSummary``.
6. Return ALL attempted records so ``CrawlReport.failure_breakdown`` is accurate.

Snapshot mode
-------------
Pass ``snapshot_dir`` to the constructor.  When a snapshot file matching the
URL's slug exists in that directory, it is used instead of a live HTTP fetch.
This enables offline testing and CI without network access.

Network constraints
-------------------
Uses stdlib ``urllib`` (via ``HttpClient``).  JavaScript-rendered pages will
return a near-empty body that the extractor cannot parse.  Such pages produce
``crawl_status="empty"`` and ``is_usable=False``, which is the correct and
honest result — the pipeline should NOT invent data for JS-gated pages.
"""

from __future__ import annotations

import re
import sys
import urllib.error
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_CRAWLER_DIR = Path(__file__).resolve().parent.parent
_CORE_DIR = _CRAWLER_DIR.parent / "crawlernest-crawler-core"
for _p in (_CRAWLER_DIR, _CORE_DIR):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from base import BaseCrawler
from extractors.admission_requirements import build_admission_record
from http_client import HttpClient
from extractors.admission_text_extractor import extract_with_diagnostics
from models import AdmissionRecord
from site_profiles.default import DEFAULT_ADMISSION_KEYWORDS


# ── Minimum content threshold ─────────────────────────────────────────────────

# A page with fewer visible-text WORDS after stripping HTML is treated as
# empty (JavaScript-rendered shell, redirect target, etc.).
# JS shells typically contain 5-20 words; real content pages contain 50+.
_MIN_VISIBLE_WORDS = 50

_TAG_RE = re.compile(r"<[^>]+>")
# The only values admission_text_extractor._DEGREE_MAP resolves to. It used to
# also accept graduate / phd / masters / bachelor, which the extractor cannot
# produce -- so the wider set never rejected anything, and it disagreed with
# ck_admission_record_degree_level in the warehouse schema.
_VALID_DEGREE_LEVELS = {
    "undergraduate",
    "postgraduate",
    "doctoral",
}


def _visible_text_length(html: str) -> int:
    """Return the approximate length of visible text after stripping HTML tags."""
    return len(_TAG_RE.sub(" ", html).split())


# ── CrawlStatus mapping ───────────────────────────────────────────────────────

def _status_from_http_error(exc: urllib.error.HTTPError) -> str:
    code = exc.code
    if code in (403, 429):
        return "blocked"
    return "error"


def _status_from_url_error(exc: urllib.error.URLError) -> str:
    reason = exc.reason
    # socket.timeout / TimeoutError surfaces as URLError.reason on some platforms
    if isinstance(reason, (TimeoutError, OSError)) and "timed out" in str(reason).lower():
        return "timeout"
    if "tunnel" in str(reason).lower() and "403" in str(reason):
        return "blocked"
    return "error"


# ── URL slug helper ───────────────────────────────────────────────────────────

def _url_to_slug(url: str) -> str:
    """Convert a URL to a safe filename slug (for snapshot lookup)."""
    # Strip scheme and replace non-alphanumeric chars with underscores
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_")
    return slug[:80]  # cap length


# ── Crawler ───────────────────────────────────────────────────────────────────

class UniversityAdmissionCrawler(BaseCrawler):
    """Crawls university admission pages and returns structured AdmissionRecords.

    For each URL attempted, exactly one :class:`AdmissionRecord` is returned
    regardless of success or failure — this ensures the ``CrawlReport``
    reflects the true total of URLs attempted.

    Parameters
    ----------
    snapshot_dir:
        When set, the crawler checks for a ``.html`` file named after the URL
        slug before making any live HTTP request.  Files are named via
        ``_url_to_slug(url) + ".html"``.  Used for offline testing and CI.
    rate_limit_seconds:
        Minimum pause between consecutive HTTP requests (courtesy delay).
        Defaults to 1 second.
    """

    def __init__(
        self,
        *,
        snapshot_dir: Path | str | None = None,
        rate_limit_seconds: float = 1.0,
    ) -> None:
        # rate_limit_seconds used to be accepted and then dropped: this call did
        # not pass an http_client, so BaseCrawler built HttpClient() with the
        # default min_interval_seconds=0.0. Every caller asking for a courtesy
        # delay got none, and the crawler went at eleven university sites as fast
        # as the network allowed. The limiter is per host, so honouring it here
        # does not serialise unrelated sites.
        super().__init__(
            name="crawlernest.admission.university_site",
            http_client=HttpClient(min_interval_seconds=rate_limit_seconds),
            snapshot_dir=snapshot_dir,
        )
        self.rate_limit_seconds = rate_limit_seconds
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    # ── Public entry point ────────────────────────────────────────────────────

    def crawl(
        self,
        *,
        university_name: str,
        base_url: str,
        candidate_urls: list[str] | None = None,
    ) -> list[AdmissionRecord]:
        """Crawl *candidate_urls* and return one :class:`AdmissionRecord` per URL.

        Args:
            university_name: Canonical university name (used in records).
            base_url: Root URL (used as fallback if ``candidate_urls`` is empty).
            candidate_urls: Ordered list of URLs to crawl.  Falls back to a
                minimal candidate list derived from ``base_url``.

        Returns:
            List of :class:`AdmissionRecord`, one per attempted URL.
        """
        urls = candidate_urls or self._default_candidates(base_url)
        return [
            self.crawl_one(university_name=university_name, base_url=base_url, url=url)
            for url in urls
        ]

    def crawl_one(
        self,
        *,
        university_name: str,
        base_url: str,
        url: str,
    ) -> AdmissionRecord:
        """Crawl a single candidate URL, allowlist check included.

        Split out of :meth:`crawl` so callers can schedule URLs themselves --
        specifically so the bridge can run different *hosts* concurrently while
        keeping one host's URLs serial. :meth:`crawl` is now that loop, run
        in order on one thread, and behaves exactly as it did.
        """
        base_host = (urlparse(base_url).hostname or "").lower().strip()
        if base_host and not self._is_allowed_candidate_url(base_host=base_host, url=url):
            self.logger.warning("Skipping non-allowlisted candidate URL %s for base host %s", url, base_host)
            return build_admission_record(
                university_name=university_name,
                source_url=url,
                degree_level="",
                requirements={},
                notes="crawl_status=blocked; skipped non-allowlisted host candidate",
                crawl_status="blocked",
                flagged_fields=["source_host_mismatch"],
            )

        self.logger.info("Crawling %s for %s", url, university_name)
        record = self._crawl_url(university_name=university_name, url=url)
        self.logger.info(
            "  crawl_status=%s is_usable=%s fields=%s",
            record.crawl_status,
            record.extraction_summary.is_usable if record.extraction_summary else "?",
            list(record.requirements.keys()),
        )
        return record

    # ── Per-URL crawl ─────────────────────────────────────────────────────────

    def _crawl_url(
        self,
        *,
        university_name: str,
        url: str,
    ) -> AdmissionRecord:
        """Attempt one URL, map any error to a CrawlStatus, return an AdmissionRecord."""
        html, crawl_status = self._fetch(url)

        if crawl_status == "success" and html:
            fields, extract_diagnostics = self._extract(html)
            normalized_fields, flagged_fields = self._validate_extracted_fields(fields)
            degree_level = normalized_fields.pop("degree_level") or ""
            requirements: dict[str, str] = {
                self._display_field_name(k): str(v)
                for k, v in normalized_fields.items()
                if v is not None
            }
            notes = self._build_notes(
                html,
                fields_found=list(requirements.keys()),
                flagged_fields=flagged_fields,
                extract_diagnostics=extract_diagnostics,
            )
        else:
            degree_level = ""
            requirements = {}
            notes = f"crawl_status={crawl_status}; no extraction attempted"
            flagged_fields = []
            extract_diagnostics = {"raw_truncated": False, "clean_truncated": False}

        return build_admission_record(
            university_name=university_name,
            source_url=url,
            degree_level=degree_level,
            requirements=requirements,
            notes=notes,
            crawl_status=crawl_status,
            flagged_fields=flagged_fields,
            input_truncated=bool(
                extract_diagnostics.get("raw_truncated") or extract_diagnostics.get("clean_truncated")
            ),
        )

    # ── Fetch layer ───────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> tuple[str, str]:
        """Return ``(html_body, crawl_status)``."""
        # 1. Check snapshot first
        if self._snapshot_dir is not None:
            slug = _url_to_slug(url)
            for suffix in (f"{slug}.html", f"{slug}.htm"):
                snap = self._snapshot_dir / suffix
                if snap.exists():
                    self.logger.debug("Snapshot hit: %s", snap)
                    html = snap.read_text(encoding="utf-8", errors="replace")
                    if _visible_text_length(html) < _MIN_VISIBLE_WORDS:
                        return html, "empty"
                    return html, "success"

        # 2. Live HTTP fetch
        try:
            html = self.fetch_text(url)
        except urllib.error.HTTPError as exc:
            self.logger.warning("HTTP %s on %s", exc.code, url)
            return "", _status_from_http_error(exc)
        except urllib.error.URLError as exc:
            self.logger.warning("URLError on %s: %s", url, exc.reason)
            return "", _status_from_url_error(exc)
        except TimeoutError:
            self.logger.warning("Timeout on %s", url)
            return "", "timeout"
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Unexpected error on %s: %s", url, exc)
            return "", "error"

        if not html or _visible_text_length(html) < _MIN_VISIBLE_WORDS:
            self.logger.warning("Empty or near-empty response from %s", url)
            return html, "empty"

        return html, "success"

    # ── Extraction layer ──────────────────────────────────────────────────────

    def _extract(self, html: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run the admission text extractor; catch and log any extraction error."""
        try:
            return extract_with_diagnostics(html)
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Extractor raised unexpectedly: %s", exc)
            return (
                {
                    "ielts": None,
                    "toefl": None,
                    "duolingo": None,
                    "degree_level": None,
                    "deadline": None,
                    "gpa": None,
                },
                {
                    "raw_truncated": False,
                    "clean_truncated": False,
                    "control_chars_removed": 0,
                    "raw_input_chars": len(html),
                    "prepared_chars": 0,
                },
            )

    # ── Notes builder ─────────────────────────────────────────────────────────

    def _build_notes(
        self,
        html: str,
        *,
        fields_found: list[str],
        flagged_fields: list[str],
        extract_diagnostics: dict[str, Any],
    ) -> str:
        """Return a debug note string with a raw text snippet and extraction summary."""
        clean = _TAG_RE.sub(" ", html)
        clean = " ".join(clean.split())
        snippet = clean[:300]
        fields_str = ", ".join(fields_found) if fields_found else "none"
        flag_str = ", ".join(flagged_fields) if flagged_fields else "none"
        truncation = (
            bool(extract_diagnostics.get("raw_truncated"))
            or bool(extract_diagnostics.get("clean_truncated"))
        )
        return (
            f"fields_extracted={fields_str} | flagged_fields={flag_str} | "
            f"input_truncated={str(truncation).lower()} | snippet: {snippet}"
        )

    # ── Fallback URL builder ──────────────────────────────────────────────────

    def _default_candidates(self, base_url: str) -> list[str]:
        """Derive minimal candidate URLs from *base_url* using keyword heuristics."""
        root = base_url.rstrip("/")
        return [
            f"{root}/admissions/english-language-requirements",
            f"{root}/admissions",
            f"{root}/study/international/entry-requirements",
        ]

    def _is_allowed_candidate_url(self, *, base_host: str, url: str) -> bool:
        candidate_host = (urlparse(url).hostname or "").lower().strip()
        if not candidate_host:
            return False
        # Strip leading "www." so that subdomains of the root domain are allowed.
        # Example: base "www.utoronto.ca" → root "utoronto.ca" allows "sgs.utoronto.ca".
        root_host = base_host.removeprefix("www.")
        return (
            candidate_host == base_host
            or candidate_host == root_host
            or candidate_host.endswith(f".{base_host}")
            or candidate_host.endswith(f".{root_host}")
        )

    def _validate_extracted_fields(self, fields: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        sanitized = dict(fields)
        flagged_fields: list[str] = []

        if sanitized.get("ielts") is not None:
            try:
                score = float(sanitized["ielts"])
            except (TypeError, ValueError):
                score = -1
            if not (0.0 <= score <= 9.0):
                flagged_fields.append("invalid_ielts")
                sanitized["ielts"] = None

        if sanitized.get("toefl") is not None:
            try:
                score = int(sanitized["toefl"])
            except (TypeError, ValueError):
                score = -1
            if not (0 <= score <= 120):
                flagged_fields.append("invalid_toefl")
                sanitized["toefl"] = None

        if sanitized.get("duolingo") is not None:
            try:
                score = int(sanitized["duolingo"])
            except (TypeError, ValueError):
                score = -1
            if not (10 <= score <= 160):
                flagged_fields.append("invalid_duolingo")
                sanitized["duolingo"] = None

        if sanitized.get("gpa") is not None:
            try:
                score = float(sanitized["gpa"])
            except (TypeError, ValueError):
                score = -1
            if not (0.0 <= score <= 4.0):
                flagged_fields.append("invalid_gpa")
                sanitized["gpa"] = None

        degree_level = str(sanitized.get("degree_level") or "").strip().lower()
        if degree_level and degree_level not in _VALID_DEGREE_LEVELS:
            flagged_fields.append("invalid_degree_level")
            sanitized["degree_level"] = None

        deadline = sanitized.get("deadline")
        if deadline not in (None, ""):
            try:
                date.fromisoformat(str(deadline))
            except ValueError:
                flagged_fields.append("invalid_deadline")
                sanitized["deadline"] = None

        return sanitized, flagged_fields

    def _display_field_name(self, key: str) -> str:
        mapping = {
            "ielts": "IELTS",
            "toefl": "TOEFL",
            "duolingo": "Duolingo",
            "gpa": "GPA",
            "deadline": "deadline",
        }
        return mapping.get(key, key)
