import unittest
import sys
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

if __name__ == '__main__':
    unittest.main()
