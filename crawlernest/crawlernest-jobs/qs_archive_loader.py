#!/usr/bin/env python3
"""Load QS world rankings for past editions from Internet Archive snapshots of QS's own data files.

Why this is a separate module and not a mode of the live crawler. The live crawl
proves its edition from the page it actually read (``ranking_edition``). QS now
answers automated requests with a Cloudflare challenge, so past editions cannot be
crawled. Feeding archived bytes through the live crawler's HTTP layer would make
that proof pass while proving nothing about QS's page, and would put a special case
into the code that runs every day. So this module fetches, verifies and writes on
its own, says what it is in the file it writes (``source_kind: web_archive``), and
meets the rest of the system only at the artifact it produces.

Nothing here decides which snapshot to use. That is a human review recorded in the
manifest (``crawlernest-kb/qs_archive/manifest.json``), together with the sha256 of
the reviewed bytes: if the archive ever serves different bytes for a pinned
snapshot, the load is refused rather than quietly taking the new content.

What a load does, in order, and where it stops:

1. fetch the archived edition page and the archived data file named by the manifest,
   refusing any response that is not exactly the snapshot asked for (Wayback answers a
   missing capture with a redirect to the nearest one);
2. prove the edition with ``ranking_edition.verify_qs_edition_page`` run on the
   *archived* page, then require that the one ranking id the page declares is the id
   of the data file and of the manifest;
3. check the data bytes against the pinned sha256;
4. parse, and run the guards (row count, duplicates, ordering, ...);
5. write ``qs_rankings_<year>.json``.

It writes no database row. Ingest is a later, separate step.

Ranks. The archived files carry the rank QS printed ("85", "=196", "201-210",
"1401+") and no per-row ordinal, unlike the live endpoint. ``rank`` in the artifact is
the lower bound of the printed rank, the convention ARWU and THE already follow, and
``rank_display`` keeps what QS printed. No ordinal is invented from row order. A row
whose printed rank is not a rank ("NA") has ``rank: null`` and is kept in the file so
the count is honest; it is not a ranked row.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import urlparse

_JOBS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _JOBS_DIR.parents[1]
for _p in (str(_JOBS_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ranking_edition import EditionMismatchError, VerifiedEdition, verify_qs_edition_page  # noqa: E402
from crawlernest.core.rank_delta import parse_rank_band  # noqa: E402

LOADER_VERSION = "1"
SOURCE_KIND = "web_archive"

KB_DIR = _JOBS_DIR.parent / "crawlernest-kb"
DEFAULT_MANIFEST = KB_DIR / "qs_archive" / "manifest.json"
DEFAULT_OUT_DIR = KB_DIR / "databases"
DEFAULT_CACHE_DIR = KB_DIR / "qs_archive" / "raw"

#: Fewest rows an edition may have and still be believed. QS editions in the manifest
#: hold 933-1,498 rows; a first page or a truncated payload is far below this.
MIN_ROWS = 800
#: Shares of blank fields above which the payload is not trusted. A name is what a row
#: is; a country is a hint the resolver can do without, and QS's own data leaves it
#: empty for a handful of universities in some editions (17 of 1,299 in 2022), so it
#: gets a wider tolerance and a warning rather than a refusal.
MAX_BLANK_NAME_SHARE = 0.01
MAX_BLANK_COUNTRY_SHARE = 0.05
#: A table is "in rank order" if it has at most this share of rows ranked below the row
#: before them, none by more than this many places. QS's own tables carry the odd
#: adjacent swap inside a tie of equal scores (2019: Liverpool "164" printed after
#: Louvain "165", both 47.9), which is the source's order and is kept as printed. A
#: scrambled table is a different thing and fails.
MAX_INVERSION_SHARE = 0.01
MAX_INVERSION_RANKS = 25

QS_HOSTS = {"www.topuniversities.com", "topuniversities.com"}
_WAYBACK_URL = re.compile(r"^https://web\.archive\.org/web/(\d{14})id_/(https?://.+)$")
_DATA_PATH = re.compile(r"^/sites/default/files/qs-rankings-data/en/(\d{5,9})\.txt$")
_PAGE_PATHS = (
    "/university-rankings/world-university-rankings/{year}",
    "/world-university-rankings/{year}",
)

USER_AGENT = "CrawlerNest-archive-loader/1 (research; reads public Internet Archive captures, 1 request per 2s)"


class ArchiveIntegrityError(RuntimeError):
    """The bytes are not the bytes the manifest pinned, or are not the snapshot asked for."""


class ArchiveGuardError(RuntimeError):
    """The payload verified as the right edition but failed a sanity guard."""


class ArchiveFetchError(RuntimeError):
    """The archive could not be read."""


# --------------------------------------------------------------------------- manifest


@dataclass(frozen=True)
class SnapshotRef:
    snapshot_url: str
    snapshot_ts: str
    original_url: str


@dataclass(frozen=True)
class ManifestEntry:
    ranking_year: int
    edition_page: SnapshotRef
    data_file: SnapshotRef
    expected_ranking_id: str
    expected_sha256: str
    reviewed_by: str
    reviewed_on: str
    notes: str = ""
    #: The year in the edition page's address, when QS has since retitled that page to another year. The label
    #: (``ranking_year``) is the year the pinned capture's title names, and the live crawler's rule proves it;
    #: the address is checked against this. Equal to ``ranking_year`` for every edition QS never retitled.
    page_year: int = 0


def _snapshot_ref(raw: Any, label: str) -> SnapshotRef:
    if not isinstance(raw, dict):
        raise ArchiveIntegrityError(f"{label}: missing")
    url = str(raw.get("snapshot_url") or "")
    ts = str(raw.get("snapshot_ts") or "")
    match = _WAYBACK_URL.match(url)
    if not match:
        raise ArchiveIntegrityError(f"{label}: snapshot_url is not an exact id_ Wayback URL: {url!r}")
    if match.group(1) != ts:
        raise ArchiveIntegrityError(f"{label}: snapshot_ts {ts!r} does not match the timestamp in {url!r}")
    original = match.group(2)
    if urlparse(original).hostname not in QS_HOSTS:
        raise ArchiveIntegrityError(f"{label}: archived URL is not on topuniversities.com: {original!r}")
    return SnapshotRef(snapshot_url=url, snapshot_ts=ts, original_url=original)


def parse_manifest_entry(year: int, raw: Any) -> ManifestEntry:
    if not isinstance(raw, dict):
        raise ArchiveIntegrityError(f"manifest[{year}] is not an object")
    if int(raw.get("ranking_year") or 0) != int(year):
        raise ArchiveIntegrityError(f"manifest[{year}].ranking_year is {raw.get('ranking_year')!r}")
    page = _snapshot_ref(raw.get("edition_page"), f"manifest[{year}].edition_page")
    data = _snapshot_ref(raw.get("data_file"), f"manifest[{year}].data_file")
    data_raw = raw.get("data_file") or {}
    expected_id = str(data_raw.get("expected_ranking_id") or "")
    expected_sha = str(data_raw.get("expected_sha256") or "").lower()
    if not re.fullmatch(r"\d{5,9}", expected_id):
        raise ArchiveIntegrityError(f"manifest[{year}].data_file.expected_ranking_id is {expected_id!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ArchiveIntegrityError(
            f"manifest[{year}].data_file.expected_sha256 is not a sha256; pin it after review "
            "(see --show-hash)"
        )
    page_year = int(raw.get("page_year") or year)
    if page_year != int(year) and not str(raw.get("label_basis") or "").strip():
        # A label that differs from the address is a deliberate decision; the manifest must say whose.
        raise ArchiveIntegrityError(f"manifest[{year}].page_year is {page_year} but no label_basis says why")
    path = urlparse(page.original_url).path.rstrip("/")
    if path not in {p.format(year=page_year) for p in _PAGE_PATHS}:
        raise ArchiveIntegrityError(
            f"manifest[{year}].edition_page archives {path!r}, which is not a QS world ranking page for {page_year}"
        )
    data_match = _DATA_PATH.match(urlparse(data.original_url).path)
    if not data_match:
        raise ArchiveIntegrityError(
            f"manifest[{year}].data_file archives {data.original_url!r}, which is not a qs-rankings-data file"
        )
    if data_match.group(1) != expected_id:
        raise ArchiveIntegrityError(
            f"manifest[{year}]: data file id {data_match.group(1)} differs from expected_ranking_id {expected_id}"
        )
    return ManifestEntry(
        ranking_year=int(year),
        edition_page=page,
        data_file=data,
        expected_ranking_id=expected_id,
        expected_sha256=expected_sha,
        reviewed_by=str(raw.get("reviewed_by") or ""),
        reviewed_on=str(raw.get("reviewed_on") or ""),
        notes=str(raw.get("notes") or ""),
        page_year=page_year if page_year != int(year) else 0,
    )


def load_manifest(path: Path) -> dict[int, ManifestEntry]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {int(year): parse_manifest_entry(int(year), entry) for year, entry in raw.items() if not str(year).startswith("_")}


# --------------------------------------------------------------------------- fetch

#: (HTTP status or None, final URL after redirects, body)
FetchBytes = Callable[[str], "tuple[Optional[int], str, bytes]"]


def wayback_fetch(
    *,
    attempts: int = 4,
    backoff: float = 20.0,
    min_interval: float = 2.0,
    timeout: float = 150.0,
    sleep: Callable[[float], None] = time.sleep,
    session: Any = None,
) -> FetchBytes:
    """A polite Wayback reader: one request at a time, spaced, retried through outages.

    The Internet Archive answers "Temporarily Offline" with a 200 and an HTML page, so a
    status code alone does not say the read worked.
    """
    import requests

    sess = session or requests.Session()
    last = {"at": 0.0}

    def _fetch(url: str) -> tuple[Optional[int], str, bytes]:
        status: Optional[int] = None
        final = url
        body = b""
        for attempt in range(attempts):
            wait = min_interval - (time.monotonic() - last["at"])
            if wait > 0:
                sleep(wait)
            try:
                resp = sess.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
                status, final, body = int(resp.status_code), str(resp.url), resp.content
            except Exception as exc:  # noqa: BLE001 - a network failure is a retry, then a fetch error
                status, final, body = None, url, str(exc).encode()
            last["at"] = time.monotonic()
            offline = b"Temporarily Offline" in body[:4000]
            if status is not None and status < 500 and status != 429 and not offline:
                return status, final, body
            if attempt + 1 < attempts:
                sleep(backoff * (attempt + 1))
        return status, final, body

    return _fetch


def decode_payload(body: bytes) -> bytes:
    """Wayback serves these files gzip-compressed; accept either form."""
    if body[:2] == b"\x1f\x8b":
        return gzip.decompress(body)
    return body


def _ts_of(url: str) -> Optional[str]:
    match = _WAYBACK_URL.match(url)
    if match:
        return match.group(1)
    match = re.match(r"^https://web\.archive\.org/web/(\d{14})", url)
    return match.group(1) if match else None


def fetch_snapshot(ref: SnapshotRef, fetch: FetchBytes) -> bytes:
    """The decoded bytes of exactly this snapshot, or an error. Never a nearby capture."""
    status, final_url, body = fetch(ref.snapshot_url)
    if status != 200:
        raise ArchiveFetchError(f"{ref.snapshot_url}: HTTP {status}")
    got = _ts_of(final_url)
    if got != ref.snapshot_ts:
        raise ArchiveIntegrityError(
            f"{ref.snapshot_url} was served as capture {got!r}, not {ref.snapshot_ts!r}; "
            "the archive redirected to a different snapshot"
        )
    if b"Temporarily Offline" in body[:4000]:
        raise ArchiveFetchError(f"{ref.snapshot_url}: the Internet Archive reported itself offline")
    return decode_payload(body)


@dataclass(frozen=True)
class Acquired:
    page_html: str
    data_bytes: bytes


def _cache_path(cache_dir: Optional[Path], year: int, ref: SnapshotRef, kind: str) -> Optional[Path]:
    if cache_dir is None:
        return None
    digest = hashlib.sha1(ref.snapshot_url.encode()).hexdigest()[:10]
    return Path(cache_dir) / str(year) / f"{kind}_{ref.snapshot_ts}_{digest}"


def _read_through(cache_dir: Optional[Path], year: int, ref: SnapshotRef, kind: str, fetch: FetchBytes) -> bytes:
    path = _cache_path(cache_dir, year, ref, kind)
    if path is not None and path.exists():
        return path.read_bytes()
    body = fetch_snapshot(ref, fetch)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    return body


def acquire(entry: ManifestEntry, fetch: FetchBytes, cache_dir: Optional[Path] = None) -> Acquired:
    page = _read_through(cache_dir, entry.ranking_year, entry.edition_page, "page", fetch)
    data = _read_through(cache_dir, entry.ranking_year, entry.data_file, "data", fetch)
    return Acquired(page_html=page.decode("utf-8", "replace"), data_bytes=data)


# --------------------------------------------------------------------------- verify


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_entry(entry: ManifestEntry, acquired: Acquired) -> VerifiedEdition:
    """Prove the edition from the archived page, and tie the data bytes to that proof.

    ``verify_qs_edition_page`` is the live crawler's own rule, run here on the archived
    page: the title names exactly the requested year and the page declares exactly one
    ranking id. On top of it the data file's id and the manifest must name that same id,
    and the bytes must be the ones that were reviewed.
    """
    edition = verify_qs_edition_page(
        acquired.page_html,
        page_url=entry.edition_page.snapshot_url,
        ranking_year=entry.ranking_year,
    )
    if edition.ranking_id != entry.expected_ranking_id:
        raise EditionMismatchError(
            f"archived page for {entry.ranking_year} declares ranking id {edition.ranking_id}, "
            f"but the manifest pins {entry.expected_ranking_id}"
        )
    data_match = _DATA_PATH.match(urlparse(entry.data_file.original_url).path)
    if not data_match or data_match.group(1) != edition.ranking_id:
        raise EditionMismatchError(
            f"data file {entry.data_file.original_url} is not the table of ranking id {edition.ranking_id}"
        )
    actual = sha256_hex(acquired.data_bytes)
    if actual != entry.expected_sha256:
        raise ArchiveIntegrityError(
            f"{entry.data_file.snapshot_url}: sha256 is {actual}, the manifest pinned {entry.expected_sha256}. "
            "The bytes changed since they were reviewed."
        )
    return edition


# --------------------------------------------------------------------------- parse


class _TitleCell(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.href: Optional[str] = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "a" and self.href is None:
            for key, value in attrs:
                if key == "href" and value:
                    self.href = value

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(unescape("".join(self._parts)).replace("\xa0", " ").split())


def parse_title_cell(value: Any) -> tuple[str, str]:
    """(name, profile path) from QS's ``title`` cell, which is a fragment of HTML."""
    parser = _TitleCell()
    parser.feed(str(value or ""))
    parser.close()
    href = (parser.href or "").strip()
    if href.startswith("http"):
        href = urlparse(href).path
    return parser.text, href


