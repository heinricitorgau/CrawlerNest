"""Observability layer for the CrawlerNest admission pipeline.

Provides structured types for:
  - Per-URL crawl status   (success / timeout / blocked / empty / error)
  - Per-URL extraction summary   (fields found, missing, confidence flags)
  - Aggregate crawl report   (counts, failure breakdown, per-URL detail)
  - JSON serialisation helpers

This module is intentionally self-contained (stdlib only) so it can be
imported by models.py, extractors, and the engine without circular deps.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

# ── Crawl status ──────────────────────────────────────────────────────────────

CrawlStatus = Literal["success", "timeout", "blocked", "empty", "error"]

# ── Admission field constants ─────────────────────────────────────────────────

# A record that is missing ALL of these is not usable.
LANGUAGE_SCORE_FIELDS: frozenset[str] = frozenset({"IELTS", "TOEFL", "Duolingo"})

# Fields we always want to see in a complete admission record.
REQUIRED_ADMISSION_FIELDS: frozenset[str] = frozenset({"degree_level"}) | LANGUAGE_SCORE_FIELDS

# Fields we track but do not require.
OPTIONAL_ADMISSION_FIELDS: frozenset[str] = frozenset(
    {"GRE", "GMAT", "GPA", "deadline", "program"}
)

# ── Confidence heuristics ─────────────────────────────────────────────────────

_IELTS_RE = re.compile(r"\b([0-9](?:\.[05])?)\b", re.IGNORECASE)
_TOEFL_RE = re.compile(r"\b([5-9][0-9]|1[01][0-9]|120)\b", re.IGNORECASE)
_DEGREE_LEVELS = frozenset(
    {"undergraduate", "postgraduate", "graduate", "doctoral", "phd", "masters", "bachelor"}
)


def _confidence_ielts(value: str) -> bool:
    """Return True if *value* looks like a plausible IELTS score (4.0–9.0)."""
    m = _IELTS_RE.search(value)
    if not m:
        return False
    try:
        score = float(m.group(1))
        return 4.0 <= score <= 9.0
    except ValueError:
        return False


def _confidence_toefl(value: str) -> bool:
    """Return True if *value* looks like a plausible TOEFL score (50–120)."""
    m = _TOEFL_RE.search(value)
    if not m:
        return False
    try:
        score = float(m.group(1))
        return 50 <= score <= 120
    except ValueError:
        return False


def _confidence_degree_level(value: str) -> bool:
    """Return True if *value* is a recognised degree level."""
    return value.strip().lower() in _DEGREE_LEVELS


def _confidence_generic(value: str) -> bool:
    """Generic non-empty check for optional fields."""
    return bool(value.strip())


# ── ExtractionSummary ─────────────────────────────────────────────────────────

@dataclass
class ExtractionSummary:
    """Quality report for a single URL's extraction result.

    Produced alongside every AdmissionRecord so debuggers can see exactly
    which fields were found, which are missing, and how confident we are
    in each extracted value without reading raw HTML.
    """

    url: str
    crawl_status: str  # CrawlStatus
    extracted_fields: list[str]
    extracted_fields_count: int
    missing_required_fields: list[str]
    has_language_score: bool
    confidence_flags: dict[str, bool]   # field_name → plausible?
    is_usable: bool                     # True if record meets minimum quality bar
    flagged_fields: list[str] = field(default_factory=list)
    input_truncated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── CrawlReport ───────────────────────────────────────────────────────────────

@dataclass
class CrawlReport:
    """Aggregate quality report for one university's admission crawl run.

    Shape matches the Phase 1 spec:
      total_urls, success_count, extraction_success_count, failure_breakdown
    Plus full per-URL detail in url_results.
    """

    university_name: str
    base_url: str
    total_urls: int
    success_count: int
    extraction_success_count: int
    failure_breakdown: dict[str, int]   # CrawlStatus value → count
    anomaly_breakdown: dict[str, int] = field(default_factory=dict)
    url_results: list[ExtractionSummary]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict representation."""
        return {
            "university_name": self.university_name,
            "base_url": self.base_url,
            "total_urls": self.total_urls,
            "success_count": self.success_count,
            "extraction_success_count": self.extraction_success_count,
            "failure_breakdown": self.failure_breakdown,
            "anomaly_breakdown": self.anomaly_breakdown,
            "url_results": [r.to_dict() for r in self.url_results],
            "warnings": self.warnings,
        }

    def write_json(self, path: Path | str) -> Path:
        """Serialise and write the report to *path*. Returns the resolved path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return target


# ── Computation helpers ───────────────────────────────────────────────────────

def compute_extraction_summary(
    *,
    url: str,
    crawl_status: str,
    requirements: dict[str, str],
    degree_level: str,
    flagged_fields: list[str] | None = None,
    input_truncated: bool = False,
) -> ExtractionSummary:
    """Derive an :class:`ExtractionSummary` from the raw extraction outputs.

    Args:
        url: The page URL this extraction came from.
        crawl_status: The outcome of the HTTP fetch (see :data:`CrawlStatus`).
        requirements: Free-form key→value map of extracted requirements
            (e.g. ``{"IELTS": "6.5 overall", "TOEFL": "90 iBT"}``).
        degree_level: Degree level string (e.g. ``"postgraduate"``).

    Returns:
        An :class:`ExtractionSummary` with field counts, missing fields,
        and per-field confidence flags.
    """
    # Normalise requirement keys to upper-case for comparison, preserving
    # original keys for output so the caller's names are not mutated.
    key_upper = {k.upper(): k for k in requirements}

    # Build the list of extracted field names (include degree_level if present).
    extracted: list[str] = list(requirements.keys())
    if degree_level:
        extracted.append("degree_level")

    # Required fields that are absent.
    # degree_level is always required; for language scores we require at least one.
    missing: list[str] = []
    if not degree_level:
        missing.append("degree_level")
    lang_present = any(lf.upper() in key_upper for lf in LANGUAGE_SCORE_FIELDS)
    if not lang_present:
        missing.extend(sorted(LANGUAGE_SCORE_FIELDS))

    # Per-field confidence flags.
    confidence_flags: dict[str, bool] = {}
    for raw_key, raw_value in requirements.items():
        ku = raw_key.upper()
        if ku == "IELTS":
            confidence_flags[raw_key] = _confidence_ielts(raw_value)
        elif ku == "TOEFL":
            confidence_flags[raw_key] = _confidence_toefl(raw_value)
        elif ku in ("GRE", "GMAT", "GPA", "DUOLINGO", "DEADLINE"):
            confidence_flags[raw_key] = _confidence_generic(raw_value)
        else:
            # Unknown field — just check it is non-empty.
            confidence_flags[raw_key] = _confidence_generic(raw_value)
    if degree_level:
        confidence_flags["degree_level"] = _confidence_degree_level(degree_level)

    is_usable = (
        crawl_status == "success"
        and lang_present
        and bool(degree_level)
    )

    return ExtractionSummary(
        url=url,
        crawl_status=crawl_status,
        extracted_fields=extracted,
        extracted_fields_count=len(extracted),
        missing_required_fields=missing,
        has_language_score=lang_present,
        confidence_flags=confidence_flags,
        is_usable=is_usable,
        flagged_fields=list(flagged_fields or []),
        input_truncated=input_truncated,
    )


def build_crawl_report(
    *,
    university_name: str,
    base_url: str,
    summaries: list[ExtractionSummary],
    warnings: list[str] | None = None,
) -> CrawlReport:
    """Aggregate a list of per-URL :class:`ExtractionSummary` objects into a
    :class:`CrawlReport`.

    Args:
        university_name: Display name of the crawled university.
        base_url: Root URL that was crawled.
        summaries: One summary per URL attempted (including failures).
        warnings: Optional list of non-fatal warnings accumulated during crawl.

    Returns:
        A fully populated :class:`CrawlReport`.
    """
    total = len(summaries)
    success_count = sum(1 for s in summaries if s.crawl_status == "success")
    extraction_ok = sum(1 for s in summaries if s.is_usable)

    failure_breakdown: dict[str, int] = {}
    anomaly_breakdown: dict[str, int] = {}
    for s in summaries:
        if s.crawl_status != "success":
            failure_breakdown[s.crawl_status] = (
                failure_breakdown.get(s.crawl_status, 0) + 1
            )
        if s.input_truncated:
            anomaly_breakdown["input_truncated"] = (
                anomaly_breakdown.get("input_truncated", 0) + 1
            )
        for field in s.flagged_fields:
            anomaly_breakdown[field] = anomaly_breakdown.get(field, 0) + 1

    return CrawlReport(
        university_name=university_name,
        base_url=base_url,
        total_urls=total,
        success_count=success_count,
        extraction_success_count=extraction_ok,
        failure_breakdown=failure_breakdown,
        anomaly_breakdown=anomaly_breakdown,
        url_results=summaries,
        warnings=list(warnings or []),
    )
