import unittest
import sys
import os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock, patch
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

    @patch('fetcher.requests.Session.get')
    def test_fetch_rankings_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"score_nodes": [{"uniname": "Test Uni"}]}
        mock_get.return_value = mock_response
        
        data = self.fetcher.fetch_rankings()
        self.assertIsNotNone(data)
        self.assertEqual(data["score_nodes"][0]["uniname"], "Test Uni")

if __name__ == '__main__':
    unittest.main()
