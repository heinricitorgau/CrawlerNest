#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from ranking_edition import THE_EDITION_PAGE, EditionMismatchError, VerifiedEdition, verify_the_edition_page


BASE_URL = "https://www.timeshighereducation.com"
WORLD_RANKINGS_PAGE = f"{BASE_URL}/world-university-rankings"
LATEST_WORLD_RANKINGS_PAGE = f"{WORLD_RANKINGS_PAGE}/latest/world-ranking"
FALLBACK_HTML_PAGES = [
    LATEST_WORLD_RANKINGS_PAGE,
    f"{BASE_URL}/news/world-university-rankings-2026-results-announced",
    f"{BASE_URL}/node/738362",
    f"{BASE_URL}/press-releases/world-university-rankings-2026-out-now",
]
DEFAULT_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 2.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "crawlernest-kb" / "databases"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}


def _sleep() -> None:
    time.sleep(REQUEST_DELAY_SECONDS)


def _request_text(url: str, session: requests.Session) -> str | None:
    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        _sleep()
        return response.text
    except requests.RequestException as exc:
        print(f"[warn] failed to fetch {url}: {exc}")
        return None


def _request_json(url: str, session: requests.Session) -> Any | None:
    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        _sleep()
        return response.json()
    except requests.RequestException as exc:
        print(f"[warn] failed to fetch {url}: {exc}")
        return None
    except ValueError as exc:
        print(f"[warn] invalid json from {url}: {exc}")
        return None


class _TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._cell_tag: str | None = None
        self._cell_chunks: list[str] = []
        self._current_row: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._in_row = True
            self._current_row = []
            return
        if self._in_row and tag in {"th", "td"}:
            self._cell_tag = tag
            self._cell_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
            self._in_table = False
            self._in_row = False
            self._cell_tag = None
            self._cell_chunks = []
            self._current_row = []
            return
        if not self._in_table:
            return
        if tag in {"th", "td"} and self._cell_tag == tag:
            text = re.sub(r"\s+", " ", "".join(self._cell_chunks)).strip()
            self._current_row.append(text)
            self._cell_tag = None
            self._cell_chunks = []
            return
        if tag == "tr" and self._in_row:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._cell_tag:
            self._cell_chunks.append(data)


