import json
import sys
import tempfile
import unittest
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
from qs_universe_registry import QS_GLOBAL  # noqa: E402
from run_pipeline import _apply_qs_snapshot_fallback, _qs_universe_artifact_dir  # noqa: E402


class TestQSResolutionStrategy(unittest.TestCase):
    def test_global_crawler_build_config_preserves_stable_ranking_id(self):
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
        self.assertEqual(config.ranking_id, "3990755")
        self.assertEqual(
            config.ranking_page_url,
            "https://www.topuniversities.com/university-rankings/world-university-rankings",
        )
        self.assertTrue(str(config.resolution_cache_path).endswith("qs_universe_resolution_cache.json"))

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
            run_status_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
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
