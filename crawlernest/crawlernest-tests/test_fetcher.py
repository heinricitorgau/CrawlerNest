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
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-jobs"))

from fetcher import (
    _abs_url,
    _block_evidence,
    _cache_keys_sharing_ranking_id,
    _classify_block_reason,
    _classify_qs_http_response,
    _classify_transport_exception_sync,
    _extract_nid_from_html,
    _is_cf_challenge_signal,
    _jittered_request_delay_seconds,
    _qs_ranking_fetch_urls,
    _ranking_page_fallbacks,
    _read_cached_resolution,
    _record_block_observation,
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

    def test_404_behind_cloudflare_is_not_a_block(self):
        """A retired ranking id must not read as "QS blocked us".

        A genuine QS 404 proxied by Cloudflare is >= 400, carries a cf-ray and
        has an HTML body, so the old ``status_code >= 400`` rule called it a
        challenge. run_pipeline then swapped in a snapshot and labelled the run
        upstream_blocked -- hiding a dead ranking id behind a network-layer
        excuse. fetch_failed is the honest answer, and it does not trigger the
        snapshot fallback.
        """
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/rankings/api/ranking/3990755",
            404,
            "<!DOCTYPE html><html lang=\"en\"><head><title>Page not found</title></head></html>",
            {"cf-ray": "abc-KHH", "server": "cloudflare", "content-type": "text/html; charset=UTF-8"},
        )
        self.assertEqual(cls, "fetch_failed")

    def test_5xx_behind_cloudflare_is_not_a_block_either(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/rankings/api/ranking/1",
            502,
            "<html><body>Bad gateway</body></html>",
            {"cf-ray": "abc", "server": "cloudflare", "content-type": "text/html"},
        )
        self.assertEqual(cls, "fetch_failed")

    def test_maintenance_still_wins_over_the_status_rule(self):
        """upstream_maintenance is checked first and still gets the fallback."""
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/x",
            503,
            "<html>Maintenance Notice</html>",
            {"cf-ray": "abc", "content-type": "text/html"},
        )
        self.assertEqual(cls, "upstream_maintenance")

    def test_a_challenge_on_an_odd_status_is_still_caught_by_body_markers(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/x",
            503,
            "<title>Just a moment...</title>",
            {"cf-ray": "abc", "content-type": "text/html"},
        )
        self.assertEqual(cls, "upstream_blocked")

    def test_429_behind_cloudflare_is_still_a_block(self):
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/x",
            429,
            "<html>rate limited</html>",
            {"cf-ray": "abc", "content-type": "text/html"},
        )
        self.assertEqual(cls, "upstream_blocked")

    def test_bare_403_without_cf_headers_still_upstream_blocked(self):
        """The coarse label must not move when the block sub-reason is added.

        run_pipeline reads "upstream_blocked" to decide the snapshot fallback, so
        a 403 from the QS origin has to keep producing it even though
        _classify_block_reason now calls that same response origin_deny.
        """
        cls, _msg = _classify_qs_http_response(
            "https://www.topuniversities.com/rankings/api/ranking/1",
            403,
            "Forbidden",
            {"server": "nginx"},
        )
        self.assertEqual(cls, "upstream_blocked")


