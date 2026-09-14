"""Which published edition a crawl actually read, proven before a row is labelled with it.

``ranking_year`` on every warehouse row means the edition the source printed on
the table: "QS World University Rankings 2026", "THE World University Rankings
2026", "ARWU 2026". Until this module the crawlers never established that. They
fetched whatever the source served and stamped the requested year on it:

* QS resolved its ranking id off the *unversioned* world page. Once QS published
  its 2027 table that page served 2027, so the 2026-09-02 crawl ingested the 2027
  edition as ``ranking_year = 2026``. The subject specs pinned ids that turned out
  to be the 2025 subject tables, under the same 2026 label.
* THE tried last year's data file, a hard-coded 2024 file and the unversioned
  page, and stamped the requested year on whichever answered.
* ARWU fell back two years and wrote those rows under the older year -- honest
  about the label, but not the edition that was asked for.

A mislabelled edition is worse than a missing one. Two crawls of the same table
under two year labels produce a rank delta of zero for every university, which
reads as a verified "unchanged". So each source now proves its edition from the
page that names it, and anything unproven is refused rather than fallen back on:

* QS: ``<ranking page>/<year>``, or the unversioned page, whose ``<title>`` names
  exactly the requested year; the node id comes from that page.
* THE: ``/world-university-rankings/<year>/world-ranking``, whose
  ``rankingsTableConfig.year`` equals the requested year.
* ARWU: ``/rankings/arwu/<year>`` and nothing else.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Any, Callable, Optional
from urllib.parse import urlparse

QS_HOST = "https://www.topuniversities.com"
#: The world ranking's unversioned page lives under /university-rankings/, but
#: its per-edition pages do not: /world-university-rankings/<year>.
_QS_WORLD_UNVERSIONED_PATH = "/university-rankings/world-university-rankings"
_QS_WORLD_EDITION_PATH = "/world-university-rankings"

THE_EDITION_PAGE = "https://www.timeshighereducation.com/world-university-rankings/{year}/world-ranking"
ARWU_EDITION_PAGE = "https://www.shanghairanking.com/rankings/arwu/{year}"

#: A fetch returns (HTTP status, final URL after redirects, body). Injected so
#: the rule is testable offline and the live path can use a Cloudflare-safe stack.
Fetch = Callable[[str], "tuple[Optional[int], str, str]"]


class EditionMismatchError(RuntimeError):
    """The source did not prove it served the edition the crawl was asked for."""


@dataclass(frozen=True)
class VerifiedEdition:
    source: str
    ranking_year: int
    page_url: str
    evidence: str
    ranking_id: str = ""

    def as_meta(self) -> dict[str, Any]:
        return {**asdict(self), "verified": True}


def edition_years_in_title(title: str) -> set[int]:
    return {int(y) for y in re.findall(r"(?<!\d)(20\d{2})(?!\d)", title or "")}


def page_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    return " ".join(unescape(match.group(1)).split()) if match else ""


def qs_page_nids(html: str) -> list[str]:
    """The ranking node ids the page declares as its own (``"nid":"…"``).

    Not every ``nid=`` in the markup: QS pages link other rankings with
    ``?nid=`` query strings, and those are exactly the ids that must not win.
    """
    seen: list[str] = []
    for nid in re.findall(r'"nid"\s*:\s*"?(\d{5,9})', html or ""):
        if nid not in seen:
            seen.append(nid)
    return seen


def qs_edition_page_candidates(ranking_page_url: str, ranking_year: int) -> list[str]:
    """Per-edition page first, then the unversioned page (checked by title like any other).

    Current editions often have no ``/<year>`` page -- QS Europe 2026 404s there
    and lives only at the unversioned URL -- so the unversioned page stays a
    candidate. It is accepted only when its title names the requested year, which
    is precisely what stops it serving 2027 for a 2026 request.
    """
    url = str(ranking_page_url or "").strip().rstrip("/")
    if not url:
        return []
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else QS_HOST
    edition_path = _QS_WORLD_EDITION_PATH if path == _QS_WORLD_UNVERSIONED_PATH else path
    candidates = [f"{base}{edition_path}/{int(ranking_year)}", f"{base}{edition_path}", url]
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def verify_qs_edition_page(html: str, *, page_url: str, ranking_year: int) -> VerifiedEdition:
    title = page_title(html)
    years = edition_years_in_title(title)
    if years != {int(ranking_year)}:
        found = ", ".join(str(y) for y in sorted(years)) or "no year"
        raise EditionMismatchError(
            f"QS page {page_url} is titled {title!r} ({found}), not edition {ranking_year}"
        )
    nids = qs_page_nids(html)
    if len(nids) != 1:
        raise EditionMismatchError(
            f"QS page {page_url} for edition {ranking_year} declares {len(nids)} ranking ids {nids}; "
            "cannot tell which table is the edition"
        )
    return VerifiedEdition("QS", int(ranking_year), page_url, f"title: {title}", ranking_id=nids[0])


def resolve_qs_edition(
    ranking_page_url: Optional[str],
    ranking_year: int,
    fetch: Fetch,
    *,
    pinned_ranking_id: str = "",
) -> VerifiedEdition:
    """The node id of exactly ``ranking_year``'s table, or EditionMismatchError.

    A pinned id is no exemption: it must be the id the edition page declares.
    A spec with no page at all cannot be verified and is refused.
    """
    if not ranking_page_url:
        raise EditionMismatchError(
            f"No ranking page to verify edition {ranking_year} against"
            + (f" (pinned id {pinned_ranking_id} is unverifiable)" if pinned_ranking_id else "")
        )
    reasons: list[str] = []
    for candidate in qs_edition_page_candidates(ranking_page_url, ranking_year):
        status, final_url, html = fetch(candidate)
        if status != 200 or not html:
            reasons.append(f"{candidate}: HTTP {status}")
            continue
        try:
            edition = verify_qs_edition_page(html, page_url=final_url or candidate, ranking_year=ranking_year)
        except EditionMismatchError as exc:
            reasons.append(str(exc))
            continue
        pin = str(pinned_ranking_id or "").strip()
        if pin and pin != edition.ranking_id:
            raise EditionMismatchError(
                f"Pinned ranking id {pin} is not edition {ranking_year}; "
                f"{edition.page_url} declares {edition.ranking_id}"
            )
        return edition
    raise EditionMismatchError(
        f"Could not prove QS edition {ranking_year} for {ranking_page_url}: " + " | ".join(reasons)
    )


def assert_crawled_edition(edition: VerifiedEdition, crawled_ranking_id: str) -> None:
    """The id the crawl actually fetched with is the one the edition page declared."""
    if str(crawled_ranking_id or "").strip() != edition.ranking_id:
        raise EditionMismatchError(
            f"Crawl fetched ranking id {crawled_ranking_id!r}, but edition {edition.ranking_year} "
            f"is {edition.ranking_id} ({edition.page_url})"
        )


def the_next_data(html: str) -> Optional[dict[str, Any]]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(unescape(match.group(1)))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def verify_the_edition_page(html: str, *, page_url: str, ranking_year: int) -> tuple[VerifiedEdition, list[dict[str, Any]]]:
    """The table rows of exactly ``ranking_year``, proven by the page's own table config."""
    data = the_next_data(html)
    try:
        config = data["props"]["pageProps"]["page"]["rankingsTableConfig"]  # type: ignore[index]
        rows = config["rankingsData"]["data"]
        table_year = int(config["year"])
    except (KeyError, TypeError, ValueError):
        raise EditionMismatchError(f"THE page {page_url} carries no rankings table with a year") from None
    if table_year != int(ranking_year):
        raise EditionMismatchError(f"THE page {page_url} holds the {table_year} table, not {ranking_year}")
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    if not rows:
        raise EditionMismatchError(f"THE page {page_url} has an empty {ranking_year} table")
    return VerifiedEdition("THE", table_year, page_url, f"rankingsTableConfig.year={table_year}"), rows


