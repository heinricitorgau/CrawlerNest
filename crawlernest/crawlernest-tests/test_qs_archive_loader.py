"""Tests for qs_archive_loader: QS past editions from reviewed Internet Archive snapshots.

No test touches the network; the archive is a dict behind the loader's ``FetchBytes``.
What these pin down is the refusals -- a loader that only ever succeeds proves nothing --
and that the file it writes says what it is.
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "crawlernest-jobs"), str(PACKAGE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import qs_archive_loader as L  # noqa: E402
from ranking_edition import EditionMismatchError  # noqa: E402

YEAR = 2024
RANKING_ID = "3897789"
PAGE_ORIGINAL = "https://www.topuniversities.com/university-rankings/world-university-rankings/2024"
DATA_ORIGINAL = f"https://www.topuniversities.com/sites/default/files/qs-rankings-data/en/{RANKING_ID}.txt"
PAGE_TS = "20230627200422"
DATA_TS = "20260329044711"
PAGE_URL = f"https://web.archive.org/web/{PAGE_TS}id_/{PAGE_ORIGINAL}"
DATA_URL = f"https://web.archive.org/web/{DATA_TS}id_/{DATA_ORIGINAL}"


def page_html(title_year: int = YEAR, nids: tuple[str, ...] = (RANKING_ID,)) -> str:
    ids = "".join(f'{{"nid":"{n}"}}' for n in nids)
    return (
        f"<html><head><title>QS World University Rankings {title_year}: Top Global Universities | "
        f"Top Universities</title></head><body><script>var d=[{ids}];</script></body></html>"
    )


def cell(name: str, slug: str) -> str:
    return f'<div class="td-wrap"><a href="/universities/{slug}" class="uni-link">{name}</a></div>'


def make_rows(n: int = 900) -> list[dict]:
    """In QS's order: exact ranks, a tie, then bands of ten."""
    rows: list[dict] = []
    for i in range(1, 151):
        rows.append({"rank_display": str(i)})
    rows += [{"rank_display": "=151"}] * 3
    lower = 201
    while len(rows) < n:
        for _ in range(10):
            rows.append({"rank_display": f"{lower}-{lower + 9}"})
        lower += 10
    rows = rows[:n]
    out = []
    for i, base in enumerate(rows):
        out.append(
            {
                "core_id": str(100 + i),
                "nid": str(1000 + i),
                "country": "Switzerland" if i % 2 else "United States",
                "city": "Somewhere",
                "region": "Europe",
                "title": cell(f"University &amp; Number {i}", f"university-{i}"),
                "score": f"{max(1.0, 100 - i / 10):.1f}",
                "rank_display": base["rank_display"],
            }
        )
    return out


def payload(rows: list[dict] | None = None) -> bytes:
    return json.dumps({"data": rows if rows is not None else make_rows()}).encode()


def entry_for(data: bytes, **overrides) -> L.ManifestEntry:
    raw = {
        "ranking_year": YEAR,
        "edition_page": {"snapshot_url": PAGE_URL, "snapshot_ts": PAGE_TS},
        "data_file": {
            "snapshot_url": DATA_URL,
            "snapshot_ts": DATA_TS,
            "expected_ranking_id": RANKING_ID,
            "expected_sha256": L.sha256_hex(data),
        },
        "reviewed_by": "test",
        "reviewed_on": "2026-10-03",
        "notes": "fixture",
    }
    raw.update(overrides)
    return L.parse_manifest_entry(YEAR, raw)


def archive(data: bytes, html: str | None = None, *, gz: bool = False):
    """A FetchBytes backed by two captures."""
    body = gzip.compress(data) if gz else data
    pages = {PAGE_URL: (200, PAGE_URL, (html if html is not None else page_html()).encode()), DATA_URL: (200, DATA_URL, body)}
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        return pages.get(url, (404, url, b""))

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


class TestRankClassification(unittest.TestCase):
    def test_printed_ranks_become_lower_bounds_and_nothing_else(self):
        self.assertEqual(L.classify_rank("85"), (85, "exact"))
        self.assertEqual(L.classify_rank("=196"), (196, "tied"))
        self.assertEqual(L.classify_rank("201-210"), (201, "banded"))
        self.assertEqual(L.classify_rank("601–650"), (601, "banded"))
        self.assertEqual(L.classify_rank("1401+"), (1401, "open_ended"))

    def test_a_non_rank_is_unranked_not_zero_and_not_guessed(self):
        for text in ("NA", "N/A", "", "—"):
            self.assertEqual(L.classify_rank(text), (None, "unranked"))