@dataclass(frozen=True)
class ArchiveRow:
    nid: str
    name: str
    country: str
    city: str
    region: str
    profile_path: str
    score: Optional[float]
    rank_display: str
    rank_position: Optional[int]
    rank_kind: str  # exact | tied | banded | open_ended | unranked
    raw: dict = field(compare=False, default_factory=dict)


def classify_rank(display: str) -> tuple[Optional[int], str]:
    """(lower bound, kind) of a printed rank. No ordinal is ever made up."""
    text = str(display or "").strip()
    band = parse_rank_band(text)
    if band is None:
        return None, "unranked"
    if band.upper is None:
        return band.lower, "open_ended"
    if band.is_exact:
        return band.lower, "tied" if text.lstrip().startswith("=") else "exact"
    return band.lower, "banded"


def _float_or_none(value: Any) -> Optional[float]:
    try:
        text = str(value).strip().replace(",", "")
        return float(text) if text else None
    except ValueError:
        return None


def parse_rows(data_bytes: bytes) -> list[ArchiveRow]:
    payload = json.loads(data_bytes)
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ArchiveGuardError("data file has no list of rows under 'data'")
    rows: list[ArchiveRow] = []
    for item in items:
        if not isinstance(item, dict):
            raise ArchiveGuardError(f"a row is not an object: {str(item)[:80]!r}")
        name, path = parse_title_cell(item.get("title"))
        display = str(item.get("rank_display") or "").strip()
        position, kind = classify_rank(display)
        rows.append(
            ArchiveRow(
                nid=str(item.get("nid") or "").strip(),
                name=name,
                country=str(item.get("country") or "").strip(),
                city=str(item.get("city") or "").strip(),
                region=str(item.get("region") or "").strip(),
                profile_path=path,
                score=_float_or_none(item.get("score")),
                rank_display=display,
                rank_position=position,
                rank_kind=kind,
                raw=item,
            )
        )
    return rows