def arwu_year_of_url(url: str) -> Optional[int]:
    match = re.search(r"/arwu/(\d{4})(?:[/?#]|$)", str(url or ""))
    return int(match.group(1)) if match else None


def verify_arwu_page_url(final_url: str, *, ranking_year: int) -> VerifiedEdition:
    year = arwu_year_of_url(final_url)
    if year != int(ranking_year):
        raise EditionMismatchError(
            f"ARWU served {final_url} (edition {year}) for a {ranking_year} request"
        )
    return VerifiedEdition("ARWU", year, final_url, f"page url /arwu/{year}")


def snapshot_edition_ok(run_status: Any, *, ranking_year: int, ranking_id: str = "") -> bool:
    """A saved crawl may be replayed or fallen back on only if it recorded a verified edition."""
    if not isinstance(run_status, dict):
        return False
    meta = run_status.get("crawl_meta") if isinstance(run_status.get("crawl_meta"), dict) else {}
    edition = meta.get("edition") if isinstance(meta, dict) else None
    if not isinstance(edition, dict) or edition.get("verified") is not True:
        return False
    if int(edition.get("ranking_year") or 0) != int(ranking_year):
        return False
    if ranking_id and str(edition.get("ranking_id") or "") != str(ranking_id):
        return False
    return True


def sync_fetch(session: Any, *, timeout: float = 40.0) -> Fetch:
    """Adapt a requests-compatible session (requests or curl_cffi) to Fetch."""

    def _fetch(url: str) -> tuple[Optional[int], str, str]:
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001 - a network failure is an unproven edition
            return None, url, str(exc)
        return int(response.status_code), str(getattr(response, "url", "") or url), response.text or ""

    return _fetch


def qs_fetch_for(config: Any = None) -> Fetch:
    """Fetch through the crawl's own transport choice, without the header set Cloudflare flags."""
    from transport import build_sync_session, resolve_backend

    choice = resolve_backend(config)
    session = build_sync_session(
        choice,
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        extra_headers={},
    )
    return sync_fetch(session)
