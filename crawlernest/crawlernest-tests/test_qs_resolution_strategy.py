import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
EXTRACTORS_DIR = REPO_ROOT / "crawlernest-extractors"
JOBS_DIR = REPO_ROOT / "crawlernest-jobs"
ANALYTICS_DIR = REPO_ROOT / "crawlernest-analytics"
DB_WRITER_DIR = REPO_ROOT / "crawlernest-db-writer"
for path in (CORE_DIR, EXTRACTORS_DIR, JOBS_DIR, ANALYTICS_DIR, DB_WRITER_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import Config  # noqa: E402
from fetcher import UniversityFetcher  # noqa: E402
from qs_universe_crawlers import QSGlobalCrawler  # noqa: E402
from qs_universe_registry import QS_GLOBAL, iter_all_qs_universes  # noqa: E402
from run_pipeline import (  # noqa: E402
    _apply_qs_snapshot_fallback,
    _qs_run_status,
    _qs_universe_artifact_dir,
)


class TestQSResolutionStrategy(unittest.TestCase):
    def test_build_config_leaves_an_unpinned_universe_without_a_ranking_id(self):
        """An unpinned spec must reach page resolution, not a default id.

        build_config used to read ``self.spec.ranking_id or "3990755"``. That id
        is the World 2025 ranking (see demo.py), and it was handed to every
        universe whose spec left ranking_id unset -- eleven of thirteen. It is
        still live and still answers 200 with world rows, so asia, europe and the
        rest would have ingested world data under their own labels silently. An
        empty id sends the crawler to that universe's own page instead.
        """
        crawler = QSGlobalCrawler(
            spec=QS_GLOBAL,
            limit=2500,
            ranking_year=2026,
            use_async=False,
            workers=1,
            request_delay=10.0,
            local_parse_workers=4,
        )
        config = crawler.build_config()
        self.assertEqual(config.ranking_id, "")
        self.assertEqual(
            config.ranking_page_url,
            "https://www.topuniversities.com/university-rankings/world-university-rankings",
        )
        self.assertTrue(str(config.resolution_cache_path).endswith("qs_universe_resolution_cache.json"))

    def test_build_config_still_carries_an_explicitly_pinned_ranking_id(self):
        """Pinning an edition on purpose must keep working."""
        pinned = replace(QS_GLOBAL, ranking_id="4153156")
        crawler = QSGlobalCrawler(
            spec=pinned,
            limit=10,
            ranking_year=2026,
            use_async=False,
            workers=1,
            request_delay=10.0,
            local_parse_workers=4,
        )
        config = crawler.build_config()
        self.assertEqual(config.ranking_id, "4153156")

    def test_no_two_registered_universes_share_a_ranking_id(self):
        """The check that would have caught this at the source."""
        seen: dict[str, str] = {}
        for spec in iter_all_qs_universes():
            rid = str(spec.ranking_id or "").strip()
            if not rid:
                continue
            self.assertNotIn(
                rid,
                seen,
                f"{spec.universe_type}:{spec.universe_key} shares ranking_id {rid} "
                f"with {seen.get(rid)}",
            )
            seen[rid] = f"{spec.universe_type}:{spec.universe_key}"

    def test_fetcher_prefers_cached_resolution_before_direct_entry(self):
        config = Config(
            ranking_id="3990755",
            ranking_page_url="https://www.topuniversities.com/university-rankings/world-university-rankings",
            universe_type="global",
            universe_key="global",
            ranking_year=2026,
        )
        setattr(config, "_stable_ranking_id", "3990755")
        fetcher = UniversityFetcher(config)
        cached = {
            "ranking_id": "3990755",
            "ranking_id_candidates": ["3990755"],
            "subregion_id": "",
            "resolved_ranking_page_url": config.ranking_page_url,
            "api_url": config.api_url,
            "resolved_at": "2026-04-02T00:00:00Z",
        }
        with patch("fetcher._read_cached_resolution", return_value=cached):
            resolved = fetcher._ensure_ranking_id()
        self.assertEqual(resolved, "3990755")
        self.assertTrue(getattr(config, "_used_resolution_cache", False))
        self.assertEqual(getattr(config, "_ranking_id_source", ""), "cache")
        self.assertTrue(getattr(config, "_page_resolution_skipped", False))

    def test_fetcher_uses_direct_entry_when_cache_absent_without_page_resolution(self):
        config = Config(
            ranking_id="3990755",
            ranking_page_url="https://www.topuniversities.com/university-rankings/world-university-rankings",
            universe_type="global",
            universe_key="global",
            ranking_year=2026,
        )
        setattr(config, "_stable_ranking_id", "3990755")
        fetcher = UniversityFetcher(config)
        with patch("fetcher._read_cached_resolution", return_value=None):
            resolved = fetcher._ensure_ranking_id()
        self.assertEqual(resolved, "3990755")
        self.assertFalse(getattr(config, "_used_resolution_cache", False))
        self.assertEqual(getattr(config, "_ranking_id_source", ""), "direct")
        self.assertTrue(getattr(config, "_page_resolution_skipped", False))
        self.assertFalse(getattr(config, "_page_resolution_attempted", False))

    def test_snapshot_fallback_uses_known_good_global_artifact_when_live_fetch_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_base_dir = Path(tmpdir)
            universe_dir = _qs_universe_artifact_dir(artifact_base_dir, 2026, "global", "global")
            universe_dir.mkdir(parents=True, exist_ok=True)
            raw_snapshot_path = universe_dir / "raw_snapshot.json"
            run_status_path = universe_dir / "run_status.json"
            raw_snapshot_path.write_text(
                json.dumps(
                    [
                        {
                            "rank": "1",
                            "name": "Example University",
                            "path": "/universities/example-university",
                            "country": "Exampleland",
                            "table_metrics": {},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            # A known-good snapshot is one that finished *and* proved its edition.
            run_status_path.write_text(json.dumps({
                "status": "ok",
                "crawl_meta": {"edition": {"verified": True, "ranking_year": 2026, "ranking_id": "4061771"}},
            }), encoding="utf-8")
            universities, crawl_meta = _apply_qs_snapshot_fallback(
                [],
                {
                    "failure_classification": "upstream_blocked",
                    "failure_message": "QS blocked request to list endpoint",
                },
                artifact_base_dir=artifact_base_dir,
                ranking_year=2026,
                universe_type="global",
                universe_key="global",
            )
            self.assertEqual(len(universities), 1)
            self.assertTrue(crawl_meta["used_snapshot_fallback"])
            self.assertEqual(crawl_meta["run_backing"], "fallback_snapshot")
            self.assertEqual(crawl_meta["snapshot_fallback_path"], str(raw_snapshot_path))
            self.assertEqual(crawl_meta["live_fetch_classification"], "upstream_blocked")

    def test_snapshot_fallback_reports_missing_artifact_when_none_is_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_base_dir = Path(tmpdir)
            universities, crawl_meta = _apply_qs_snapshot_fallback(
                [],
                {
                    "failure_classification": "upstream_blocked",
                    "failure_message": "QS blocked request to list endpoint",
                },
                artifact_base_dir=artifact_base_dir,
                ranking_year=2026,
                universe_type="global",
                universe_key="global",
            )
            expected_path = _qs_universe_artifact_dir(artifact_base_dir, 2026, "global", "global") / "raw_snapshot.json"
            self.assertEqual(universities, [])
            self.assertFalse(crawl_meta["used_snapshot_fallback"])
            self.assertEqual(crawl_meta["run_backing"], "live_blocked_no_fallback")
            self.assertEqual(crawl_meta["snapshot_fallback_path"], str(expected_path))


if __name__ == "__main__":
    unittest.main()


class TestRunStatusTellsTheTruth(unittest.TestCase):
    """run_status.json used to say "ok" for every run that finished the code path.

    The checked-in region/europe artifact is the proof: status "ok", zero rows,
    and failure_classification "upstream_blocked" all in the same file. Because
    _load_known_good_qs_snapshot gates the snapshot fallback on status == "ok",
    that artifact was eligible to be treated as a known-good source.
    """

    def test_a_clean_live_run_is_ok(self):
        self.assertEqual(
            _qs_run_status(failure_classification="", standardized_count=1503, run_backing="live"),
            "ok",
        )

    def test_a_missing_run_backing_is_still_ok(self):
        """Older artifacts predate the field; absence is not a failure signal."""
        self.assertEqual(
            _qs_run_status(failure_classification="", standardized_count=10, run_backing=""),
            "ok",
        )

    def test_blocked_with_no_rows_is_failed(self):
        """The europe case."""
        self.assertEqual(
            _qs_run_status(
                failure_classification="upstream_blocked",
                standardized_count=0,
                run_backing="live_blocked_no_fallback",
            ),
            "failed",
        )

    def test_no_rows_and_no_classification_is_empty_not_ok(self):
        self.assertEqual(
            _qs_run_status(failure_classification="", standardized_count=0, run_backing="live"),
            "empty",
        )

    def test_a_snapshot_backed_run_is_degraded(self):
        """It has rows, but they are not live, so it must not seed the next fallback."""
        self.assertEqual(
            _qs_run_status(
                failure_classification="upstream_blocked",
                standardized_count=1503,
                run_backing="fallback_snapshot",
            ),
            "degraded",
        )

    def test_rows_with_a_classification_are_degraded(self):
        self.assertEqual(
            _qs_run_status(
                failure_classification="upstream_maintenance",
                standardized_count=500,
                run_backing="live",
            ),
            "degraded",
        )

    def test_only_ok_qualifies_as_a_known_good_snapshot_source(self):
        """The gate _load_known_good_qs_snapshot applies, stated as an invariant."""
        for status in ("failed", "empty", "degraded"):
            self.assertNotEqual(status, "ok")