# --------------------------------------------------------------------------- guards


@dataclass
class GuardReport:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def check_guards(
    rows: Sequence[ArchiveRow],
    *,
    neighbor: Optional[tuple[int, list[str], int]] = None,
    year: int = 0,
) -> GuardReport:
    """Sanity checks that a right-edition payload is also a whole, well-formed one.

    ``neighbor`` is (year, top-50 names, row count) of the nearest already-written
    edition; it only ever produces warnings, because a real change of order looks the
    same as a wrong table until a person has looked.
    """
    report = GuardReport()
    if len(rows) < MIN_ROWS:
        report.failures.append(f"{len(rows)} rows is below the minimum of {MIN_ROWS}; the payload looks truncated")
    nids = [r.nid for r in rows if r.nid]
    if len(nids) != len(set(nids)):
        report.failures.append(f"{len(nids) - len(set(nids))} duplicate nid values")
    if len(nids) < len(rows):
        report.failures.append(f"{len(rows) - len(nids)} rows have no nid")
    paths = [r.profile_path for r in rows if r.profile_path]
    if len(paths) != len(set(paths)):
        report.failures.append(f"{len(paths) - len(set(paths))} duplicate profile paths; ids would collide")
    if rows:
        no_name = sum(1 for r in rows if not r.name)
        if no_name / len(rows) > MAX_BLANK_NAME_SHARE:
            report.failures.append(f"{no_name} of {len(rows)} rows have no name")
        no_country = sum(1 for r in rows if not r.country)
        if no_country / len(rows) > MAX_BLANK_COUNTRY_SHARE:
            report.failures.append(f"{no_country} of {len(rows)} rows have no country")
        elif no_country:
            report.warnings.append(f"{no_country} of {len(rows)} rows have no country in the source; left blank")
        first = rows[0]
        if not (first.rank_display == "1" and first.rank_kind == "exact"):
            report.failures.append(f"first row is rank {first.rank_display!r}, not an exact 1")
    last = 0
    inversions: list[tuple[int, ArchiveRow, int]] = []
    for index, row in enumerate(rows):
        if row.rank_position is None:
            continue
        if row.rank_position < last:
            inversions.append((index, row, last - row.rank_position))
        else:
            last = row.rank_position
    ranked = sum(1 for r in rows if r.rank_position is not None)
    if inversions:
        worst = max(size for _, _, size in inversions)
        described = "; ".join(f"row {i} {r.name!r} printed {r.rank_display!r} after {r.rank_position + size}" for i, r, size in inversions[:5])
        if worst > MAX_INVERSION_RANKS or len(inversions) / max(ranked, 1) > MAX_INVERSION_SHARE:
            report.failures.append(
                f"{len(inversions)} rows are out of rank order (worst by {worst} places): {described}; "
                "the table is not in rank order"
            )
        else:
            report.warnings.append(
                f"{len(inversions)} row(s) printed out of rank order by at most {worst} place(s), kept as the source printed them: {described}"
            )
    if not any(r.rank_position is not None for r in rows):
        report.failures.append("no row has a rank")
    if neighbor is not None and rows:
        n_year, n_top, n_count = neighbor
        top = [r.name for r in rows[:50]]
        overlap = len(set(top) & set(n_top))
        if overlap < 35:
            report.warnings.append(
                f"top 50 shares {overlap} names with the {n_year} edition; a table this different needs a person's look"
            )
        if n_count and abs(len(rows) - n_count) / n_count > 0.25:
            report.warnings.append(f"{len(rows)} rows against {n_count} in {n_year}: more than 25% apart")
    return report


