import datetime
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

from fetcher import (
    _abs_url,
    _classify_qs_http_response,
    _classify_transport_exception_sync,
    _extract_nid_from_html,
    _jittered_request_delay_seconds,
    _qs_ranking_fetch_urls,
    _ranking_page_fallbacks,
    UniversityFetcher,
)
import requests
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

    def test_qs_ranking_fetch_urls_respects_endpoint_order(self):
        c = Config()
        c.api_url = "https://www.topuniversities.com/rankings/endpoint"
        c.qs_endpoint_order = "api_first"
        u = _qs_ranking_fetch_urls(c, "42")
        self.assertEqual(
            u[0],
            "https://www.topuniversities.com/rankings/api/ranking/42",
        )
        c.qs_endpoint_order = "endpoint_first"
        u = _qs_ranking_fetch_urls(c, "42")
        self.assertEqual(u[0], "https://www.topuniversities.com/rankings/endpoint")

    def test_request_delay_jitter_is_bounded(self):
        c = Config()
        c.request_delay = 10.0
        c.request_delay_jitter_ratio = 0.2
        for _ in range(50):
            d = _jittered_request_delay_seconds(c)
            self.assertGreaterEqual(d, 8.0)
            self.assertLessEqual(d, 12.0)

class TestUniversityFetcher(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.ranking_id = "3990755"
        self.fetcher = UniversityFetcher(self.config)

    def test_fetch_rankings_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.text = '{"score_nodes": [{"uniname": "Test Uni"}]}'
        mock_response.json.return_value = {"score_nodes": [{"uniname": "Test Uni"}]}

        with patch.object(self.fetcher.session, "get", return_value=mock_response) as mock_get:
            data = self.fetcher.fetch_rankings()

        self.assertIsNotNone(data)
        self.assertEqual(data["score_nodes"][0]["uniname"], "Test Uni")
        self.assertGreater(mock_get.call_count, 0)

    def test_cached_resolution_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "resolution_cache.json"
            # Freshly resolved. This used to be a hardcoded 2026-03-27, which put
            # the entry outside the 30-day default TTL about a month after the
            # test was written and turned a cache hit into an HTTP fallthrough.
            resolved_at = (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
            cache_path.write_text(
                json.dumps(
                    {
                        "entries": {
                            "QS|2026|region|europe": {
                                "ranking_id": "3990755",
                                "ranking_id_candidates": ["3990755"],
                                "resolved_ranking_page_url": "https://www.topuniversities.com/europe-university-rankings",
                                "resolved_at": resolved_at,
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
            # This test is about the cache being preferred over HTTP, not about
            # expiry, so state the TTL rather than inheriting whatever the Config
            # default happens to be. TestResolutionCacheTTL covers expiry.
            self.config.resolution_cache_ttl_seconds = 3600

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
            mock_response.headers = {}
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
            mock_response.headers = {}
            with patch.object(self.fetcher.session, "get", return_value=mock_response):
                with self.assertRaises(ValueError):
                    self.fetcher._ensure_ranking_id()
            self.assertEqual(getattr(self.config, "_last_failure_classification", ""), "resolve_blocked")


class TestQsClassification(unittest.TestCase):
    def test_maintenance_body(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/x",
            503,
            "<html>Maintenance Notice — scheduled upgrade</html>",
            {},
        )
        self.assertEqual(cls, "upstream_maintenance")

    def test_cloudflare_interstitial_403(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/rankings/api/ranking/1",
            403,
            "<!DOCTYPE html><title>Just a moment...</title>",
            {"cf-ray": "abc-dead-beef"},
        )
        self.assertEqual(cls, "upstream_blocked")

    def test_generic_404_fetch_failed(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/missing",
            404,
            "not found",
            {},
        )
        self.assertEqual(cls, "fetch_failed")

    def test_live_ok_200(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/rankings/endpoint",
            200,
            '{"score_nodes":[]}',
            {"Content-Type": "application/json"},
        )
        self.assertEqual(cls, "live_ok")

    def test_network_error_timeout(self):
        cls, _msg = _classify_transport_exception_sync(requests.Timeout("slow"), "https://x")
        self.assertEqual(cls, "network_error")


class TestResolutionCacheTTL(unittest.TestCase):
    """Tests for TTL-based cache expiry in _read_cached_resolution."""

    def _write_cache(self, path: Path, ranking_id: str, resolved_at: str) -> None:
        payload = {
            "entries": {
                "QS|2026|region|europe": {
                    "ranking_id": ranking_id,
                    "ranking_id_candidates": [ranking_id],
                    "resolved_ranking_page_url": "https://www.topuniversities.com/europe-university-rankings",
                    "resolved_at": resolved_at,
                }
            }
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _make_config(self, cache_path: str, ttl: int) -> Config:
        config = Config()
        config.ranking_id = ""
        config.ranking_year = 2026
        config.universe_type = "region"
        config.universe_key = "europe"
        config.ranking_page_url = "https://www.topuniversities.com/europe-university-rankings"
        config.resolution_cache_path = cache_path
        config.resolution_cache_ttl_seconds = ttl
        return config

    def test_fresh_cache_is_used(self):
        """Cache entry within TTL should be returned without HTTP calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            now = datetime.datetime.now(datetime.timezone.utc)
            self._write_cache(cache_path, "9999", now.isoformat().replace("+00:00", "Z"))

            fetcher = UniversityFetcher(Config())
            config = self._make_config(str(cache_path), ttl=3600)  # 1 hour TTL

            with patch.object(fetcher.session, "get") as mock_get:
                nid = fetcher._ensure_ranking_id.__func__(fetcher) if False else None
                # Use the fetcher we already have but reassign config
                fetcher.config = config
                nid = fetcher._ensure_ranking_id()

            self.assertEqual(nid, "9999")
            mock_get.assert_not_called()

    def test_expired_cache_is_ignored(self):
        """Cache entry beyond TTL should be bypassed; falls through to HTML resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            # Timestamp 2 hours in the past
            old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
            self._write_cache(cache_path, "OLD_ID", old_time.isoformat().replace("+00:00", "Z"))

            config = self._make_config(str(cache_path), ttl=3600)  # 1 hour TTL
            fetcher = UniversityFetcher(Config())
            fetcher.config = config

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '<div data-nid="54321"></div>'
            mock_response.headers = {}

            with patch.object(fetcher.session, "get", return_value=mock_response) as mock_get:
                nid = fetcher._ensure_ranking_id()

            # The expired cache should have been ignored; HTML resolution fires
            self.assertEqual(nid, "54321")
            mock_get.assert_called()

    def test_zero_ttl_always_uses_cache(self):
        """TTL=0 means no expiry check — any cache entry should be accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            # Entry written a long time ago
            ancient = "2000-01-01T00:00:00Z"
            self._write_cache(cache_path, "ANCIENT_ID", ancient)

            config = self._make_config(str(cache_path), ttl=0)
            fetcher = UniversityFetcher(Config())
            fetcher.config = config

            with patch.object(fetcher.session, "get") as mock_get:
                nid = fetcher._ensure_ranking_id()

            self.assertEqual(nid, "ANCIENT_ID")
            mock_get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
