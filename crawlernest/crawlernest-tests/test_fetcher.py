import unittest
import sys
import json
import tempfile
from pathlib import Path

from unittest.mock import MagicMock, patch

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-extractors"))

from fetcher import _abs_url, _extract_nid_from_html, _ranking_page_fallbacks, UniversityFetcher
from config import Config

class TestFetcherUtils(unittest.TestCase):
    def test_abs_url(self):
        base = "https://example.com"
        self.assertEqual(_abs_url(base, "/path"), "https://example.com/path")
        self.assertEqual(_abs_url(base, "path"), "https://example.com/path")
        self.assertEqual(_abs_url(base, "http://other.com"), "http://other.com")

    def test_extract_nid_from_html(self):
        html = '<div data-nid="12345"></div>'
        self.assertEqual(_extract_nid_from_html(html), "12345")
        
        html_json = '{"nid": "67890"}'
        self.assertEqual(_extract_nid_from_html(html_json), "67890")
        
        html_api = 'fetch("/rankings/api/ranking/11111")'
        self.assertEqual(_extract_nid_from_html(html_api), "11111")

    def test_ranking_page_fallbacks(self):
        url = "https://www.topuniversities.com/asia-university-rankings/south-eastern-asia"
        fallbacks = _ranking_page_fallbacks(url)
        self.assertIn("https://www.topuniversities.com/asia-university-rankings", fallbacks)

class TestUniversityFetcher(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.ranking_id = "3990755"
        self.fetcher = UniversityFetcher(self.config)

    def test_fetch_rankings_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"score_nodes": [{"uniname": "Test Uni"}]}

        with patch.object(self.fetcher.session, "get", return_value=mock_response) as mock_get:
            data = self.fetcher.fetch_rankings()

        self.assertIsNotNone(data)
        self.assertEqual(data["score_nodes"][0]["uniname"], "Test Uni")
        self.assertGreater(mock_get.call_count, 0)

    def test_cached_resolution_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "resolution_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "QS|2026|region|europe": {
                                "ranking_id": "3990755",
                                "ranking_id_candidates": ["3990755"],
                                "resolved_ranking_page_url": "https://www.topuniversities.com/europe-university-rankings",
                                "resolved_at": "2026-03-27T00:00:00Z",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.config.ranking_id = ""
            self.config.ranking_year = 2026
            self.config.universe_type = "region"
            self.config.universe_key = "europe"
            self.config.ranking_page_url = "https://www.topuniversities.com/europe-university-rankings"
            self.config.resolution_cache_path = str(cache_path)

            with patch.object(self.fetcher.session, "get") as mock_get:
                nid = self.fetcher._ensure_ranking_id()

            self.assertEqual(nid, "3990755")
            self.assertEqual(self.config.ranking_id, "3990755")
            self.assertTrue(getattr(self.config, "_used_resolution_cache", False))
            mock_get.assert_not_called()

    def test_direct_ranking_id_beats_cache_and_html(self):
        self.config.ranking_id = "3990755"
        self.config.ranking_page_url = "https://www.topuniversities.com/europe-university-rankings"
        with patch.object(self.fetcher.session, "get") as mock_get:
            nid = self.fetcher._ensure_ranking_id()
        self.assertEqual(nid, "3990755")
        mock_get.assert_not_called()

    def test_html_resolution_is_last_resort(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.config.ranking_id = ""
            self.config.ranking_year = 2026
            self.config.universe_type = "region"
            self.config.universe_key = "europe"
            self.config.ranking_page_url = "https://www.topuniversities.com/europe-university-rankings"
            self.config.resolution_cache_path = str(Path(tmpdir) / "resolution_cache.json")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '<div data-nid="12345"></div>'
            with patch.object(self.fetcher.session, "get", return_value=mock_response) as mock_get:
                nid = self.fetcher._ensure_ranking_id()
            self.assertEqual(nid, "12345")
            self.assertEqual(mock_get.call_count, 1)

    def test_resolve_blocked_classification_is_stable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.config.ranking_id = ""
            self.config.ranking_year = 2026
            self.config.universe_type = "region"
            self.config.universe_key = "europe"
            self.config.ranking_page_url = "https://www.topuniversities.com/europe-university-rankings"
            self.config.resolution_cache_path = str(Path(tmpdir) / "resolution_cache.json")
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "Just a moment..."
            with patch.object(self.fetcher.session, "get", return_value=mock_response):
                with self.assertRaises(ValueError):
                    self.fetcher._ensure_ranking_id()
            self.assertEqual(getattr(self.config, "_last_failure_classification", ""), "resolve_blocked")

if __name__ == '__main__':
    unittest.main()