# --------------------------------------------------------------------------- artifact


def build_artifact(
    entry: ManifestEntry,
    edition: VerifiedEdition,
    rows: Sequence[ArchiveRow],
    *,
    payload_sha256: str,
    guard: GuardReport,
) -> dict[str, Any]:
    counts = {"exact": 0, "tied": 0, "banded": 0, "open_ended": 0, "unranked": 0}
    for row in rows:
        counts[row.rank_kind] += 1
    out_rows = []
    for row in rows:
        entity_id = row.profile_path or f"qs-nid:{row.nid}"
        out_rows.append(
            {
                "id": entity_id,
                "name": row.name,
                "country": row.country,
                "year": entry.ranking_year,
                "ranking_type": "world",
                "rank": row.rank_position,
                "rank_display": row.rank_display,
                "score": row.score,
                "url": f"https://www.topuniversities.com{row.profile_path}" if row.profile_path else None,
                "metadata": {
                    "raw_source": "QS",
                    "extraction_method": "archived_qs_rankings_data",
                    "id_basis": "qs_profile_path" if row.profile_path else "nid",
                    "source_page": entry.data_file.snapshot_url,
                    "nid": row.nid,
                    "rank_kind": row.rank_kind,
                    "raw_row": row.raw,
                },
            }
        )
    return {
        "metadata": {
            "source": "QS",
            "ranking_type": "world",
            "ranking_year": entry.ranking_year,
            "source_kind": SOURCE_KIND,
            "loader_version": LOADER_VERSION,
            "archive_snapshot_url": entry.data_file.snapshot_url,
            "original_url": entry.data_file.original_url,
            "snapshot_timestamp": entry.data_file.snapshot_ts,
            "payload_sha256": payload_sha256,
            "edition": {
                **edition.as_meta(),
                "page_snapshot_timestamp": entry.edition_page.snapshot_ts,
                **({"page_address_year": entry.page_year} if entry.page_year else {}),
            },
            "reviewed_by": entry.reviewed_by,
            "reviewed_on": entry.reviewed_on,
            "review_notes": entry.notes,
            "row_count": len(rows),
            "valid_rank_count": len(rows) - counts["unranked"],
            "rank_counts": counts,
            "rank_convention": "rank is the lower bound of the rank QS printed; rank_display is what QS printed",
            "guard_warnings": list(guard.warnings),
        },
        "rows": out_rows,
    }