class TestBlockReasonClassification(unittest.TestCase):
    """The split that tells a Cloudflare block from a QS one.

    Before this existed, _is_cf_challenge_signal returned True for every 403, so
    every failure was labelled a Cloudflare challenge whether or not Cloudflare
    was involved -- which is the wrong basis for choosing between a fingerprinted
    HTTP client and a headless browser.
    """

    def test_js_interstitial_body(self):
        self.assertEqual(
            _classify_block_reason(403, "<title>Just a moment...</title>", {"cf-ray": "abc"}),
            "cf_js_challenge",
        )

    def test_challenge_platform_script_marker(self):
        self.assertEqual(
            _classify_block_reason(
                503,
                '<script src="/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"></script>',
                {"cf-ray": "abc"},
            ),
            "cf_js_challenge",
        )

    def test_cf_mitigated_header_alone(self):
        self.assertEqual(
            _classify_block_reason(403, "", {"cf-mitigated": "challenge"}),
            "cf_js_challenge",
        )

    def test_waf_deny_has_cf_headers_but_no_challenge(self):
        self.assertEqual(
            _classify_block_reason(403, "error code: 1020", {"cf-ray": "abc", "server": "cloudflare"}),
            "cf_waf_deny",
        )

    def test_origin_deny_has_no_cloudflare_anywhere(self):
        self.assertEqual(
            _classify_block_reason(403, "Forbidden", {"server": "nginx"}),
            "origin_deny",
        )

    def test_rate_limited_behind_cloudflare(self):
        self.assertEqual(
            _classify_block_reason(429, "too many requests", {"cf-ray": "abc", "retry-after": "60"}),
            "cf_rate_limited",
        )

    def test_404_is_not_a_block(self):
        self.assertEqual(_classify_block_reason(404, "not found", {"cf-ray": "abc"}), "")

    def test_500_is_not_a_block(self):
        self.assertEqual(_classify_block_reason(500, "boom", {"cf-ray": "abc"}), "")

    def test_200_is_not_a_block(self):
        self.assertEqual(_classify_block_reason(200, '{"score_nodes":[]}', {"cf-ray": "abc"}), "")

    def test_cf_challenge_signal_no_longer_fires_on_every_403(self):
        self.assertFalse(_is_cf_challenge_signal(403, "Forbidden", {"server": "nginx"}))
        self.assertTrue(_is_cf_challenge_signal(403, "Just a moment...", {"cf-ray": "abc"}))

    def test_evidence_keeps_edge_headers_and_drops_the_rest(self):
        evidence = _block_evidence(
            403,
            "Forbidden",
            {"CF-Ray": "abc-DFW", "Set-Cookie": "secret=1", "Server": "cloudflare"},
        )
        self.assertTrue(evidence["on_cloudflare"])
        self.assertEqual(evidence["headers"], {"cf-ray": "abc-DFW", "server": "cloudflare"})
        self.assertNotIn("set-cookie", evidence["headers"])
        self.assertEqual(evidence["status"], 403)


class TestBlockObservationRecording(unittest.TestCase):
    def setUp(self):
        self.config = Config()

    def test_block_is_recorded_on_the_config(self):
        reason, evidence = _record_block_observation(
            self.config, 403, "error code: 1020", {"cf-ray": "abc", "server": "cloudflare"}
        )
        self.assertEqual(reason, "cf_waf_deny")
        self.assertEqual(getattr(self.config, "_last_block_reason"), "cf_waf_deny")
        self.assertEqual(getattr(self.config, "_last_block_evidence")["status"], 403)
        self.assertIsNotNone(evidence)

    def test_success_records_nothing(self):
        reason, evidence = _record_block_observation(self.config, 200, "{}", {"cf-ray": "abc"})
        self.assertEqual(reason, "")
        self.assertIsNone(evidence)
        self.assertEqual(getattr(self.config, "_last_block_reason", ""), "")

    def test_a_later_success_clears_a_recorded_block(self):
        """Matches how _last_failure_classification already behaves."""
        from fetcher import _clear_failure_classification

        _record_block_observation(self.config, 403, "Forbidden", {"server": "nginx"})
        self.assertEqual(getattr(self.config, "_last_block_reason"), "origin_deny")
        _clear_failure_classification(self.config)
        self.assertEqual(getattr(self.config, "_last_block_reason"), "")
        self.assertEqual(getattr(self.config, "_last_block_evidence"), {})

    def test_fetcher_records_reason_through_the_sync_retry_helper(self):
        fetcher = UniversityFetcher(self.config)
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Just a moment..."
        mock_response.headers = {"cf-ray": "abc"}
        with patch.object(fetcher.session, "get", return_value=mock_response):
            fetcher._session_get_transient_retry("https://www.topuniversities.com/x")
        self.assertEqual(getattr(self.config, "_last_block_reason"), "cf_js_challenge")


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


