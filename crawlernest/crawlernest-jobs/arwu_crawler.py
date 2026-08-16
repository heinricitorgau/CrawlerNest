#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests


BASE_URL = "https://www.shanghairanking.com"
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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


class _CellAwareTableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._cell_tag: str | None = None
        self._cell_chunks: list[str] = []
        self._cell_links: list[str] = []
        self._current_row: list[dict[str, Any]] = []
        self._current_table: list[list[dict[str, Any]]] = []
        self.tables: list[list[list[dict[str, Any]]]] = []

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
            self._cell_links = []
            return
        if self._cell_tag == "td" and tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._cell_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._in_table = False
            self._in_row = False
            self._cell_tag = None
            self._current_row = []
            self._current_table = []
            self._cell_chunks = []
            self._cell_links = []
            return
        if not self._in_table:
            return
        if tag in {"th", "td"} and self._cell_tag == tag:
            texts = []
            for chunk in self._cell_chunks:
                cleaned = re.sub(r"\s+", " ", chunk).strip()
                if cleaned:
                    texts.append(cleaned)
            self._current_row.append(
                {
                    "tag": tag,
                    "text": " ".join(texts),
                    "texts": texts,
                    "links": list(self._cell_links),
                }
            )
            self._cell_tag = None
            self._cell_chunks = []
            self._cell_links = []
            return
        if tag == "tr" and self._in_row:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_row = False

    def handle_data(self, data: str) -> None:
        if self._cell_tag:
            self._cell_chunks.append(data)


def _pick_country_from_texts(texts: list[str], institution_name: str) -> str | None:
    name_norm = institution_name.strip().lower()
    for text in texts:
        candidate = text.strip()
        if not candidate:
            continue
        if candidate.strip().lower() == name_norm:
            continue
        if _to_int(candidate) is not None and re.fullmatch(r"\d+(?:\.\d+)?", candidate):
            continue
        return candidate
    return None


def _extract_rows_from_html_tables(html: str, year: int, page_url: str) -> list[dict[str, Any]]:
    parser = _CellAwareTableExtractor()
    parser.feed(html)
    normalized_rows: list[dict[str, Any]] = []

    for table in parser.tables:
        if len(table) < 2:
            continue
        header_cells = [cell.get("text", "").strip().lower() for cell in table[0]]
        rank_idx = next((i for i, cell in enumerate(header_cells) if "world rank" in cell or cell == "rank"), None)
        institution_idx = next((i for i, cell in enumerate(header_cells) if "institution" in cell or "university" in cell), None)
        score_idx = next((i for i, cell in enumerate(header_cells) if "total score" in cell or cell == "score"), None)
        if rank_idx is None or institution_idx is None:
            continue

        for row in table[1:]:
            if max(rank_idx, institution_idx) >= len(row):
                continue
            rank = _to_int(row[rank_idx].get("text"))
            if rank is None:
                continue

            institution_cell = row[institution_idx]
            texts = [str(t).strip() for t in institution_cell.get("texts", []) if str(t).strip()]
            institution_name = texts[0] if texts else institution_cell.get("text", "").strip()
            if not institution_name:
                continue
            profile_link = None
            links = [str(link).strip() for link in institution_cell.get("links", []) if str(link).strip()]
            if links:
                profile_link = urljoin(BASE_URL, links[0])

            score = None
            if score_idx is not None and score_idx < len(row):
                score = _to_float(row[score_idx].get("text"))
            country = _pick_country_from_texts(texts[1:] if len(texts) > 1 else texts, institution_name)
            source_id = profile_link or f"arwu:{year}:{_slugify(institution_name)}"

            normalized_rows.append(
                {
                    "id": source_id,
                    "name": institution_name,
                    "country": country,
                    "year": year,
                    "ranking_type": "world",
                    "rank": rank,
                    # ARWU bands its tail ("401-500"), and the band is what it
                    # published. Both paths carry it so rows from the rendered
                    # table and rows from the payload have one shape.
                    "rank_display": str(row[rank_idx].get("text", "")).strip() if rank_idx is not None else str(rank),
                    "score": score,
                    "url": profile_link or page_url,
                    "metadata": {
                        "raw_source": "ARWU",
                        "extraction_method": "html_table",
                        "source_page": page_url,
                        "raw_row": [cell.get("text", "") for cell in row],
                    },
                }
            )
        if normalized_rows:
            break

    return normalized_rows


