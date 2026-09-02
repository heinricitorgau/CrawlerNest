"""Tests for HTTP backend selection and the header policy that goes with it.

The header policy is the part worth guarding. Config.get_headers() builds a
browser-looking set -- User-Agent, Accept-Encoding, Connection, Cache-Control,
Pragma, Origin, Sec-Fetch-* -- to make `requests` pass for a browser. Measured
against topuniversities.com, sending that same set through curl_cffi's
impersonated stack brings the Cloudflare challenge straight back (403), while
sending only the semantic subset returns 200. No individual header trips it; the
combination does, because Chrome's header order is part of what is matched.

So this is a case where adding "more browser-like" headers makes things worse,
and a future edit that widens SEMANTIC_HEADERS or drops the filter would silently
re-break the ranking feed. These tests exist to make that loud.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-extractors"))

import transport  # noqa: E402
from config import Config  # noqa: E402
from transport import (  # noqa: E402
    BACKEND_CURL_CFFI,
    BACKEND_REQUESTS,
    SEMANTIC_HEADERS,
    TransportChoice,
    _translate_kwargs,
    request_headers,
    resolve_backend,
)

CURL = TransportChoice(BACKEND_CURL_CFFI, "chrome124", "test")
PLAIN = TransportChoice(BACKEND_REQUESTS, "chrome124", "test")


def _no_env():
    """resolve_backend reads the environment; tests must not inherit the caller's."""
    return patch.dict(os.environ, {"CRAWLERNEST_HTTP_BACKEND": "", "CRAWLERNEST_HTTP_IMPERSONATE": ""}, clear=False)


class TestBackendSelection(unittest.TestCase):
    def test_explicit_requests(self):
        with _no_env():
            choice = resolve_backend(Config(http_backend="requests"))
        self.assertEqual(choice.backend, BACKEND_REQUESTS)
        self.assertFalse(choice.is_fingerprinted)

    def test_auto_prefers_curl_cffi_when_available(self):
        with _no_env(), patch.object(transport, "CURL_CFFI_AVAILABLE", True):
            choice = resolve_backend(Config())
        self.assertEqual(choice.backend, BACKEND_CURL_CFFI)
        self.assertTrue(choice.is_fingerprinted)

    def test_auto_falls_back_and_says_why(self):
        with _no_env(), patch.object(transport, "CURL_CFFI_AVAILABLE", False):
            choice = resolve_backend(Config())
        self.assertEqual(choice.backend, BACKEND_REQUESTS)
        self.assertIn("Cloudflare", choice.reason)

    def test_explicit_curl_cffi_without_the_dependency_raises(self):
        """Downgrading silently would leave the operator debugging the wrong thing."""
        with _no_env(), patch.object(transport, "CURL_CFFI_AVAILABLE", False):
            with self.assertRaises(RuntimeError) as ctx:
                resolve_backend(Config(http_backend="curl_cffi"))
        self.assertIn("not installed", str(ctx.exception))

    def test_unknown_backend_raises(self):
        with _no_env():
            with self.assertRaises(ValueError):
                resolve_backend(Config(http_backend="playwright"))

    def test_env_var_is_read_when_config_is_silent(self):
        with patch.dict(os.environ, {"CRAWLERNEST_HTTP_BACKEND": "requests"}):
            self.assertEqual(resolve_backend(Config()).backend, BACKEND_REQUESTS)

    def test_config_beats_the_env_var(self):
        with patch.dict(os.environ, {"CRAWLERNEST_HTTP_BACKEND": "curl_cffi"}):
            self.assertEqual(resolve_backend(Config(http_backend="requests")).backend, BACKEND_REQUESTS)


class TestRequestHeaderPolicy(unittest.TestCase):
    def setUp(self):
        self.config = Config(ranking_page_url="https://www.topuniversities.com/asia-university-rankings")

    def test_plain_backend_gets_the_full_hand_built_set(self):
        full = self.config.get_headers("page")
        self.assertEqual(request_headers(PLAIN, full), dict(full))
        self.assertIn("User-Agent", request_headers(PLAIN, full))

    def test_fingerprinted_backend_drops_the_profile_owned_headers(self):
        """These are exactly the headers that produced a 403 when sent together."""
        sent = request_headers(CURL, self.config.get_headers("page"))
        for name in (
            "User-Agent",
            "Accept-Encoding",
            "Accept-Language",
            "Connection",
            "Cache-Control",
            "Pragma",
            "Origin",
            "Upgrade-Insecure-Requests",
            "Sec-Fetch-Dest",
            "Sec-Fetch-Mode",
            "Sec-Fetch-Site",
        ):
            self.assertNotIn(name, sent, f"{name} must not be forwarded to an impersonated stack")

    def test_fingerprinted_backend_keeps_the_semantic_ones(self):
        sent = request_headers(CURL, self.config.get_headers("api"))
        self.assertEqual(sent.get("Accept"), "application/json, text/plain, */*")
        self.assertEqual(sent.get("Referer"), self.config.ranking_page_url)
        self.assertEqual(sent.get("X-Requested-With"), "XMLHttpRequest")

    def test_the_allowlist_stays_small(self):
        """A widened allowlist is how this regresses; make the change deliberate."""
        self.assertEqual(SEMANTIC_HEADERS, frozenset({"accept", "referer", "x-requested-with"}))

    def test_filtering_is_case_insensitive(self):
        sent = request_headers(CURL, {"USER-AGENT": "x", "referer": "https://example.com"})
        self.assertNotIn("USER-AGENT", sent)
        self.assertEqual(sent.get("referer"), "https://example.com")

    def test_empty_headers(self):
        self.assertEqual(request_headers(CURL, None), {})
        self.assertEqual(request_headers(PLAIN, {}), {})