class TestRankingIdCollision(unittest.TestCase):
    """One ranking id must not be shared by two universes.

    Every region, the global universe and all three specials were pinned to the
    same id, "3990755", by a hardcoded fallback. That id is still live and still
    answers 200 -- with WORLD ranking rows -- so an asia or europe run would have
    ingested world data under its own label without producing a single error.
    Nothing in the pipeline noticed: _payload_matches_page only inspects
    subregion wording ("northern europe", "central asia") and returns True for
    the plain regional pages.
    """

    def _entries(self):
        return {
            "QS|2026|region|asia": {"ranking_id": "3990755", "ranking_year": 2026},
            "QS|2026|region|europe": {"ranking_id": "3990755", "ranking_year": 2026},
            "QS|2026|global|global": {"ranking_id": "3990755", "ranking_year": 2026},
            "QS|2026|subject|computer-science": {"ranking_id": "4023722", "ranking_year": 2026},
        }

    def test_it_names_the_other_claimants(self):
        clashes = _cache_keys_sharing_ranking_id(
            self._entries(), key="QS|2026|region|asia", ranking_id="3990755"
        )
        self.assertEqual(clashes, ["QS|2026|global|global", "QS|2026|region|europe"])

    def test_a_unique_id_has_no_clash(self):
        clashes = _cache_keys_sharing_ranking_id(
            self._entries(), key="QS|2026|subject|computer-science", ranking_id="4023722"
        )
        self.assertEqual(clashes, [])

    def test_an_empty_id_is_not_a_clash(self):
        self.assertEqual(
            _cache_keys_sharing_ranking_id(self._entries(), key="QS|2026|region|asia", ranking_id=""),
            [],
        )

    def test_the_same_id_in_a_different_year_is_allowed(self):
        entries = {
            "QS|2025|global|global": {"ranking_id": "4153156", "ranking_year": 2025},
            "QS|2026|global|global": {"ranking_id": "4153156", "ranking_year": 2026},
        }
        self.assertEqual(
            _cache_keys_sharing_ranking_id(entries, key="QS|2026|global|global", ranking_id="4153156"),
            [],
        )