class TestTitleCell(unittest.TestCase):
    def test_name_and_profile_path_come_out_of_the_html(self):
        name, path = L.parse_title_cell(cell("Massachusetts Institute of Technology (MIT) ", "massachusetts-institute-technology-mit"))
        self.assertEqual(name, "Massachusetts Institute of Technology (MIT)")
        self.assertEqual(path, "/universities/massachusetts-institute-technology-mit")

    def test_entities_and_nbsp_are_normalised(self):
        name, _ = L.parse_title_cell(cell("Johns&nbsp;Hopkins &amp; Co", "x"))
        self.assertEqual(name, "Johns Hopkins & Co")

    def test_a_cell_without_html_is_just_a_name(self):
        self.assertEqual(L.parse_title_cell("Plain Name"), ("Plain Name", ""))


class TestManifest(unittest.TestCase):
    def good(self):
        return {
            "ranking_year": YEAR,
            "edition_page": {"snapshot_url": PAGE_URL, "snapshot_ts": PAGE_TS},
            "data_file": {
                "snapshot_url": DATA_URL,
                "snapshot_ts": DATA_TS,
                "expected_ranking_id": RANKING_ID,
                "expected_sha256": "a" * 64,
            },
        }

    def test_a_good_entry_parses(self):
        entry = L.parse_manifest_entry(YEAR, self.good())
        self.assertEqual(entry.expected_ranking_id, RANKING_ID)

    def test_timestamp_must_match_the_url(self):
        raw = self.good()
        raw["data_file"]["snapshot_ts"] = "20260329044712"
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)

    def test_only_exact_id_snapshots_are_accepted(self):
        raw = self.good()
        raw["data_file"]["snapshot_url"] = f"https://web.archive.org/web/{DATA_TS}/{DATA_ORIGINAL}"
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)

    def test_only_topuniversities_may_be_archived(self):
        raw = self.good()
        other = "https://example.com/sites/default/files/qs-rankings-data/en/3897789.txt"
        raw["data_file"]["snapshot_url"] = f"https://web.archive.org/web/{DATA_TS}id_/{other}"
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)

    def test_the_page_must_be_this_years_world_ranking_page(self):
        raw = self.good()
        wrong = PAGE_ORIGINAL.replace("/2024", "/2023")
        raw["edition_page"]["snapshot_url"] = f"https://web.archive.org/web/{PAGE_TS}id_/{wrong}"
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)

    def test_an_unpinned_hash_is_refused(self):
        raw = self.good()
        raw["data_file"]["expected_sha256"] = ""
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)

    def test_data_file_id_must_equal_the_pinned_id(self):
        raw = self.good()
        raw["data_file"]["expected_ranking_id"] = "3897788"
        with self.assertRaises(L.ArchiveIntegrityError):
            L.parse_manifest_entry(YEAR, raw)


class TestFetch(unittest.TestCase):
    def ref(self):
        return L.SnapshotRef(DATA_URL, DATA_TS, DATA_ORIGINAL)

    def test_a_redirect_to_a_nearby_capture_is_refused(self):
        other = DATA_URL.replace(DATA_TS, "20260401000000")
        with self.assertRaises(L.ArchiveIntegrityError):
            L.fetch_snapshot(self.ref(), lambda url: (200, other, b"{}"))

    def test_http_errors_are_errors(self):
        with self.assertRaises(L.ArchiveFetchError):
            L.fetch_snapshot(self.ref(), lambda url: (404, url, b""))

    def test_the_archives_offline_page_is_not_data(self):
        with self.assertRaises(L.ArchiveFetchError):
            L.fetch_snapshot(self.ref(), lambda url: (200, url, b"<title>Internet Archive: Temporarily Offline</title>"))

    def test_gzip_and_plain_bodies_decode_to_the_same_bytes(self):
        data = payload()
        self.assertEqual(L.decode_payload(gzip.compress(data)), data)
        self.assertEqual(L.decode_payload(data), data)