class TestAiohttpKwargTranslation(unittest.TestCase):
    """curl_cffi does not speak aiohttp's connector vocabulary."""

    def test_ssl_is_dropped(self):
        self.assertNotIn("ssl", _translate_kwargs({"ssl": object(), "headers": {}}))

    def test_client_timeout_becomes_a_number(self):
        class FakeClientTimeout:
            total = 42.0

        out = _translate_kwargs({"timeout": FakeClientTimeout()})
        self.assertEqual(out["timeout"], 42.0)

    def test_a_plain_number_timeout_survives(self):
        self.assertEqual(_translate_kwargs({"timeout": 15})["timeout"], 15)

    def test_empty_params_are_dropped(self):
        self.assertNotIn("params", _translate_kwargs({"params": {}}))

    def test_real_params_survive(self):
        self.assertEqual(_translate_kwargs({"params": {"nid": "1"}})["params"], {"nid": "1"})


class TestAiohttpShapedResponse(unittest.TestCase):
    """The adapter the async fetcher's call sites depend on."""

    class _FakeCurlResponse:
        status_code = 403
        headers = {"cf-ray": "abc"}
        text = "Just a moment..."

        def json(self):
            return {"ok": True}

        def raise_for_status(self):
            raise RuntimeError("boom")

    def test_it_presents_aiohttp_names(self):
        async def run():
            wrapped = transport._AiohttpShapedResponse(self._FakeCurlResponse())
            self.assertEqual(wrapped.status, 403)
            self.assertEqual(wrapped.status_code, 403)
            self.assertEqual(wrapped.headers["cf-ray"], "abc")
            self.assertEqual(await wrapped.text(), "Just a moment...")
            self.assertEqual(wrapped.json(), {"ok": True})
            with self.assertRaises(RuntimeError):
                wrapped.raise_for_status()

        asyncio.run(run())

    def test_it_works_as_an_async_context_manager(self):
        """`async with session.get(...) as resp` is how every call site is written."""
        fake = self._FakeCurlResponse()

        async def coro():
            return fake

        async def run():
            async with transport._AiohttpShapedRequest(coro()) as resp:
                self.assertEqual(resp.status, 403)
                self.assertEqual(await resp.text(), "Just a moment...")

        asyncio.run(run())

    def test_it_can_also_simply_be_awaited(self):
        fake = self._FakeCurlResponse()

        async def coro():
            return fake

        async def run():
            resp = await transport._AiohttpShapedRequest(coro())
            self.assertEqual(resp.status, 403)

        asyncio.run(run())


class TestUnifiedExceptionSets(unittest.TestCase):
    def test_requests_hierarchy_is_always_present(self):
        import requests

        self.assertIn(requests.Timeout, transport.TIMEOUT_ERRORS)
        self.assertIn(requests.ConnectionError, transport.CONNECTION_ERRORS)
        self.assertIn(requests.RequestException, transport.REQUEST_ERRORS)

    def test_transient_covers_timeouts_and_connection_errors(self):
        for exc in transport.TIMEOUT_ERRORS + transport.CONNECTION_ERRORS:
            self.assertIn(exc, transport.TRANSIENT_ERRORS)

    def test_curl_cffi_hierarchy_is_included_when_installed(self):
        if not transport.CURL_CFFI_AVAILABLE:
            self.skipTest("curl_cffi not installed in this interpreter")
        from curl_cffi.requests import exceptions as ce

        self.assertIn(ce.Timeout, transport.TIMEOUT_ERRORS)
        self.assertIn(ce.ConnectionError, transport.CONNECTION_ERRORS)
        self.assertIn(ce.RequestException, transport.REQUEST_ERRORS)


if __name__ == "__main__":
    unittest.main()
