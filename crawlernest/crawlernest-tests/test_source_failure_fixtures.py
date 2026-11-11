"""Each known way a ranking source fails, end to end and with no network: the real crawler, a recorded-shape
response, RankingSource.run, and the classification left in run_status.json.

Before this, four different THE failures -- a refusal, a changed page, an empty table and a real wrong-year page --
all read "edition_mismatch", and a refused ARWU payload read "truncated_table". The classification decides what
happens next (only network_error is rerun), so each failure is pinned here to its own.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import arwu_crawler
import the_crawler
from crawlernest_ranking_crawler.sources import ARWUCrawler, THECrawler
from crawlernest_ranking_crawler.sources.base import read_run_status
from ranking_edition import EditionMismatchError
from transport import NetworkError

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "source_failures"
THE_PAGE = "https://www.timeshighereducation.com/world-university-rankings/2026/world-ranking"


class _Response:
    def __init__(self, url, text="", status=200):
        self.url, self.text, self.status_code = url, text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}")


def _fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Run:
    """Runs a source in a temporary folder and returns (classification, status record, exception)."""

    def __init__(self, source):
        self.source = source
        self.dir = Path(tempfile.mkdtemp())

    def __call__(self, *, existing=None, year=2026):
        if existing is not None:
            path = self.dir / f"{self.source.name.lower()}_rankings_{year}.json"
            path.write_text(json.dumps(existing), encoding="utf-8")
        error = None
        try:
            self.source.run(year=year, output_dir=self.dir)
        except Exception as exc:  # the run re-raises; the status file is what is checked
            error = exc
        status_files = list((self.dir / "source_runs").rglob("run_status.json"))
        record = read_run_status(status_files[0]) if status_files else None
        return (record or {}).get("failure_classification"), record or {}, error


class TestTHEFailures(unittest.TestCase):
    def _run(self, *, answer=None, raises=None, existing=None):
        def fake_get(session, url, **kwargs):
            if raises is not None:
                raise raises
            return answer

        with mock.patch.object(the_crawler, "get_with_transient_retry", side_effect=fake_get):
            return _Run(THECrawler())(existing=existing)

    def test_the_control_page_is_ok(self):
        classification, record, error = self._run(answer=_Response(THE_PAGE, _fixture("the_2026_ok.html")))
        self.assertIsNone(error)
        self.assertEqual("", classification)
        self.assertEqual("ok", record["status"])
        self.assertEqual(3, record["standardized_count"])

    def test_a_refusal_is_blocked_not_an_edition_mismatch(self):
        for status in (403, 429):
            with self.subTest(status=status):
                classification, record, error = self._run(answer=_Response(THE_PAGE, "Access denied", status))
                self.assertEqual("blocked", classification)
                self.assertEqual("failed", record["status"])

    def test_a_server_error_is_an_http_error(self):
        classification, _, _ = self._run(answer=_Response(THE_PAGE, "oops", 500))
        self.assertEqual("http_error", classification)

    def test_another_editions_table_is_an_edition_mismatch(self):
        classification, _, _ = self._run(answer=_Response(THE_PAGE, _fixture("the_2026_serves_2025_table.html")))
        self.assertEqual("edition_mismatch", classification)

    def test_a_page_without_the_table_is_a_layout_change(self):
        classification, _, error = self._run(answer=_Response(THE_PAGE, _fixture("the_2026_layout_changed.html")))
        self.assertEqual("layout_changed", classification)
        # Still an EditionMismatchError for every caller that refuses an unverified edition.
        self.assertIsInstance(error, EditionMismatchError)

    def test_an_empty_verified_table_is_an_empty_table(self):
        classification, _, _ = self._run(answer=_Response(THE_PAGE, _fixture("the_2026_empty_table.html")))
        self.assertEqual("empty_table", classification)

    def test_no_answer_is_a_network_error(self):
        classification, _, error = self._run(raises=NetworkError("timed out after 3 attempts"))
        self.assertEqual("network_error", classification)
        self.assertIsInstance(error, NetworkError)

    def test_a_shrinking_snapshot_is_refused_and_kept(self):
        existing = {"rows": [{"id": f"x{i}", "name": f"U{i}", "rank": i + 1} for i in range(100)]}
        classification, _, _ = self._run(answer=_Response(THE_PAGE, _fixture("the_2026_ok.html")), existing=existing)
        self.assertEqual("snapshot_regression", classification)


class TestARWUFailures(unittest.TestCase):
    PAGE = "https://www.shanghairanking.com/rankings/arwu/2026"

    def _run(self, *, page, payload=None):
        page_html, page_status = page
        if payload is not None:
            page_html += '<script src="/_nuxt/static/123/rankings/arwu/2026/payload.js"></script>'

        def fake_get(session, url, **kwargs):
            if url.endswith("payload.js"):
                text, status = payload
                return _Response(url, text, status)
            return _Response(url, page_html, page_status)

        with mock.patch.object(arwu_crawler, "_new_session", return_value=(mock.MagicMock(), {})), \
                mock.patch.object(arwu_crawler, "_sleep"), \
                mock.patch.object(arwu_crawler, "get_with_transient_retry", side_effect=fake_get):
            return _Run(ARWUCrawler())()

    RENDERED = """
    <table>
      <tr><th>World Rank</th><th>Institution</th><th>Total Score</th></tr>
      <tr><td>1</td><td><a href="/institutions/alpha-university">Alpha University</a><span>United States</span></td><td>100.0</td></tr>
    </table>
    """

    def test_a_refused_page_is_blocked(self):
        classification, _, _ = self._run(page=("Forbidden", 403))
        self.assertEqual("blocked", classification)

    def test_a_refused_payload_is_blocked_not_a_truncated_table(self):
        classification, _, _ = self._run(page=(self.RENDERED, 200), payload=("Too Many Requests", 429))
        self.assertEqual("blocked", classification)

    def test_an_unreadable_payload_is_a_truncated_table(self):
        classification, _, _ = self._run(page=(self.RENDERED, 200), payload=("__NUXT_JSONP__ changed shape", 200))
        self.assertEqual("truncated_table", classification)

    def test_a_page_without_a_table_is_a_layout_change(self):
        classification, _, _ = self._run(page=(_fixture("arwu_2026_no_table.html"), 200))
        self.assertEqual("layout_changed", classification)


if __name__ == "__main__":
    unittest.main()