class TestVerification(unittest.TestCase):
    def acquired(self, html=None, data=None):
        data = payload() if data is None else data
        return data, L.Acquired(page_html=html if html is not None else page_html(), data_bytes=data)

    def test_the_right_edition_verifies(self):
        data, acquired = self.acquired()
        edition = L.verify_entry(entry_for(data), acquired)
        self.assertEqual(edition.ranking_id, RANKING_ID)
        self.assertEqual(edition.ranking_year, YEAR)

    def test_a_page_titled_for_another_year_is_refused(self):
        data, acquired = self.acquired(html=page_html(title_year=2023))
        with self.assertRaises(EditionMismatchError):
            L.verify_entry(entry_for(data), acquired)

    def test_a_page_declaring_several_ranking_ids_is_refused(self):
        data, acquired = self.acquired(html=page_html(nids=(RANKING_ID, "294786", "294857")))
        with self.assertRaises(EditionMismatchError):
            L.verify_entry(entry_for(data), acquired)

    def test_a_page_whose_id_is_not_the_pinned_one_is_refused(self):
        data, acquired = self.acquired(html=page_html(nids=("3816281",)))
        with self.assertRaises(EditionMismatchError):
            L.verify_entry(entry_for(data), acquired)

    def test_bytes_that_changed_since_review_are_refused(self):
        data, acquired = self.acquired()
        entry = entry_for(data)
        changed = L.Acquired(page_html=acquired.page_html, data_bytes=payload(make_rows(901)))
        with self.assertRaises(L.ArchiveIntegrityError):
            L.verify_entry(entry, changed)


class TestGuards(unittest.TestCase):
    def rows(self, items=None):
        return L.parse_rows(payload(items))

    def test_a_good_table_passes(self):
        self.assertTrue(L.check_guards(self.rows()).ok)

    def test_a_truncated_payload_is_refused(self):
        report = L.check_guards(self.rows(make_rows(100)))
        self.assertFalse(report.ok)
        self.assertTrue(any("truncated" in f for f in report.failures))

    def test_duplicate_nids_are_refused(self):
        items = make_rows()
        items[5]["nid"] = items[4]["nid"]
        self.assertFalse(L.check_guards(self.rows(items)).ok)

    def test_a_table_out_of_rank_order_is_refused(self):
        items = make_rows()
        items[400], items[500] = items[500], items[400]
        report = L.check_guards(self.rows(items))
        self.assertFalse(report.ok)
        self.assertTrue(any("rank order" in f for f in report.failures))

    def test_one_adjacent_swap_inside_a_tie_is_the_sources_order_and_only_warns(self):
        # QS 2019 prints Louvain "165" before Liverpool "164"; both score 47.9.
        items = make_rows()
        items[120], items[121] = items[121], items[120]
        report = L.check_guards(self.rows(items))
        self.assertTrue(report.ok, report.failures)
        self.assertTrue(any("out of rank order" in w for w in report.warnings))

    def test_a_row_far_out_of_place_is_refused_even_if_it_is_only_one(self):
        items = make_rows()
        items.insert(150, items.pop(700))
        self.assertFalse(L.check_guards(self.rows(items)).ok)

    def test_a_few_blank_countries_warn_but_many_refuse(self):
        items = make_rows()
        for item in items[:17]:
            item["country"] = ""
        report = L.check_guards(self.rows(items))
        self.assertTrue(report.ok, report.failures)
        self.assertTrue(any("no country" in w for w in report.warnings))
        for item in items[:100]:
            item["country"] = ""
        self.assertFalse(L.check_guards(self.rows(items)).ok)

    def test_a_table_that_does_not_start_at_one_is_refused(self):
        items = make_rows()[1:]
        self.assertFalse(L.check_guards(self.rows(items)).ok)

    def test_blank_names_beyond_the_tolerance_are_refused(self):
        items = make_rows()
        for item in items[:20]:
            item["title"] = ""
        self.assertFalse(L.check_guards(self.rows(items)).ok)

    def test_a_very_different_neighbour_only_warns(self):
        rows = self.rows()
        report = L.check_guards(rows, neighbor=(2023, [f"Other {i}" for i in range(50)], len(rows)))
        self.assertTrue(report.ok)
        self.assertTrue(report.warnings)