def artifact_path(out_dir: Path, year: int) -> Path:
    return Path(out_dir) / f"qs_rankings_{year}.json"


def render_artifact(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, ensure_ascii=False, indent=2) + "\n"


def write_artifact(artifact: dict[str, Any], out_dir: Path) -> Path:
    """Write the file, refusing to replace anything this loader did not write."""
    year = int(artifact["metadata"]["ranking_year"])
    path = artifact_path(out_dir, year)
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            kind = (existing.get("metadata") or {}).get("source_kind")
        except Exception:  # noqa: BLE001 - unreadable is as foreign as anything else
            kind = None
        if kind != SOURCE_KIND:
            raise ArchiveIntegrityError(f"{path} exists and was not written by this loader; refusing to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(render_artifact(artifact), encoding="utf-8")
    tmp.replace(path)
    return path


def nearest_neighbor(out_dir: Path, year: int) -> Optional[tuple[int, list[str], int]]:
    for gap in (1, 2):
        for candidate in (year - gap, year + gap):
            path = artifact_path(out_dir, candidate)
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if (data.get("metadata") or {}).get("source_kind") != SOURCE_KIND:
                    continue
                rows = data["rows"]
                return candidate, [str(r["name"]) for r in rows[:50]], len(rows)
            except Exception:  # noqa: BLE001
                continue
    return None


# --------------------------------------------------------------------------- driver


@dataclass
class YearResult:
    year: int
    status: str  # written | refused | error
    detail: str = ""
    rows: int = 0
    ranked: int = 0
    path: Optional[Path] = None
    warnings: list[str] = field(default_factory=list)


def load_year(
    entry: ManifestEntry,
    fetch: FetchBytes,
    *,
    out_dir: Path,
    cache_dir: Optional[Path] = None,
) -> YearResult:
    try:
        acquired = acquire(entry, fetch, cache_dir)
        edition = verify_entry(entry, acquired)
        rows = parse_rows(acquired.data_bytes)
        guard = check_guards(rows, neighbor=nearest_neighbor(out_dir, entry.ranking_year), year=entry.ranking_year)
        if not guard.ok:
            raise ArchiveGuardError("; ".join(guard.failures))
        artifact = build_artifact(
            entry, edition, rows, payload_sha256=sha256_hex(acquired.data_bytes), guard=guard
        )
        path = write_artifact(artifact, out_dir)
    except (EditionMismatchError, ArchiveIntegrityError, ArchiveGuardError) as exc:
        return YearResult(entry.ranking_year, "refused", f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported per year so one outage does not hide the others
        return YearResult(entry.ranking_year, "error", f"{type(exc).__name__}: {exc}")
    meta = artifact["metadata"]
    return YearResult(
        entry.ranking_year, "written", rows=meta["row_count"], ranked=meta["valid_rank_count"],
        path=path, warnings=list(guard.warnings),
    )


def show_hash(entry: ManifestEntry, fetch: FetchBytes, cache_dir: Optional[Path]) -> str:
    data = _read_through(cache_dir, entry.ranking_year, entry.data_file, "data", fetch)
    rows = parse_rows(data)
    return f"{entry.ranking_year} {entry.data_file.snapshot_ts} sha256={sha256_hex(data)} bytes={len(data)} rows={len(rows)}"


# --------------------------------------------------------------------------- ingest

BACKUP_DIR = _REPO_ROOT / ".local" / "backups"
RECEIPT_DIR = KB_DIR / "qs_archive" / "receipts"
ARCHIVE_VERSION_PREFIX = "web_archive:"


class IngestRefused(RuntimeError):
    """The ingest was stopped before it wrote anything."""


@dataclass(frozen=True)
class PgConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "clawer"
    user: str = "test"
    password: str = "test"


@dataclass(frozen=True)
class QsYearState:
    """What the warehouse already holds for QS in one edition."""

    ranking_records: int
    archive_records: int
    aggregated_with_qs: int


def existing_qs_state(conn: Any, year: int) -> QsYearState:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*),
                   count(*) FILTER (WHERE rr.source_version LIKE %s)
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
            WHERE rs.source_code = 'QS' AND rr.ranking_year = %s AND rr.ranking_type = 'world'
            """,
            (ARCHIVE_VERSION_PREFIX + "%", year),
        )
        records, archive = cur.fetchone()
        cur.execute(
            """
            SELECT count(*) FROM analytics.aggregated_rankings
            WHERE ranking_year = %s AND source_ranks_json->>'QS' IS NOT NULL
            """,
            (year,),
        )
        (aggregated,) = cur.fetchone()
    return QsYearState(int(records), int(archive), int(aggregated))


def check_ingest_allowed(state: QsYearState, *, year: int, replace: bool) -> None:
    """The guard the pipeline's own shrink guard cannot be: it only looks at editions already held."""
    if state.ranking_records == 0 and state.aggregated_with_qs == 0:
        return
    if not replace:
        raise IngestRefused(
            f"QS {year} is not empty (ranking_record {state.ranking_records}, aggregated rows with a QS rank "
            f"{state.aggregated_with_qs}); the loader fills empty editions only. --replace is for re-loading an "
            "earlier archive load"
        )
    if state.ranking_records != state.archive_records:
        raise IngestRefused(
            f"--replace would overwrite {state.ranking_records - state.archive_records} QS {year} rows that did "
            "not come from this loader; refusing"
        )


def make_backup(
    pg: PgConfig,
    year: int,
    backup_dir: Path,
    *,
    run: Callable[..., Any] = None,  # type: ignore[assignment]
    now: Optional[str] = None,
) -> Path:
    """A custom-format dump, checked by listing it, before anything is written."""
    import os
    import subprocess

    runner = run or subprocess.run
    stamp = now or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = Path(backup_dir) / f"qs_archive_pre_ingest_{year}_{pg.database}_{stamp}.dump"
    path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PGPASSWORD": pg.password}
    runner(
        ["pg_dump", "-Fc", "-h", pg.host, "-p", str(pg.port), "-U", pg.user, "-f", str(path), pg.database],
        check=True, env=env, capture_output=True,
    )
    listing = runner(["pg_restore", "-l", str(path)], check=True, env=env, capture_output=True)
    if not path.exists() or path.stat().st_size == 0 or not getattr(listing, "stdout", b"").strip():
        raise IngestRefused(f"backup {path} is empty or unreadable; refusing to ingest")
    return path


def archive_universities(rows: Sequence[ArchiveRow]) -> tuple[list[Any], int]:
    """University objects for the rows that have a rank, and the count that do not.

    A row QS printed no rank for stays in the artifact so the count is honest, but a
    rank-less row has nothing to contribute to a ranking and is not ingested.
    """
    from models import University  # crawlernest-core; on the path once run_pipeline is imported

    out = []
    skipped = 0
    for row in rows:
        if row.rank_position is None:
            skipped += 1
            continue
        profile = row.profile_path
        metrics = {"Overall Score": str(row.raw.get("score") or "").strip()} if row.score is not None else {}
        out.append(
            University(
                rank=str(row.rank_position),
                name=row.name,
                country=row.country,
                city_name=row.city,
                qs_profile_path=profile,
                path=profile,
                table_metrics=metrics,
                rank_display=row.rank_display,
            )
        )
    return out, skipped


@dataclass
class IngestResult:
    year: int
    run_id: str
    backup: Path
    receipt: Path
    ingested: int
    unranked_skipped: int
    matched: int
    unresolved: int
    rows_written: int
    aggregated_rows: int
    years_aggregated: list[int]


def ingest_year(
    entry: ManifestEntry,
    fetch: FetchBytes,
    *,
    out_dir: Path,
    cache_dir: Optional[Path],
    pg: PgConfig,
    replace: bool = False,
    backup_dir: Path = BACKUP_DIR,
    receipt_dir: Path = RECEIPT_DIR,
    run_pipeline_module: Any = None,
    backup: Callable[..., Path] = make_backup,
    withhold: Sequence[str] = (),
) -> IngestResult:
    """Fill one empty QS edition from the pinned archive load. Nothing is written until every check passes."""
    year = entry.ranking_year
    acquired = acquire(entry, fetch, cache_dir)
    edition = verify_entry(entry, acquired)
    rows = parse_rows(acquired.data_bytes)
    guard = check_guards(rows, neighbor=nearest_neighbor(out_dir, year), year=year)
    if not guard.ok:
        raise ArchiveGuardError("; ".join(guard.failures))
    artifact = build_artifact(entry, edition, rows, payload_sha256=sha256_hex(acquired.data_bytes), guard=guard)
    rendered = render_artifact(artifact)

    # The file in the repository is what gets ingested, byte for byte.
    on_disk = artifact_path(out_dir, year)
    if not on_disk.exists() or on_disk.read_text(encoding="utf-8") != rendered:
        raise IngestRefused(
            f"{on_disk} is missing or differs from what the manifest produces; load the year again and "
            "commit the file before ingesting it"
        )

    rp = run_pipeline_module
    if rp is None:
        from crawlernest import run_pipeline as rp  # noqa: PLC0415 - heavy, and only an ingest needs it

    universities, skipped = archive_universities(rows)
    normalized = rp.normalize_universities(universities)
    version = f"{ARCHIVE_VERSION_PREFIX}{entry.data_file.snapshot_ts}"
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_id = f"qs-archive-{year}-{started}"

    conn = rp._connect_postgres(pg.host, pg.port, pg.database, pg.user, pg.password)
    try:
        state = existing_qs_state(conn, year)
        check_ingest_allowed(state, year=year, replace=replace)
        backup_path = backup(pg, year, backup_dir)
        pipeline = rp._build_multi_source_pipeline(conn)
        standardized = rp.QSAdapter(
            ranking_year=year,
            ranking_type="world",
            source_version=version,
            universe_type="global",
            universe_key="global",
        ).adapt(normalized)
        provenance = {
            "source_kind": SOURCE_KIND,
            "archive_snapshot_url": entry.data_file.snapshot_url,
            "snapshot_timestamp": entry.data_file.snapshot_ts,
            "payload_sha256": sha256_hex(acquired.data_bytes),
            "edition_page_snapshot_url": entry.edition_page.snapshot_url,
            "loader_version": LOADER_VERSION,
            "rank_convention": artifact["metadata"]["rank_convention"],
        }
        for record in standardized:
            record.metadata["provenance"] = dict(provenance)
        # Rows an operator chose to hold back, named on the command line and recorded in
        # the receipt. The pipeline refuses a batch that would let the resolver re-decide
        # a standing human review (a source id that changed spelling between editions);
        # re-keying that decision is a person's work, so the loader never does it.
        held = set(withhold)
        withheld = [r.source_entity_id for r in standardized if r.source_entity_id in held]
        unknown = held - set(withheld)
        if unknown:
            raise IngestRefused(f"--withhold-id names ids that are not in this edition: {sorted(unknown)}")
        standardized = [r for r in standardized if r.source_entity_id not in held]
        summary = pipeline.ingest_records(
            standardized,
            batch_id=run_id,
            run_label_prefix="qs_archive",
            ranking_type="world",
            enable_aggregation=True,
        )
    finally:
        conn.close()

    receipt = {
        "year": year,
        "run_id": run_id,
        "started_utc": started,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database": pg.database,
        "manifest": {
            "data_snapshot_url": entry.data_file.snapshot_url,
            "payload_sha256": sha256_hex(acquired.data_bytes),
            "expected_ranking_id": entry.expected_ranking_id,
            "reviewed_by": entry.reviewed_by,
        },
        "artifact_sha256": sha256_hex(rendered.encode("utf-8")),
        "before": {
            "ranking_records": state.ranking_records,
            "aggregated_with_qs": state.aggregated_with_qs,
        },
        "ingested": len(standardized),
        "unranked_skipped": skipped,
        "withheld_by_operator": withheld,
        "summary": {
            "standardized": summary.standardized_count,
            "matched": summary.matched_count,
            "unresolved": summary.unresolved_count,
            "duplicates": summary.duplicate_input_count,
            "rows_written": summary.rows_written,
            "years_aggregated": list(summary.years_aggregated),
            "aggregated_rows": summary.aggregated_row_count,
        },
        "backup": {"path": str(backup_path), "bytes": Path(backup_path).stat().st_size},
        "rollback": {
            "full": (
                f"pg_restore -h {pg.host} -p {pg.port} -U {pg.user} -d {pg.database} --clean --if-exists "
                f"{backup_path}"
            ),
            "note": "restores the whole database to its state before this ingest; anything written since is lost",
        },
    }
    receipt_path = Path(receipt_dir) / f"{year}_{run_id}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return IngestResult(
        year=year, run_id=run_id, backup=Path(backup_path), receipt=receipt_path, ingested=len(standardized),
        unranked_skipped=skipped, matched=summary.matched_count, unresolved=summary.unresolved_count,
        rows_written=summary.rows_written, aggregated_rows=summary.aggregated_row_count,
        years_aggregated=list(summary.years_aggregated),
    )


