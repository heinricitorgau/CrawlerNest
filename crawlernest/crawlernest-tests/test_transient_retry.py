"""A dropped connection is retried briefly, then reported as a NetworkError -- never as a site change."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for mod in ("crawlernest-core", "crawlernest-extractors", "crawlernest-jobs"):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

import requests  # noqa: E402

import transport  # noqa: E402
from transport import NetworkError, get_with_transient_retry  # noqa: E402


class _Resp:
    def __init__(self, url="https://example.test/", text="ok", status_code=200):
        self.url, self.text, self.status_code = url, text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class _ScriptedSession:
    """get() raises or returns the next scripted item."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self):
        pass


class TestGetWithTransientRetry(unittest.TestCase):
    def setUp(self):
        self.slept: list[float] = []

    def get(self, session):
        return get_with_transient_retry(session, "https://example.test/x", sleep=self.slept.append, timeout=5)

    def test_recovers_after_two_drops(self):
        s = _ScriptedSession(requests.ConnectionError("reset"), requests.ConnectionError("reset"), _Resp())
        self.assertEqual("ok", self.get(s).text)
        self.assertEqual(3, s.calls)
        self.assertEqual([1.0, 3.0], self.slept)

    def test_raises_network_error_after_three(self):
        s = _ScriptedSession(*[requests.Timeout("slow")] * 3)
        with self.assertRaises(NetworkError) as ctx:
            self.get(s)
        self.assertEqual("network_error", ctx.exception.failure_class)
        self.assertEqual(3, s.calls)
        self.assertIn("example.test", str(ctx.exception))

    def test_http_error_is_not_retried(self):
        s = _ScriptedSession(requests.HTTPError("403"))
        with self.assertRaises(requests.HTTPError):
            self.get(s)
        self.assertEqual(1, s.calls)
        self.assertEqual([], self.slept)

    def test_non_200_response_returned_as_is(self):
        s = _ScriptedSession(_Resp(status_code=503))
        self.assertEqual(503, self.get(s).status_code)
        self.assertEqual(1, s.calls)


class TestTheReportsDropsAsNetworkErrors(unittest.TestCase):
    def test_the_connection_drop_is_network_error_not_edition_mismatch(self):
        import the_crawler

        s = _ScriptedSession(*[requests.ConnectionError("network is unreachable")] * 3)
        with mock.patch.object(transport.time, "sleep"):
            with self.assertRaises(NetworkError):
                the_crawler._load_verified_edition(2026, s)


class TestArwuReportsDropsAsNetworkErrors(unittest.TestCase):
    HTML = ('<table><tr><th>World Rank</th><th>Institution</th><th>Total Score</th></tr>'
            '<tr><td>1</td><td><a href="/institutions/harvard-university">Harvard University</a>'
            '<span>United States</span></td><td>100.0</td></tr></table>'
            '<script src="/_nuxt/static/123/rankings/arwu/2026/payload.js"></script>')

    def _crawl(self, *script):
        import arwu_crawler

        out = Path(tempfile.mkdtemp())
        existing = out / "arwu_rankings_2026.json"
        existing.write_text(json.dumps({"rows": ["the committed edition"]}), encoding="utf-8")
        session = _ScriptedSession(*script)
        with mock.patch.object(arwu_crawler, "_new_session", return_value=(session, {})), \
                mock.patch.object(arwu_crawler, "_sleep"), \
                mock.patch.object(transport.time, "sleep"):
            with self.assertRaises(NetworkError):
                arwu_crawler.crawl_arwu_rankings(2026, output_dir=out)
        return existing.read_text(encoding="utf-8")

    def test_arwu_page_drop_raises_network_error(self):
        content = self._crawl(*[requests.ConnectionError("down")] * 3)
        self.assertIn("the committed edition", content)

    def test_arwu_payload_drop_raises_network_error_and_keeps_file(self):
        page = _Resp(url="https://www.shanghairanking.com/rankings/arwu/2026", text=self.HTML)
        content = self._crawl(page, *[requests.Timeout("payload slow")] * 3)
        self.assertIn("the committed edition", content)


if __name__ == "__main__":
    unittest.main()