class TestPoisonedCacheIsRefused(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config.ranking_year = 2026
        self.config.universe_type = "region"
        self.config.universe_key = "asia"
        self.config.ranking_page_url = "https://www.topuniversities.com/asia-university-rankings"

    def _write(self, tmpdir, entries):
        path = Path(tmpdir) / "cache.json"
        path.write_text(json.dumps({"entries": entries}), encoding="utf-8")
        self.config.resolution_cache_path = str(path)

    def test_a_world_slice_may_share_an_id(self):
        """Every region cut from the world ranking uses the world id on purpose.

        Applying the collision check to these would reject the whole family and
        force a page resolution on every run forever.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write(
                tmpdir,
                {
                    "QS|2026|region|asia": {
                        "ranking_id": "4153156",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                    "QS|2026|region|europe": {
                        "ranking_id": "4153156",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                },
            )
            self.config.resolution_cache_ttl_seconds = 0
            self.config.ranking_scope = "world_slice"
            cached = _read_cached_resolution(self.config)
            self.assertIsNotNone(cached)
            self.assertEqual(cached["ranking_id"], "4153156")

    def test_a_shared_id_is_not_served_from_cache(self):
        """Returning None here is what sends the crawler back to page resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write(
                tmpdir,
                {
                    "QS|2026|region|asia": {
                        "ranking_id": "3990755",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                    "QS|2026|global|global": {
                        "ranking_id": "3990755",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                },
            )
            self.config.resolution_cache_ttl_seconds = 0
            self.assertIsNone(_read_cached_resolution(self.config))

    def test_an_unshared_id_is_still_served(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write(
                tmpdir,
                {
                    "QS|2026|region|asia": {
                        "ranking_id": "4085811",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                    "QS|2026|global|global": {
                        "ranking_id": "4153156",
                        "ranking_year": 2026,
                        "resolved_at": "2026-08-01T00:00:00Z",
                    },
                },
            )
            self.config.resolution_cache_ttl_seconds = 0
            cached = _read_cached_resolution(self.config)
            self.assertIsNotNone(cached)
            self.assertEqual(cached["ranking_id"], "4085811")


class TestEndpointOrder(unittest.TestCase):
    def test_the_working_endpoint_is_tried_first_by_default(self):
        """/rankings/api/ranking/{nid} answers 404 for every nid, resolved or not."""
        config = Config()
        urls = _qs_ranking_fetch_urls(config, "4085811")
        self.assertTrue(urls[0].endswith("/rankings/endpoint"), urls)
        self.assertIn("/rankings/api/ranking/4085811", urls[1])


class TestRegistryHasNoSharedRankingIds(unittest.TestCase):
    """The structural guard, at the source rather than in the cache.

    A pinned ranking_id belongs to exactly one universe. Two specs carrying the
    same one means at least one of them is pointing at another ranking's data --
    which is precisely how QS_GLOBAL and the europe spec both ended up on
    "3990755", the World 2025 id.
    """

    def test_no_two_universes_pin_the_same_ranking_id(self):
        from qs_universe_registry import iter_all_qs_universes

        seen = {}
        for spec in iter_all_qs_universes():
            rid = str(spec.ranking_id or "").strip()
            if not rid:
                continue
            owner = f"{spec.universe_type}:{spec.universe_key}"
            self.assertNotIn(
                rid,
                seen,
                f"{owner} shares ranking_id {rid} with {seen.get(rid)}",
            )
            seen[rid] = owner


class TestRankingScopeRegistry(unittest.TestCase):
    """The two products the registry now distinguishes.

    Every region:* universe has always produced the world ranking narrowed to a
    region -- the checked-in artifacts hold NUS at world rank 8 for asia, MIT at
    1 for north-america. The labels and page URLs claimed to be QS's separate
    regional publications instead, and nothing recorded which was meant. That
    ambiguity is what let one stale world id sit across eleven universes without
    looking wrong.
    """

    def _registry(self):
        import qs_universe_registry as reg

        return reg

    def test_every_world_slice_points_at_the_world_page(self):
        """Their id is the world ranking's, so the world page is where it lives.

        Four of the old per-region URLs now 404 (africa, oceania, north-america,
        latin-america). Pointing these at the world page is what keeps them
        working once ids are resolved from pages rather than hardcoded.
        """
        reg = self._registry()
        for spec in reg.QS_REGION_SPECS.values():
            self.assertTrue(spec.is_world_slice, spec.universe_key)
            self.assertEqual(spec.ranking_page_url, reg.WORLD_RANKING_PAGE, spec.universe_key)

    def test_every_world_slice_has_a_region_name(self):
        """The region name is the filter; without it the slice is the whole world."""
        for spec in self._registry().QS_REGION_SPECS.values():
            self.assertTrue(str(spec.region_name or "").strip(), spec.universe_key)

    def test_regional_rankings_each_have_their_own_page(self):
        reg = self._registry()
        pages = {}
        for spec in reg.QS_REGIONAL_SPECS.values():
            self.assertFalse(spec.is_world_slice, spec.universe_key)
            url = spec.ranking_page_url
            self.assertTrue(url, spec.universe_key)
            self.assertNotEqual(url, reg.WORLD_RANKING_PAGE, spec.universe_key)
            self.assertNotIn(url, pages, f"{spec.universe_key} shares a page with {pages.get(url)}")
            pages[url] = spec.universe_key

    def test_the_two_families_do_not_collide_on_ranking_type(self):
        """region:asia and regional:asia are different datasets and must stay so."""
        reg = self._registry()
        types = [s.ranking_type for s in reg.iter_all_qs_universes()]
        self.assertEqual(len(types), len(set(types)), "duplicate ranking_type in the registry")
        self.assertIn("region:asia", types)
        self.assertIn("regional:asia", types)

    def test_lookup_reaches_both_families(self):
        reg = self._registry()
        self.assertTrue(reg.get_qs_universe_spec("region", "asia").is_world_slice)
        self.assertFalse(reg.get_qs_universe_spec("regional", "asia").is_world_slice)

    def test_oceania_and_north_america_exist_only_as_world_slices(self):
        """QS publishes no separate ranking for either; its own index lists none."""
        reg = self._registry()
        for key in ("oceania", "north-america"):
            self.assertIn(key, reg.QS_REGION_SPECS)
            self.assertNotIn(key, reg.QS_REGIONAL_SPECS)

    def test_latin_america_is_one_slice_but_three_regional_rankings(self):
        reg = self._registry()
        self.assertIn("latin-america", reg.QS_REGION_SPECS)
        for key in ("caribbean", "central-america", "south-america"):
            self.assertIn(key, reg.QS_REGIONAL_SPECS)
        self.assertNotIn("latin-america", reg.QS_REGIONAL_SPECS)