def _discover_data_urls(html: str, year: int) -> list[str]:
    candidates: list[str] = []

    direct_pattern = re.compile(
        r"""["'](?P<url>(?:https://www\.timeshighereducation\.com)?/sites/default/files/the_data_rankings/[^"'<>]*?(?:%s|20\d{2})[^"'<>]*?\.json)["']"""
        % year,
        re.IGNORECASE,
    )
    for match in direct_pattern.finditer(html):
        candidates.append(urljoin(BASE_URL, unescape(match.group("url"))))

    generic_pattern = re.compile(
        r"""["'](?P<url>(?:https://www\.timeshighereducation\.com)?/sites/default/files/the_data_rankings/[^"'<>]+?\.json)["']""",
        re.IGNORECASE,
    )
    for match in generic_pattern.finditer(html):
        candidates.append(urljoin(BASE_URL, unescape(match.group("url"))))

    data_url_pattern = re.compile(r"""data[_-]?url["']?\s*[:=]\s*["'](?P<url>[^"']+\.json)["']""", re.IGNORECASE)
    for match in data_url_pattern.finditer(html):
        candidates.append(urljoin(BASE_URL, unescape(match.group("url"))))

    fetch_pattern = re.compile(r"""fetch\(\s*["'](?P<url>[^"']+\.json)["']""", re.IGNORECASE)
    for match in fetch_pattern.finditer(html):
        candidates.append(urljoin(BASE_URL, unescape(match.group("url"))))

    absolute_json_pattern = re.compile(
        r"""https://www\.timeshighereducation\.com/sites/default/files/the_data_rankings/[^"'<> ]+?\.json""",
        re.IGNORECASE,
    )
    for match in absolute_json_pattern.finditer(html):
        candidates.append(unescape(match.group(0)))

    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def _fallback_urls(year: int) -> list[str]:
    return [
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_{year}_0__3557f02116b0bdf81f23e1ef83580d1f.json",
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_{year}_0.json",
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_{year}.json",
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_{year - 1}_0.json",
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_{year - 1}.json",
        f"{BASE_URL}/sites/default/files/the_data_rankings/world_university_rankings_2024_0__3557f02116b0bdf81f23e1ef83580d1f.json",
    ]


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("rows", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        if all(not isinstance(value, (dict, list)) for value in payload.values()):
            return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _extract_rows_from_next_data(html: str) -> list[dict[str, Any]]:
    match = re.search(
        r"""<script id="__NEXT_DATA__" type="application/json">(?P<payload>.*?)</script>""",
        html,
        re.DOTALL,
    )
    if not match:
        return []
    try:
        next_data = json.loads(unescape(match.group("payload")))
    except ValueError as exc:
        print(f"[warn] invalid __NEXT_DATA__ payload: {exc}")
        return []

    try:
        rows = (
            next_data["props"]["pageProps"]["page"]["rankingsTableConfig"]["rankingsData"]["data"]
        )
    except (KeyError, TypeError):
        return []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _pick_first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _make_profile_url(row: dict[str, Any]) -> str | None:
    raw_url = _pick_first(
        row,
        "url",
        "profile_url",
        "profile",
        "profileUrl",
        "institution_url",
        "university_url",
    )
    if raw_url:
        return urljoin(BASE_URL, str(raw_url).strip())

    slug = _pick_first(row, "slug", "path", "institution_slug")
    if slug:
        slug_text = str(slug).strip()
        if slug_text.startswith("http://") or slug_text.startswith("https://"):
            return slug_text
        return urljoin(BASE_URL, slug_text)
    return None


def extract_the_ranking_record(row: dict[str, Any]) -> dict[str, Any]:
    """Map a normalized THE row (see `_normalize_row`) to the documented ingestion shape."""
    name = row.get("name") or row.get("university_name")
    if not name:
        raise ValueError("row must include name or university_name")
    ry = row.get("ranking_year", row.get("year"))
    if ry is None:
        raise ValueError("row must include year or ranking_year")
    rank = row.get("rank")
    if rank is None:
        raise ValueError("row must include rank")
    country = row.get("country")
    return {
        "university_name": str(name).strip(),
        "country": str(country).strip() if country else "",
        "rank": int(rank),
        "score": row.get("score"),
        "source": "THE",
        "ranking_year": int(ry),
    }


def run_the_crawl(year: int = 2026, output_dir: Path | None = None) -> Path:
    """Pipeline alias for QS parity (`run_qs_crawl` / `run_the_crawl`)."""
    return crawl_the_rankings(year=year, output_dir=output_dir)


def _normalize_row(row: dict[str, Any], year: int) -> dict[str, Any] | None:
    name = _pick_first(row, "name", "university_name", "institution", "school")
    if not name:
        return None

    rank = _to_int(_pick_first(row, "rank", "rank_order", "rank_position", "overall_rank", "overall"))
    if rank is None:
        return None

    profile_url = _make_profile_url(row)
    source_id = (
        _pick_first(row, "id", "nid", "source_entity_id")
        or profile_url
        or _pick_first(row, "slug", "path")
        or str(name).strip()
    )
    country = _pick_first(row, "country", "location", "country_name")
    score = _to_float(_pick_first(row, "score", "overall_score", "scores_overall", "scores"))
    if score is None and isinstance(row.get("scores"), dict):
        score = _to_float(
            _pick_first(
                row["scores"],
                "overall",
                "overall_score",
                "total",
            )
        )

    return {
        "id": str(source_id).strip(),
        "name": str(name).strip(),
        "country": str(country).strip() if country else None,
        "year": year,
        "ranking_type": "world",
        "rank": rank,
        "score": score,
        "url": profile_url,
        "metadata": {
            "raw_source": "THE",
            "raw_row": row,
        },
    }


def _extract_rows_from_html_tables(html: str, year: int, page_url: str) -> list[dict[str, Any]]:
    parser = _TableExtractor()
    parser.feed(html)

    normalized_rows: list[dict[str, Any]] = []
    for table in parser.tables:
        if len(table) < 2:
            continue
        header = [cell.strip().lower() for cell in table[0]]
        has_rank = any("rank" in cell for cell in header)
        has_name = any("institution" in cell or "name" in cell or "university" in cell for cell in header)
        has_country = any("country" in cell or "territory" in cell or "region" in cell for cell in header)
        if not (has_rank and has_name and has_country):
            continue

        rank_idx = next((i for i, cell in enumerate(header) if "rank" in cell), None)
        name_idx = next(
            (i for i, cell in enumerate(header) if "institution" in cell or "name" in cell or "university" in cell),
            None,
        )
        country_idx = next(
            (i for i, cell in enumerate(header) if "country" in cell or "territory" in cell or "region" in cell),
            None,
        )
        if rank_idx is None or name_idx is None or country_idx is None:
            continue

        for row in table[1:]:
            if max(rank_idx, name_idx, country_idx) >= len(row):
                continue
            name = row[name_idx].strip()
            if not name:
                continue
            rank = _to_int(row[rank_idx])
            if rank is None:
                continue
            country = row[country_idx].strip() or None
            normalized_rows.append(
                {
                    "id": urljoin(page_url, "#" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")),
                    "name": name,
                    "country": country,
                    "year": year,
                    "ranking_type": "world",
                    "rank": rank,
                    "score": None,
                    "url": page_url,
                    "metadata": {
                        "raw_source": "THE",
                        "extraction_method": "html_table",
                        "source_page": page_url,
                        "raw_row": row,
                    },
                }
            )
        if normalized_rows:
            break

    return normalized_rows


def _load_payload_for_year(year: int, session: requests.Session) -> tuple[Any | None, str | None]:
    """Prefer static JSON blobs, then `__NEXT_DATA__` on the rankings page, then fallbacks."""
    seen: set[str] = set()
    ordered_json: list[str] = []
    for url in _fallback_urls(year):
        if url in seen:
            continue
        seen.add(url)
        ordered_json.append(url)

    for url in ordered_json:
        payload = _request_json(url, session)
        rows = _extract_rows(payload)
        if rows:
            return payload, url

    html = _request_text(WORLD_RANKINGS_PAGE, session)
    extra_json: list[str] = []

    if html:
        next_data_rows = _extract_rows_from_next_data(html)
        if next_data_rows:
            return {"rows": next_data_rows}, WORLD_RANKINGS_PAGE
        for url in _discover_data_urls(html, year):
            if url in seen:
                continue
            seen.add(url)
            extra_json.append(url)

    for url in extra_json:
        payload = _request_json(url, session)
        rows = _extract_rows(payload)
        if rows:
            return payload, url

    html_pages = [WORLD_RANKINGS_PAGE, *FALLBACK_HTML_PAGES]
    seen_pages: set[str] = set()
    for page_url in html_pages:
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        page_html = html if page_url == WORLD_RANKINGS_PAGE and html else _request_text(page_url, session)
        if not page_html:
            continue

        next_data_rows = _extract_rows_from_next_data(page_html)
        if next_data_rows:
            return {"rows": next_data_rows}, page_url

        for url in _discover_data_urls(page_html, year):
            if url in seen:
                continue
            seen.add(url)
            payload = _request_json(url, session)
            rows = _extract_rows(payload)
            if rows:
                return payload, url

        html_rows = _extract_rows_from_html_tables(page_html, year, page_url)
        if html_rows:
            return {"rows": html_rows}, page_url

    return None, None


def _load_verified_edition(year: int, session: requests.Session) -> tuple[list[dict[str, Any]], VerifiedEdition]:
    """The rows of exactly ``year``'s table, from the page whose table config names that year.

    ``_load_payload_for_year`` is not used for ingestion any more: every fallback
    it tries -- last year's data file, a hard-coded 2024 file, the unversioned
    and "latest" pages -- can answer with another edition, and the requested year
    was stamped on whichever did. A 2025 request that got the latest page would
    have ingested 2026 as 2025.
    """
    page_url = THE_EDITION_PAGE.format(year=int(year))
    try:
        response = session.get(page_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        raise EditionMismatchError(f"THE edition page {page_url} failed: {exc}") from exc
    if response.status_code != 200:
        raise EditionMismatchError(f"THE edition page {page_url}: HTTP {response.status_code}")
    # The current edition's /<year>/ page redirects to /latest/; the table config
    # still names its year, which is what is checked.
    edition, rows = verify_the_edition_page(response.text, page_url=str(response.url or page_url), ranking_year=year)
    return rows, edition


def crawl_the_rankings(year: int = 2026, output_dir: Path | None = None) -> Path:
    output_base = output_dir or DEFAULT_OUTPUT_DIR
    output_base.mkdir(parents=True, exist_ok=True)
    output_path = output_base / f"the_rankings_{year}.json"

    print(f"[THE_CRAWL] start year={year} source=THE edition_page={THE_EDITION_PAGE.format(year=year)}")

    session = requests.Session()
    try:
        raw_rows, edition = _load_verified_edition(year, session)
    finally:
        session.close()
    resolved_url = edition.page_url

    normalized_rows: list[dict[str, Any]] = []
    valid_rank_count = 0
    for row in raw_rows:
        normalized = _normalize_row(row, year)
        if normalized is None:
            continue
        normalized_rows.append(normalized)
        valid_rank_count += 1

    output_payload = {
        "rows": normalized_rows,
        "metadata": {
            "source": "THE",
            "ranking_type": "world",
            "ranking_year": year,
            "resolved_data_url": resolved_url,
            "edition": edition.as_meta(),
            "raw_row_count": len(raw_rows),
            "valid_rank_count": valid_rank_count,
        },
    }
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[THE_CRAWL] rows_fetched={len(raw_rows)} year={year} source=THE "
        f"valid_rows={valid_rank_count} resolved={resolved_url!r}"
    )
    print(f"[THE_CRAWL] output={output_path}")
    return output_path


def main() -> int:
    try:
        crawl_the_rankings()
        return 0
    except Exception as exc:
        print(f"[error] THE crawl failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
