"""A crawl may label rows with a ranking_year only after proving it read that edition.

The fixtures mirror what the live sites served on 2026-09-13: QS's unversioned
world page titled "... 2027" (nid 4153156) while /world-university-rankings/2026
declared 4061771; QS Europe 2026 reachable only unversioned; QS Sub-Saharan
Africa titled with no year at all; THE's /2026/ page redirecting to /latest/.
The 2026-09-02 crawl read the unversioned page and ingested the 2027 table as
2026 -- every case below is a way that could happen again.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
for mod in ("crawlernest-core", "crawlernest-extractors", "crawlernest-jobs", "crawlernest-db-writer", "crawlernest-analytics"):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

from ranking_edition import (  # noqa: E402
    EditionMismatchError,
    VerifiedEdition,
    assert_crawled_edition,
    qs_edition_page_candidates,
    resolve_qs_edition,
    snapshot_edition_ok,
    verify_arwu_page_url,
    verify_qs_edition_page,
    verify_the_edition_page,
)

WORLD = "https://www.topuniversities.com/university-rankings/world-university-rankings"
EUROPE = "https://www.topuniversities.com/europe-university-rankings"
SSA = "https://www.topuniversities.com/sub-saharan-africa-university-rankings"


def qs_page(title: str, nid: str | None, *, linked: tuple[str, ...] = ("4161492", "889350")) -> str:
    declared = f'<script>var s = {{"nid":"{nid}"}};</script>' if nid else ""
    links = "".join(f'<a href="/rankings?nid={n}">x</a>' for n in linked)
    return f"<html><head><title>{title}</title></head><body>{declared}{links}</body></html>"


LIVE_QS = {
    "https://www.topuniversities.com/world-university-rankings/2025": (200, qs_page("QS World University Rankings 2025: Top Global Universities", "3990755")),
    "https://www.topuniversities.com/world-university-rankings/2026": (200, qs_page("QS World University Rankings 2026: Top Global Universities", "4061771")),
    "https://www.topuniversities.com/world-university-rankings": (200, qs_page("QS World University Rankings 2027: Top Global Universities", "4153156")),
    WORLD: (200, qs_page("QS World University Rankings 2027: Top Global Universities", "4153156")),
    f"{EUROPE}/2026": (404, "<title>Page not found</title>"),
    EUROPE: (200, qs_page("European University Rankings 2026 | Top Universities", "4104407")),
    f"{SSA}/2026": (404, "<title>Page not found</title>"),
    SSA: (200, qs_page("QS Rankings Sub-Saharan Africa | TopUniversities", "4104268")),
}


def fake_fetch(pages):
    calls: list[str] = []

    def _fetch(url):
        calls.append(url)
        status, body = pages.get(url, (404, ""))
        return status, url, body

    _fetch.calls = calls
    return _fetch


class TestQSEditionResolution(unittest.TestCase):
    def test_the_world_edition_page_is_tried_before_the_unversioned_one(self):
        self.assertEqual(
            [
                "https://www.topuniversities.com/world-university-rankings/2026",
                "https://www.topuniversities.com/world-university-rankings",
                WORLD,
            ],
            qs_edition_page_candidates(WORLD, 2026),
        )

    def test_2026_resolves_to_the_2026_table_not_the_page_now_serving_2027(self):
        edition = resolve_qs_edition(WORLD, 2026, fake_fetch(LIVE_QS))
        self.assertEqual("4061771", edition.ranking_id)
        self.assertEqual(2026, edition.ranking_year)

    def test_each_edition_gets_its_own_id(self):
        self.assertEqual("3990755", resolve_qs_edition(WORLD, 2025, fake_fetch(LIVE_QS)).ranking_id)
        self.assertEqual("4153156", resolve_qs_edition(WORLD, 2027, fake_fetch(LIVE_QS)).ranking_id)

    def test_the_unversioned_page_is_accepted_only_when_its_title_names_the_year(self):
        """QS Europe 2026 has no /2026 page; its unversioned page is titled 2026."""
        self.assertEqual("4104407", resolve_qs_edition(EUROPE, 2026, fake_fetch(LIVE_QS)).ranking_id)
        pages = dict(LIVE_QS)
        del pages["https://www.topuniversities.com/world-university-rankings/2026"]
        with self.assertRaises(EditionMismatchError):
            resolve_qs_edition(WORLD, 2026, fake_fetch(pages))

    def test_a_page_that_names_no_year_proves_nothing(self):
        with self.assertRaisesRegex(EditionMismatchError, "no year"):
            resolve_qs_edition(SSA, 2026, fake_fetch(LIVE_QS))

    def test_a_pin_must_be_the_id_the_edition_page_declares(self):
        with self.assertRaisesRegex(EditionMismatchError, "Pinned ranking id 4153156 is not edition 2026"):
            resolve_qs_edition(WORLD, 2026, fake_fetch(LIVE_QS), pinned_ranking_id="4153156")
        self.assertEqual(
            "4061771",
            resolve_qs_edition(WORLD, 2026, fake_fetch(LIVE_QS), pinned_ranking_id="4061771").ranking_id,
        )

    def test_no_page_means_no_proof_even_with_a_pin(self):
        """How the subject pins (computer-science's was the 2025 table) went unchecked."""
        with self.assertRaisesRegex(EditionMismatchError, "unverifiable"):
            resolve_qs_edition(None, 2026, fake_fetch({}), pinned_ranking_id="4023722")

    def test_linked_nids_are_not_the_pages_own(self):
        with self.assertRaisesRegex(EditionMismatchError, "declares 0 ranking ids"):
            verify_qs_edition_page(qs_page("QS World University Rankings 2026", None), page_url="u", ranking_year=2026)

    def test_a_title_naming_two_years_is_ambiguous(self):
        with self.assertRaises(EditionMismatchError):
            verify_qs_edition_page(
                qs_page("QS World University Rankings 2026 vs 2027", "1"), page_url="u", ranking_year=2026
            )

    def test_the_crawl_must_have_fetched_the_verified_id(self):
        edition = VerifiedEdition("QS", 2026, "u", "t", ranking_id="4061771")
        assert_crawled_edition(edition, "4061771")
        with self.assertRaises(EditionMismatchError):
            assert_crawled_edition(edition, "4153156")


class TestFetcherHonoursTheVerifiedEdition(unittest.TestCase):
    def _fetcher(self):
        from config import Config
        from fetcher import UniversityFetcher

        config = Config(ranking_id="", ranking_page_url=WORLD, universe_type="global", universe_key="global", ranking_year=2026)
        setattr(config, "_edition_ranking_id", "4061771")
        return config, UniversityFetcher(config)

    def test_the_verified_id_beats_a_cache_entry_left_by_the_unversioned_page(self):
        config, fetcher = self._fetcher()
        stale = {"ranking_id": "4153156", "ranking_id_candidates": ["4153156"], "subregion_id": "",
                 "resolved_ranking_page_url": WORLD, "api_url": "", "resolved_at": "2026-09-02T06:47:00Z"}
        with patch("fetcher._read_cached_resolution", return_value=stale):
            self.assertEqual("4061771", fetcher._ensure_ranking_id())
        self.assertEqual("edition_page", config._ranking_id_source)
        self.assertFalse(config._used_resolution_cache)

    def test_a_forced_refresh_does_not_re_resolve_off_the_latest_page(self):
        config, fetcher = self._fetcher()
        with patch.object(fetcher, "_session_get_transient_retry", side_effect=AssertionError("page fetched")):
            self.assertEqual("4061771", fetcher._ensure_ranking_id(force_refresh=True))


class TestUniverseCrawlerRefusesBeforeFetching(unittest.TestCase):
    def _crawler(self, spec, pages):
        from qs_universe_crawlers import QSGlobalCrawler

        crawler = QSGlobalCrawler(spec=spec, limit=5, ranking_year=2026, use_async=False, workers=1,
                                  request_delay=0.0, local_parse_workers=1)
        crawler.edition_fetch = fake_fetch(pages)
        return crawler

    def test_an_unprovable_edition_crawls_nothing(self):
        from qs_universe_registry import get_qs_universe_spec

        crawler = self._crawler(get_qs_universe_spec("regional", "sub-saharan-africa"), LIVE_QS)
        with patch("qs_universe_crawlers.UniversityCrawler", side_effect=AssertionError("crawled")):
            with self.assertRaises(EditionMismatchError):
                crawler.crawl()

    def test_the_crawl_runs_on_the_edition_id_and_records_it(self):
        from qs_universe_registry import QS_GLOBAL

        seen = {}

        class FakeCrawler:
            def __init__(self, config):
                self.config = config
                self.interrupted = False

            def crawl(self):
                from fetcher import _apply_edition_ranking_id

                seen["page"] = self.config.ranking_page_url
                seen["id"] = _apply_edition_ranking_id(self.config)
                return ["row"]

        crawler = self._crawler(QS_GLOBAL, LIVE_QS)
        with patch("qs_universe_crawlers.UniversityCrawler", FakeCrawler), \
                patch("qs_universe_crawlers._persist_resolution_cache"):
            rows, meta = crawler.crawl()
        self.assertEqual(["row"], rows)
        self.assertEqual("4061771", seen["id"])
        self.assertEqual("https://www.topuniversities.com/world-university-rankings/2026", seen["page"])
        self.assertEqual({"verified": True, "ranking_year": 2026, "ranking_id": "4061771"},
                         {k: meta["edition"][k] for k in ("verified", "ranking_year", "ranking_id")})


class TestTHEAndARWUEditions(unittest.TestCase):
    @staticmethod
    def the_page(year, rows=({"rank": "1", "name": "University of Oxford"},)):
        data = {"props": {"pageProps": {"page": {"rankingsTableConfig": {"year": year, "rankingsData": {"data": list(rows)}}}}}}
        return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'

    def test_the_table_year_must_be_the_requested_edition(self):
        edition, rows = verify_the_edition_page(self.the_page(2026), page_url="https://x/latest/world-ranking", ranking_year=2026)
        self.assertEqual((2026, 1), (edition.ranking_year, len(rows)))
        with self.assertRaisesRegex(EditionMismatchError, "holds the 2026 table, not 2025"):
            verify_the_edition_page(self.the_page(2026), page_url="https://x/latest/world-ranking", ranking_year=2025)

    def test_a_page_without_a_dated_table_is_refused(self):
        with self.assertRaises(EditionMismatchError):
            verify_the_edition_page("<html></html>", page_url="https://x/world-university-rankings", ranking_year=2026)
        with self.assertRaises(EditionMismatchError):
            verify_the_edition_page(self.the_page(2026, rows=()), page_url="u", ranking_year=2026)

    def test_arwu_redirected_to_another_edition_is_refused(self):
        self.assertEqual(2025, verify_arwu_page_url("https://www.shanghairanking.com/rankings/arwu/2025", ranking_year=2025).ranking_year)
        with self.assertRaises(EditionMismatchError):
            verify_arwu_page_url("https://www.shanghairanking.com/rankings/arwu/2024", ranking_year=2025)
        with self.assertRaises(EditionMismatchError):
            verify_arwu_page_url("https://www.shanghairanking.com/rankings/arwu", ranking_year=2025)


class TestSnapshotsReplayOnlyVerifiedEditions(unittest.TestCase):
    VERIFIED = {"status": "ok", "crawl_meta": {"edition": {"verified": True, "ranking_year": 2026, "ranking_id": "4061771"}}}

    def test_snapshot_rule(self):
        self.assertTrue(snapshot_edition_ok(self.VERIFIED, ranking_year=2026))
        self.assertTrue(snapshot_edition_ok(self.VERIFIED, ranking_year=2026, ranking_id="4061771"))
        self.assertFalse(snapshot_edition_ok(self.VERIFIED, ranking_year=2025))
        self.assertFalse(snapshot_edition_ok(self.VERIFIED, ranking_year=2026, ranking_id="4153156"))
        self.assertFalse(snapshot_edition_ok({"status": "ok", "crawl_meta": {}}, ranking_year=2026))
        self.assertFalse(snapshot_edition_ok(None, ranking_year=2026))

    def test_the_blocked_run_fallback_refuses_a_pre_guard_snapshot(self):
        from run_pipeline import _apply_qs_snapshot_fallback, _qs_universe_artifact_dir

        for run_status, expected_rows in (({"status": "ok"}, 0), (self.VERIFIED, 1)):
            with self.subTest(verified=bool(run_status.get("crawl_meta"))), tempfile.TemporaryDirectory() as tmp:
                universe_dir = _qs_universe_artifact_dir(Path(tmp), 2026, "global", "global")
                universe_dir.mkdir(parents=True)
                (universe_dir / "raw_snapshot.json").write_text(json.dumps(
                    [{"rank": "1", "name": "Example University", "path": "/universities/example", "country": "X", "table_metrics": {}}]
                ), encoding="utf-8")
                (universe_dir / "run_status.json").write_text(json.dumps(run_status), encoding="utf-8")
                rows, meta = _apply_qs_snapshot_fallback(
                    [], {"failure_classification": "upstream_blocked"}, artifact_base_dir=Path(tmp),
                    ranking_year=2026, universe_type="global", universe_key="global",
                )
                self.assertEqual(expected_rows, len(rows))

    def test_reingest_skips_a_snapshot_without_a_verified_edition(self):
        sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
        import reingest_qs_universes

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_status.json"
            self.assertFalse(reingest_qs_universes.edition_verified(path, 2026))
            path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            self.assertFalse(reingest_qs_universes.edition_verified(path, 2026))
            path.write_text(json.dumps(self.VERIFIED), encoding="utf-8")
            self.assertTrue(reingest_qs_universes.edition_verified(path, 2026))


class TestLegacyBackfillNeverOverwritesAnIngestedRank(unittest.TestCase):
    """The legacy QS seed fills gaps; it does not replace an edition-verified row.

    Asserted on the statement rather than against PostgreSQL because the function
    re-aggregates every held year as a side effect, which a test must not do to a
    developer's warehouse.
    """

    def test_the_upsert_is_do_nothing(self):
        import inspect
        import re

        from crawlernest.pipeline.commands import canonical

        source = inspect.getsource(canonical.backfill_qs_ranking_records_from_legacy)
        insert = source[source.index("INSERT INTO warehouse.ranking_record"):]
        insert = re.sub(r"--[^\n]*", "", insert)
        self.assertRegex(insert, r"ON CONFLICT \([^)]*\)\s*DO NOTHING")
        self.assertNotIn("DO UPDATE", insert.split("SELECT DISTINCT ranking_year")[0])


if __name__ == "__main__":
    unittest.main()