class TestLoadYear(unittest.TestCase):
    def test_a_load_writes_a_file_that_says_what_it_is(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), archive(data, gz=True), out_dir=Path(tmp))
            self.assertEqual(result.status, "written", result.detail)
            written = json.loads(Path(result.path).read_text(encoding="utf-8"))
        meta = written["metadata"]
        self.assertEqual(meta["source_kind"], "web_archive")
        self.assertEqual(meta["archive_snapshot_url"], DATA_URL)
        self.assertEqual(meta["snapshot_timestamp"], DATA_TS)
        self.assertEqual(meta["payload_sha256"], L.sha256_hex(data))
        self.assertTrue(meta["edition"]["verified"])
        self.assertEqual(meta["edition"]["ranking_id"], RANKING_ID)
        self.assertEqual(meta["row_count"], len(written["rows"]))
        self.assertEqual(sum(meta["rank_counts"].values()), meta["row_count"])

    def test_ranks_are_lower_bounds_and_the_printed_rank_is_kept(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), archive(data), out_dir=Path(tmp))
            rows = json.loads(Path(result.path).read_text(encoding="utf-8"))["rows"]
        by_display = {}
        for row in rows:
            by_display.setdefault(row["rank_display"], row)
        self.assertEqual(by_display["1"]["rank"], 1)
        self.assertEqual(by_display["=151"]["rank"], 151)
        self.assertEqual(by_display["201-210"]["rank"], 201)
        self.assertEqual(by_display["201-210"]["metadata"]["rank_kind"], "banded")
        self.assertEqual(by_display["1"]["id"], "/universities/university-0")
        self.assertEqual(by_display["1"]["name"], "University & Number 0")

    def test_an_unranked_row_is_kept_without_a_rank(self):
        items = make_rows()
        items.append({**items[-1], "nid": "99999", "title": cell("Unranked U", "unranked-u"), "rank_display": "NA"})
        data = payload(items)
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), archive(data), out_dir=Path(tmp))
            written = json.loads(Path(result.path).read_text(encoding="utf-8"))
        unranked = [r for r in written["rows"] if r["name"] == "Unranked U"]
        self.assertEqual(unranked[0]["rank"], None)
        self.assertEqual(written["metadata"]["rank_counts"]["unranked"], 1)
        self.assertEqual(written["metadata"]["valid_rank_count"], written["metadata"]["row_count"] - 1)

    def test_a_refused_edition_writes_nothing(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(
                entry_for(data), archive(data, html=page_html(title_year=2023)), out_dir=Path(tmp)
            )
            self.assertEqual(result.status, "refused")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_a_guard_failure_writes_nothing(self):
        data = payload(make_rows(100))
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), archive(data), out_dir=Path(tmp))
            self.assertEqual(result.status, "refused")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_the_same_inputs_give_identical_bytes(self):
        data = payload()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            ra = L.load_year(entry_for(data), archive(data), out_dir=Path(a))
            rb = L.load_year(entry_for(data), archive(data), out_dir=Path(b))
            self.assertEqual(Path(ra.path).read_bytes(), Path(rb.path).read_bytes())

    def test_a_file_this_loader_did_not_write_is_never_replaced(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            target = L.artifact_path(Path(tmp), YEAR)
            target.write_text(json.dumps({"metadata": {"source": "QS"}, "rows": []}), encoding="utf-8")
            result = L.load_year(entry_for(data), archive(data), out_dir=Path(tmp))
            self.assertEqual(result.status, "refused")
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"metadata": {"source": "QS"}, "rows": []})

    def test_a_file_this_loader_wrote_can_be_regenerated(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(L.load_year(entry_for(data), archive(data), out_dir=Path(tmp)).status, "written")
            self.assertEqual(L.load_year(entry_for(data), archive(data), out_dir=Path(tmp)).status, "written")

    def test_the_cache_serves_a_second_run_without_the_network(self):
        data = payload()
        fetch = archive(data)
        with tempfile.TemporaryDirectory() as out, tempfile.TemporaryDirectory() as cache:
            first = L.load_year(entry_for(data), fetch, out_dir=Path(out), cache_dir=Path(cache))
            self.assertEqual(first.status, "written", first.detail)
            before = len(fetch.calls)
            second = L.load_year(entry_for(data), L._offline_fetch, out_dir=Path(out), cache_dir=Path(cache))
            self.assertEqual(second.status, "written", second.detail)
            self.assertEqual(len(fetch.calls), before)

    def test_an_outage_is_reported_as_an_error_not_a_refusal(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), lambda url: (503, url, b""), out_dir=Path(tmp))
            self.assertEqual(result.status, "error")


class TestNotMistakenForAnotherSource(unittest.TestCase):
    def test_the_artifact_is_not_a_live_crawl_file(self):
        data = payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = L.load_year(entry_for(data), archive(data), out_dir=Path(tmp))
            meta = json.loads(Path(result.path).read_text(encoding="utf-8"))["metadata"]
        # The live crawl artifacts carry no source_kind; this one must never read as one.
        self.assertEqual(meta["source_kind"], L.SOURCE_KIND)
        self.assertIn("lower bound", meta["rank_convention"])


if __name__ == "__main__":
    unittest.main()
