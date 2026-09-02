"""Tests for the shared crawler-core primitives.

Three of these guard bugs that were live and measurable:

* ``UniversityAdmissionCrawler(rate_limit_seconds=1.0)`` produced a client with
  ``min_interval_seconds=0.0`` -- the argument was accepted and dropped, so a
  crawl of eleven university sites ran with no courtesy delay at all.
* ``HttpClient`` inherited ``retry_call``'s default of retrying every exception,
  so one HTTP 403 became three requests with sleeps between them: re-asking a
  server that had already refused.
* ``RateLimiter`` kept one clock for every host, which both allowed bursts after
  an idle period and, once requests ran concurrently, serialised unrelated sites
  behind one another.
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-crawler-core"))

from host_scheduler import (  # noqa: E402
    group_by_host,
    host_of,
    run_grouped_by_host,
)
from rate_limit import RateLimiter  # noqa: E402
from retry import retry_call  # noqa: E402


class TestRateLimiterIsPerHost(unittest.TestCase):
    def test_different_hosts_do_not_wait_for_each_other(self):
        limiter = RateLimiter(0.2)
        start = time.monotonic()
        limiter.wait("a.example.com")
        limiter.wait("b.example.com")
        limiter.wait("c.example.com")
        self.assertLess(time.monotonic() - start, 0.15)

    def test_the_same_host_does_wait(self):
        limiter = RateLimiter(0.15)
        limiter.wait("a.example.com")
        start = time.monotonic()
        limiter.wait("a.example.com")
        self.assertGreaterEqual(time.monotonic() - start, 0.12)

    def test_host_keys_are_case_insensitive(self):
        limiter = RateLimiter(0.15)
        limiter.wait("A.Example.COM")
        start = time.monotonic()
        limiter.wait("a.example.com")
        self.assertGreaterEqual(time.monotonic() - start, 0.12)

    def test_zero_interval_never_sleeps(self):
        limiter = RateLimiter(0.0)
        start = time.monotonic()
        for _ in range(50):
            limiter.wait("a.example.com")
        self.assertLess(time.monotonic() - start, 0.05)

    def test_concurrent_callers_on_one_host_are_still_spaced(self):
        """Two threads must not both decide they may go now."""
        limiter = RateLimiter(0.1)
        hits: list[float] = []
        lock = threading.Lock()

        def go():
            limiter.wait("a.example.com")
            with lock:
                hits.append(time.monotonic())

        threads = [threading.Thread(target=go) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        hits.sort()
        gaps = [hits[i] - hits[i - 1] for i in range(1, len(hits))]
        for gap in gaps:
            self.assertGreaterEqual(gap, 0.08, f"gaps={gaps}")


class TestRetryCall(unittest.TestCase):
    def test_non_retriable_wins_over_retriable(self):
        calls = []

        def boom():
            calls.append(1)
            raise HTTPError("http://x", 403, "Forbidden", {}, None)

        with self.assertRaises(HTTPError):
            retry_call(
                boom,
                attempts=3,
                delay_seconds=0.0,
                retriable_exceptions=(Exception,),
                non_retriable_exceptions=(HTTPError,),
            )
        self.assertEqual(len(calls), 1, "a refusal must not be re-sent")

    def test_retriable_still_retries(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise OSError("connection reset")
            return "ok"

        self.assertEqual(
            retry_call(flaky, attempts=3, delay_seconds=0.0, retriable_exceptions=(OSError,)),
            "ok",
        )
        self.assertEqual(len(calls), 3)

    def test_success_on_the_first_try(self):
        self.assertEqual(retry_call(lambda: 7, attempts=3, delay_seconds=0.0), 7)


class TestHostGrouping(unittest.TestCase):
    def test_host_of(self):
        self.assertEqual(host_of("https://WWW.Example.com/a?b=1"), "www.example.com")
        self.assertEqual(host_of("not a url"), "")

    def test_grouping_preserves_order_within_a_host(self):
        urls = [
            "https://a.com/1",
            "https://b.com/1",
            "https://a.com/2",
            "https://a.com/3",
        ]
        groups = group_by_host(urls, lambda u: u)
        self.assertEqual(groups["a.com"], ["https://a.com/1", "https://a.com/2", "https://a.com/3"])
        self.assertEqual(groups["b.com"], ["https://b.com/1"])

    def test_ports_do_not_split_a_host(self):
        """Politeness is owed to a server, not to a port."""
        groups = group_by_host(["https://a.com:443/x", "https://a.com:8443/y"], lambda u: u)
        self.assertEqual(list(groups), ["a.com"])


class TestRunGroupedByHost(unittest.TestCase):
    def test_results_come_back_in_input_order(self):
        urls = [f"https://h{i % 3}.com/{i}" for i in range(9)]
        out = run_grouped_by_host(urls, lambda u: u.rsplit("/", 1)[1], url_of=lambda u: u)
        self.assertEqual(out, [str(i) for i in range(9)])

    def test_one_host_runs_serially(self):
        """The invariant that keeps the crawl polite."""
        urls = [f"https://one.com/{i}" for i in range(4)]
        active = []
        peak = []
        lock = threading.Lock()

        def worker(url):
            with lock:
                active.append(url)
                peak.append(len(active))
            time.sleep(0.02)
            with lock:
                active.remove(url)
            return url

        run_grouped_by_host(urls, worker, url_of=lambda u: u)
        self.assertEqual(max(peak), 1, "two requests to one host overlapped")

    def test_different_hosts_run_concurrently(self):
        urls = [f"https://h{i}.com/x" for i in range(6)]
        start = time.monotonic()
        run_grouped_by_host(urls, lambda u: time.sleep(0.15), url_of=lambda u: u, max_workers=6)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.45, f"6 hosts x 0.15s took {elapsed:.2f}s; not concurrent")

    def test_serial_flag_forces_one_thread(self):
        urls = [f"https://h{i}.com/x" for i in range(4)]
        seen = []
        run_grouped_by_host(urls, lambda u: seen.append(u), url_of=lambda u: u, serial=True)
        self.assertEqual(seen, urls)

    def test_empty_input(self):
        self.assertEqual(run_grouped_by_host([], lambda x: x, url_of=lambda x: x), [])

    def test_an_exception_in_a_chain_is_not_swallowed(self):
        def worker(url):
            if url.endswith("boom"):
                raise ValueError("kaboom")
            return url

        with self.assertRaises(ValueError):
            run_grouped_by_host(
                ["https://a.com/ok", "https://b.com/boom"], worker, url_of=lambda u: u
            )

    def test_unparseable_urls_do_not_pretend_to_be_concurrent(self):
        """Everything in one bucket runs serially; the caller is warned."""
        items = ["not-a-url-1", "not-a-url-2", "not-a-url-3"]
        with self.assertLogs("crawlernest.host_scheduler", level="WARNING") as logs:
            out = run_grouped_by_host(items, lambda x: x, url_of=lambda x: x)
        self.assertEqual(out, items)
        self.assertIn("unparseable host", " ".join(logs.output))


class TestHttpClientAgainstALocalServer(unittest.TestCase):
    """The two bugs, at the level a caller actually hits them."""

    @classmethod
    def setUpClass(cls):
        from http.server import BaseHTTPRequestHandler, HTTPServer

        cls.hits = []
        hits = cls.hits

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append((time.monotonic(), self.path))
                if self.path.startswith("/deny"):
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"denied")
                    return
                body = b"<html><body>hello</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        self.hits.clear()

    def test_a_403_is_requested_exactly_once(self):
        from http_client import HttpClient

        client = HttpClient()
        with self.assertRaises(HTTPError):
            client.get_text(f"{self.base}/deny")
        self.assertEqual(len(self.hits), 1, "a 403 must not be retried")

    def test_the_rate_limit_is_applied_per_host(self):
        from http_client import HttpClient

        client = HttpClient(min_interval_seconds=0.15)
        start = time.monotonic()
        client.get_text(f"{self.base}/a")
        client.get_text(f"{self.base}/b")
        self.assertGreaterEqual(time.monotonic() - start, 0.12)


if __name__ == "__main__":
    unittest.main()