def _candidate_pages(year: int) -> list[str]:
    return [
        f"{BASE_URL}/rankings/arwu/{year}",
        f"{BASE_URL}/rankings/arwu/{year - 1}",
        f"{BASE_URL}/rankings/arwu/{year - 2}",
    ]


def _split_top_level(blob: str) -> list[str]:
    """Split a comma-separated argument list, ignoring commas inside quotes or brackets."""
    out: list[str] = []
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    for ch in blob:
        if quote:
            buf.append(ch)
            if ch == quote and buf[-2:-1] != ["\\"]:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{(":
            depth += 1
            buf.append(ch)
        elif ch in "]})":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf).strip())
    return out


#: Entries appear in two syntaxes. Most are object literals; a couple of dozen
#: are runs of assignments to one object. Both carry the same fields.
_LITERAL_ENTRY = re.compile(
    r"ranking:(\w+),univNameEn:(\w+),univUp:\w+,univLogo:\w+,"
    r"region:(\w+),regionLogo:\w+,regionRanking:\w+,univCode:\w+,score:(\w+)"
)
_ASSIGNED_ENTRY = re.compile(
    r"\.ranking=(\w+);\w+\.univNameEn=(\w+);\w+\.univUp=\w+;\w+\.univLogo=\w+;"
    r"\w+\.region=(\w+);\w+\.regionLogo=\w+;\w+\.regionRanking=\w+;\w+\.univCode=\w+;\w+\.score=(\w+)"
)


def _rows_from_payload(payload_js: str, year: int, page_url: str) -> list[dict[str, Any]]:
    """Read the whole table out of the Nuxt payload.

    The rendered page carries only the first 30 rows; the payload behind it
    carries all ~1,000. It is a JSONP call whose values are all replaced by
    positional parameter names, so reading it means rebuilding the
    parameter-to-argument map and resolving each entry through it.

    Returns an empty list on anything unexpected. The caller falls back to the
    HTML table, which is smaller but has been correct for as long as it existed.
    """
    head = re.match(r'__NUXT_JSONP__\("[^"]*",\s*\(function\(([^)]*)\)\{', payload_js)
    if not head:
        return []
    params = [p.strip() for p in head.group(1).split(",")]

    tail_start = payload_js.rfind("}(")
    if tail_start < 0:
        return []
    args = _split_top_level(payload_js[tail_start + 2:].rstrip().rstrip(");"))
    if len(args) != len(params):
        print(f"[arwu] payload parameter/argument mismatch ({len(params)} vs {len(args)}); "
              "falling back to the rendered table")
        return []

    table: dict[str, Any] = {}
    for name, raw in zip(params, args):
        try:
            table[name] = json.loads(raw)
        except Exception:
            table[name] = raw

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for pattern in (_LITERAL_ENTRY, _ASSIGNED_ENTRY):
        for rank_v, name_v, region_v, score_v in pattern.findall(payload_js):
            name = table.get(name_v)
            if not isinstance(name, str) or not name.strip() or name in seen:
                continue
            seen.add(name)
            rank_text = str(table.get(rank_v, "")).strip()
            rows.append(
                {
                    "id": f"arwu:{year}:{_slugify(name)}",
                    "name": name.strip(),
                    "country": table.get(region_v),
                    "year": year,
                    "ranking_type": "world",
                    "rank": _to_int(rank_text),
                    "rank_display": rank_text,
                    "score": _to_float(str(table.get(score_v, ""))),
                    "url": page_url,
                    "metadata": {
                        "raw_source": "ARWU",
                        "extraction_method": "nuxt_payload",
                        "source_page": page_url,
                    },
                }
            )
    return rows


