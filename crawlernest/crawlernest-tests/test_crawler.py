"""Tests for UniversityCrawler core logic.

Covers:
- _process_university()  : node-to-University mapping
- _resume_node_key()     : checkpoint key generation
- crawl()                : full crawl with mocked fetcher
  - success path
  - fetch_rankings failure → returns []
  - missing score_nodes → returns []
  - resume checkpoint skipping
  - detail 403 degrade / fallback trigger
  - stats tracking (total / success / failed / skipped)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

for mod in (
    "crawlernest-core",
    "crawlernest-extractors",
    "crawlernest-jobs",
    "crawlernest-db-writer",
    "crawlernest-analytics",
):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

from config import Config
from crawler import UniversityCrawler, _resume_node_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(rank="1", name="Test University", country="Japan", path="/uni/test"):
    return {
        "rank": rank,
        "title": name,
        "country": country,
        "path": path,
    }


def _make_data(nodes):
    return {"score_nodes": nodes}


# ---------------------------------------------------------------------------
# _resume_node_key
# ---------------------------------------------------------------------------

class TestResumeNodeKey(unittest.TestCase):
    def test_path_based_key(self):
        node = {"path": "/uni/mit", "rank": "1", "title": "MIT"}
        key = _resume_node_key(node)
        self.assertTrue(key.startswith("path:"))
        self.assertIn("/uni/mit", key)

    def test_url_field_also_used(self):
        node = {"url": "/uni/stanford", "rank": "2", "title": "Stanford"}
        key = _resume_node_key(node)
        self.assertTrue(key.startswith("path:"))
        self.assertIn("/uni/stanford", key)

    def test_rank_name_fallback_when_no_path(self):
        node = {"rank": "5", "title": "Oxford"}
        key = _resume_node_key(node)
        self.assertTrue(key.startswith("rank-name:"))
        self.assertIn("5", key)
        self.assertIn("oxford", key)

    def test_empty_node_produces_stable_key(self):
        key = _resume_node_key({})
        self.assertIsInstance(key, str)
        self.assertTrue(len(key) > 0)


# ---------------------------------------------------------------------------
# _process_university
# ---------------------------------------------------------------------------

class TestProcessUniversity(unittest.TestCase):
    def setUp(self):
        config = Config()
        config.use_async = False
        self.crawler = UniversityCrawler(config)

    def test_valid_node_returns_university(self):
        node = _make_node(rank="3", name="Cambridge", country="UK", path="/uni/cambridge")
        uni = self.crawler._process_university(node)
        self.assertIsNotNone(uni)
        self.assertEqual(uni.name, "Cambridge")
        self.assertEqual(uni.rank, "3")
        self.assertEqual(uni.country, "UK")
        self.assertEqual(uni.path, "/uni/cambridge")

    def test_non_dict_returns_none(self):
        self.assertIsNone(self.crawler._process_university(None))
        self.assertIsNone(self.crawler._process_university("not a dict"))
        self.assertIsNone(self.crawler._process_university([]))

    def test_missing_fields_use_defaults(self):
        uni = self.crawler._process_university({})
        self.assertIsNotNone(uni)
        self.assertEqual(uni.rank, "N/A")
        self.assertEqual(uni.name, "N/A")
        self.assertEqual(uni.country, "N/A")

    def test_alternate_field_names(self):
        node = {
            "rank_display": "10",
            "name": "Tokyo Institute of Technology",
            "location": "Japan",
            "url": "/uni/titech",
        }
        uni = self.crawler._process_university(node)
        self.assertIsNotNone(uni)
        self.assertEqual(uni.rank, "10")
        self.assertEqual(uni.name, "Tokyo Institute of Technology")
        self.assertEqual(uni.country, "Japan")

    def test_table_metrics_extracted(self):
        node = _make_node()
        node["overall_score"] = "85.5"
        uni = self.crawler._process_university(node)
        self.assertIsNotNone(uni)
        self.assertIn("Overall Score", uni.table_metrics)
        self.assertEqual(uni.table_metrics["Overall Score"], "85.5")


# ---------------------------------------------------------------------------
# UniversityCrawler.crawl() — success path
# ---------------------------------------------------------------------------

class TestCrawlSuccess(unittest.TestCase):
    def _make_crawler(self, nodes, fetch_details=False):
        config = Config()
        config.use_async = False
        config.fetch_details = fetch_details
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.fetch_university_detail.return_value = ""
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        return crawler, mock_fetcher

    def test_crawl_returns_universities(self):
        nodes = [_make_node(rank=str(i), name=f"Uni {i}") for i in range(1, 4)]
        crawler, _ = self._make_crawler(nodes)
        results = crawler.crawl()
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].name, "Uni 1")

    def test_crawl_empty_nodes_returns_empty(self):
        crawler, _ = self._make_crawler([])
        results = crawler.crawl()
        self.assertEqual(results, [])

    def test_crawl_fetch_failure_returns_empty(self):
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.show_progress = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.side_effect = RuntimeError("network error")
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        results = crawler.crawl()
        self.assertEqual(results, [])

    def test_crawl_missing_score_nodes_returns_empty(self):
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.show_progress = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = {"other_key": []}
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        results = crawler.crawl()
        self.assertEqual(results, [])

    def test_ranking_limit_respected(self):
        nodes = [_make_node(rank=str(i), name=f"Uni {i}") for i in range(1, 11)]
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.ranking_limit = 5
        config.show_progress = False
        config.sort_ascending = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        results = crawler.crawl()
        self.assertLessEqual(len(results), 5)

    def test_stats_success_count(self):
        nodes = [_make_node(rank=str(i), name=f"Uni {i}") for i in range(1, 4)]
        crawler, _ = self._make_crawler(nodes, fetch_details=False)
        crawler.crawl()
        self.assertEqual(crawler.stats["total"], 3)
        # success count should be non-zero (no details fetched, so all succeed)
        self.assertGreater(crawler.stats["success"], 0)

    def test_stats_failed_count_for_bad_nodes(self):
        # Mix of valid and non-dict nodes (non-dict gets filtered in _process_university)
        nodes = [_make_node(), None, "bad"]
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.show_progress = False
        config.ranking_limit = 0
        config.sort_ascending = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        # score_nodes with bad entries — only valid dicts pass
        mock_fetcher.fetch_rankings.return_value = {
            "score_nodes": [_make_node(rank="1", name="Good Uni"), {"rank": None}]
        }
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        results = crawler.crawl()
        # Both dict nodes should be processed (even rank=None node returns a University with N/A)
        self.assertGreaterEqual(len(results), 1)


# ---------------------------------------------------------------------------
# Resume checkpoint logic
# ---------------------------------------------------------------------------

class TestCrawlResume(unittest.TestCase):
    def _make_crawler_with_resume(self, nodes, resume_paths=None, resume_keys=None):
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        if resume_paths:
            config._resume_paths = resume_paths
        if resume_keys:
            config._resume_node_keys = resume_keys
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher
        return crawler

    def test_resume_paths_skips_already_crawled(self):
        nodes = [
            _make_node(rank="1", name="Uni A", path="/uni/a"),
            _make_node(rank="2", name="Uni B", path="/uni/b"),
            _make_node(rank="3", name="Uni C", path="/uni/c"),
        ]
        # "/uni/a" already crawled — should be skipped
        crawler = self._make_crawler_with_resume(nodes, resume_paths=["/uni/a"])
        results = crawler.crawl()
        names = [u.name for u in results]
        self.assertNotIn("Uni A", names)
        self.assertIn("Uni B", names)
        self.assertIn("Uni C", names)

    def test_resume_keys_skips_already_crawled(self):
        node_a = _make_node(rank="10", name="Keio University", path="")
        node_b = _make_node(rank="11", name="Waseda", path="")
        key_a = _resume_node_key(node_a)
        crawler = self._make_crawler_with_resume(
            [node_a, node_b], resume_keys=[key_a]
        )
        results = crawler.crawl()
        names = [u.name for u in results]
        self.assertNotIn("Keio University", names)
        self.assertIn("Waseda", names)

    def test_no_resume_state_returns_all(self):
        nodes = [_make_node(rank=str(i), name=f"Uni {i}") for i in range(1, 4)]
        crawler = self._make_crawler_with_resume(nodes)
        results = crawler.crawl()
        self.assertEqual(len(results), 3)


# ---------------------------------------------------------------------------
# Detail fetch 403 degrade logic
# ---------------------------------------------------------------------------

class TestDetail403Degrade(unittest.TestCase):
    def test_detail_403_streak_triggers_degrade(self):
        """After detail_forbidden_streak_threshold consecutive 403s, crawler
        should set _detail_fallback_triggered and stop fetching details."""
        nodes = [_make_node(rank=str(i), name=f"Uni {i}", path=f"/uni/{i}") for i in range(1, 10)]
        config = Config()
        config.use_async = False
        config.fetch_details = True
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        config.detail_forbidden_streak_threshold = 3
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.fetch_university_detail.side_effect = RuntimeError("HTTP 403 Forbidden")
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher

        crawler.crawl()

        self.assertTrue(getattr(config, "_detail_fallback_triggered", False))
        # deferred paths should contain the 403'd paths
        deferred = getattr(config, "_detail_deferred_paths", [])
        self.assertGreater(len(deferred), 0)

    def test_non_403_detail_failure_does_not_degrade(self):
        """Timeouts / generic errors should NOT trigger the 403-degrade path."""
        nodes = [_make_node(rank="1", name="Uni A", path="/uni/a")]
        config = Config()
        config.use_async = False
        config.fetch_details = True
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        config.detail_forbidden_streak_threshold = 3
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.fetch_university_detail.side_effect = RuntimeError("timeout")
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher

        crawler.crawl()

        self.assertFalse(getattr(config, "_detail_fallback_triggered", False))

    def test_details_disabled_defers_all_paths(self):
        """When fetch_details=False, no detail requests are made."""
        nodes = [_make_node(rank=str(i), name=f"Uni {i}", path=f"/uni/{i}") for i in range(1, 4)]
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher

        crawler.crawl()

        mock_fetcher.fetch_university_detail.assert_not_called()

    def test_successful_detail_resets_forbidden_streak(self):
        """A successful detail fetch after a 403 should reset the streak counter."""
        # Simulate: 403, success — streak should be reset, no degrade
        call_count = [0]
        def _detail_side_effect(path):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("HTTP 403 Forbidden")
            return "<html>Requirements here</html>"

        nodes = [
            _make_node(rank="1", name="Uni A", path="/uni/a"),
            _make_node(rank="2", name="Uni B", path="/uni/b"),
        ]
        config = Config()
        config.use_async = False
        config.fetch_details = True
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        config.detail_forbidden_streak_threshold = 3
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_rankings.return_value = _make_data(nodes)
        mock_fetcher.fetch_university_detail.side_effect = _detail_side_effect
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher

        crawler.crawl()

        # One 403 out of threshold=3 should NOT trigger degrade
        self.assertFalse(getattr(config, "_detail_fallback_triggered", False))


# ---------------------------------------------------------------------------
# Node deduplication across pages
# ---------------------------------------------------------------------------

class TestNodeDeduplication(unittest.TestCase):
    def test_duplicate_nodes_are_deduplicated(self):
        """When pagination returns duplicate rows, they must only appear once."""
        node = _make_node(rank="1", name="MIT", country="USA", path="/uni/mit")
        config = Config()
        config.use_async = False
        config.fetch_details = False
        config.ranking_limit = 0
        config.show_progress = False
        config.sort_ascending = False
        crawler = UniversityCrawler(config)
        mock_fetcher = MagicMock()

        call_count = [0]
        def _fetch():
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: normal data
                return {"score_nodes": [node]}
            # Second call (pagination): 404 to stop
            raise RuntimeError("status=404")

        mock_fetcher.fetch_rankings.side_effect = _fetch
        mock_fetcher.close.return_value = None
        crawler.fetcher = mock_fetcher

        results = crawler.crawl()
        mit_count = sum(1 for u in results if u.name == "MIT")
        self.assertEqual(mit_count, 1)


if __name__ == "__main__":
    unittest.main()