def _offline_fetch(url: str) -> tuple[Optional[int], str, bytes]:
    raise ArchiveFetchError(f"--offline: {url} is not in the cache")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load QS editions from reviewed Internet Archive snapshots.")
    parser.add_argument("--year", type=int, action="append", help="edition to load (repeatable)")
    parser.add_argument("--all", action="store_true", help="every edition in the manifest")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--offline", action="store_true", help="read only from the cache; no network")
    parser.add_argument("--show-hash", action="store_true", help="print the sha256 to pin after review; write nothing")
    parser.add_argument("--request-delay", type=float, default=2.0)
    parser.add_argument("--ingest", action="store_true", help="after loading, fill the empty QS edition in PostgreSQL")
    parser.add_argument("--replace", action="store_true", help="with --ingest: re-load an earlier archive load")
    parser.add_argument("--withhold-id", action="append", default=[], metavar="SOURCE_ID",
                        help="with --ingest: leave this QS source id out (repeatable); recorded in the receipt")
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=RECEIPT_DIR)
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)
    if args.ingest and (args.all or not args.year):
        parser.error("--ingest needs explicit --year values; it never runs for every edition at once")

    if not args.year and not args.all:
        parser.error("name --year or --all")
    manifest = load_manifest(args.manifest) if not args.show_hash else _load_manifest_unpinned(args.manifest)
    years = sorted(manifest) if args.all else sorted(set(args.year))
    missing = [y for y in years if y not in manifest]
    if missing:
        print(f"not in the manifest: {missing}", file=sys.stderr)
        return 2
    fetch = _offline_fetch if args.offline else wayback_fetch(min_interval=args.request_delay)

    if args.show_hash:
        for year in years:
            print(show_hash(manifest[year], fetch, args.cache_dir))
        return 0

    failed = 0
    for year in years:
        result = load_year(manifest[year], fetch, out_dir=args.out_dir, cache_dir=args.cache_dir)
        if result.status == "written":
            print(f"{year}: written rows={result.rows} ranked={result.ranked} -> {result.path}")
            for warning in result.warnings:
                print(f"{year}:   warning: {warning}")
        else:
            failed += 1
            print(f"{year}: {result.status.upper()} {result.detail}", file=sys.stderr)
            continue
        if args.ingest:
            pg = PgConfig(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)
            try:
                done = ingest_year(
                    manifest[year], fetch, out_dir=args.out_dir, cache_dir=args.cache_dir, pg=pg,
                    replace=args.replace, backup_dir=args.backup_dir, receipt_dir=args.receipt_dir,
                    withhold=args.withhold_id,
                )
            except (IngestRefused, ArchiveIntegrityError, ArchiveGuardError, EditionMismatchError) as exc:
                failed += 1
                print(f"{year}: INGEST REFUSED {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            print(
                f"{year}: ingested={done.ingested} (unranked skipped {done.unranked_skipped}) matched={done.matched} "
                f"unresolved={done.unresolved} rows_written={done.rows_written} aggregated_rows={done.aggregated_rows} "
                f"years_aggregated={done.years_aggregated}\n"
                f"{year}:   run_id={done.run_id}\n{year}:   backup={done.backup}\n{year}:   receipt={done.receipt}"
            )
    return 1 if failed else 0


def _load_manifest_unpinned(path: Path) -> dict[int, ManifestEntry]:
    """For --show-hash only: entries whose sha256 is not pinned yet."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[int, ManifestEntry] = {}
    placeholder = "0" * 64
    for year, entry in raw.items():
        if str(year).startswith("_"):
            continue
        entry = json.loads(json.dumps(entry))
        entry.setdefault("data_file", {}).setdefault("expected_sha256", placeholder)
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(entry["data_file"]["expected_sha256"])):
            entry["data_file"]["expected_sha256"] = placeholder
        out[int(year)] = parse_manifest_entry(int(year), entry)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