def _payload_url(html: str, page_url: str) -> str | None:
    """The payload path is stamped with a build id, so it is read, not guessed."""
    match = re.search(r'["\'](/_nuxt/static/[^"\']*?/payload\.js)["\']', html)
    return urljoin(BASE_URL, match.group(1)) if match else None


def _year_of_page(page_url: str, requested: int) -> int:
    """The year the fetched page is actually for.

    The crawler falls back two years, so asking for 2026 and stamping every row
    with 2026 records a year the data is not from. That is how
    arwu_rankings_2026.json came to hold the 2025 table: identical names, ranks
    and scores to arwu_rankings_2025.json, from the same source_page, under a
    year label that made it look like a fresh edition.
    """
    match = re.search(r"/arwu/(\d{4})", page_url)
    return int(match.group(1)) if match else requested


def crawl_arwu_rankings(year: int = 2026, output_dir: Path | None = None) -> Path:
    output_base = output_dir or DEFAULT_OUTPUT_DIR
    output_base.mkdir(parents=True, exist_ok=True)
    output_path = output_base / f"arwu_rankings_{year}.json"

    print(f"[arwu] starting crawl for year={year}")
    session = requests.Session()
    resolved_url = None
    resolved_year = year
    normalized_rows: list[dict[str, Any]] = []
    try:
        for page_url in _candidate_pages(year):
            print(f"[arwu] page={page_url}")
            html = _request_text(page_url, session)
            if not html:
                continue
            # Rows carry the year of the page they came from, not the year that
            # was asked for. Those differ whenever the fallback fires.
            page_year = _year_of_page(page_url, year)
            normalized_rows = _extract_rows_from_html_tables(html, page_year, page_url)

            # The rendered table stops at 30. The payload behind it holds the
            # whole ranking, so prefer it -- but only when it is a superset, so a
            # payload format change degrades to the smaller table instead of
            # silently shrinking the crawl.
            payload_url = _payload_url(html, page_url)
            if payload_url:
                print(f"[arwu] payload={payload_url}")
                payload_js = _request_text(payload_url, session)
                if payload_js:
                    payload_rows = _rows_from_payload(payload_js, page_year, page_url)
                    if len(payload_rows) > len(normalized_rows):
                        rendered = {r["name"] for r in normalized_rows}
                        recovered = {r["name"] for r in payload_rows}
                        missing = rendered - recovered
                        if missing:
                            print(f"[arwu] payload is missing {len(missing)} of the rendered "
                                  f"rows ({sorted(missing)[:3]}...); keeping both")
                            payload_rows.extend(
                                r for r in normalized_rows if r["name"] in missing
                            )
                        print(f"[arwu] payload rows: {len(payload_rows)} "
                              f"(rendered table had {len(normalized_rows)})")
                        normalized_rows = payload_rows

            if normalized_rows:
                resolved_url = page_url
                resolved_year = page_year
                break
    finally:
        session.close()

    if resolved_year != year:
        print(f"[arwu] requested {year} but the table came from {resolved_year}; "
              f"writing it as {resolved_year}")
        output_path = output_base / f"arwu_rankings_{resolved_year}.json"
        for row in normalized_rows:
            row["metadata"]["requested_year"] = year
            row["metadata"]["fell_back_from"] = f"{BASE_URL}/rankings/arwu/{year}"

    if not normalized_rows:
        raise RuntimeError("Unable to locate or parse ARWU rankings table.")

    output_payload = {
        "rows": normalized_rows,
        "metadata": {
            "source": "ARWU",
            "ranking_type": "world",
            "ranking_year": year,
            "resolved_page_url": resolved_url,
            "valid_rank_count": len(normalized_rows),
        },
    }
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[arwu] rows with valid rank: {len(normalized_rows)}")
    print(f"[arwu] output: {output_path}")
    return output_path


def main() -> int:
    try:
        crawl_arwu_rankings()
        return 0
    except Exception as exc:
        print(f"[error] ARWU crawl failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
