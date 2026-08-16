"""Tests for arwu_crawler.py utility functions (ARWU global rankings acquisition)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

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

from arwu_crawler import (  # noqa: E402
    _candidate_pages,
    _extract_rows_from_html_tables,
    _to_float,
    _to_int,
    _year_of_page,
)


class TestArwuParsingHelpers(unittest.TestCase):
    def test_to_int(self):
        self.assertEqual(_to_int("7"), 7)
        self.assertEqual(_to_int("101-150"), 101)
        self.assertIsNone(_to_int("N/A"))

    def test_to_float(self):
        self.assertAlmostEqual(_to_float("100.0"), 100.0)
        self.assertAlmostEqual(_to_float("72.3%"), 72.3)
        self.assertIsNone(_to_float(""))

    def test_candidate_pages_include_requested_year_first(self):
        pages = _candidate_pages(2026)
        self.assertEqual(pages[0], "https://www.shanghairanking.com/rankings/arwu/2026")
        self.assertIn("2025", pages[1])


class TestArwuHtmlExtraction(unittest.TestCase):
    def test_extract_rows_from_html_table(self):
        html = """
        <table>
          <tr>
            <th>World Rank</th>
            <th>Institution</th>
            <th>National/Regional Rank</th>
            <th>Total Score</th>
          </tr>
          <tr>
            <td>1</td>
            <td><a href="/institutions/harvard-university">Harvard University</a><span>United States</span></td>
            <td>1</td>
            <td>100.0</td>
          </tr>
          <tr>
            <td>6</td>
            <td><a href="/institutions/university-of-oxford">University of Oxford</a><span>United Kingdom</span></td>
            <td>2</td>
            <td>61.0</td>
          </tr>
        </table>
        """
        rows = _extract_rows_from_html_tables(html, 2025, "https://www.shanghairanking.com/rankings/arwu/2025")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Harvard University")
        self.assertEqual(rows[0]["country"], "United States")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertAlmostEqual(rows[0]["score"], 100.0)
        self.assertEqual(rows[0]["ranking_type"], "world")
        self.assertEqual(rows[1]["url"], "https://www.shanghairanking.com/institutions/university-of-oxford")

    def test_skip_rows_without_valid_rank(self):
        html = """
        <table>
          <tr>
            <th>World Rank</th>
            <th>Institution</th>
            <th>Total Score</th>
          </tr>
          <tr>
            <td>N/A</td>
            <td><a href="/institutions/example">Example University</a><span>Exampleland</span></td>
            <td>12.0</td>
          </tr>
        </table>
        """
        rows = _extract_rows_from_html_tables(html, 2025, "https://www.shanghairanking.com/rankings/arwu/2025")
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()


class TestPageYearIsRecorded(unittest.TestCase):
    """Rows must carry the year of the page they came from, not the year asked for.

    The crawler falls back two years when a table is not published yet. Stamping
    the requested year onto rows from an older page is how
    arwu_rankings_2026.json came to hold the 2025 table -- byte-identical ranks
    and scores to arwu_rankings_2025.json, from the same source_page, under a
    label that made it look like a new edition. Ingesting that would have put a
    year-old third source into the 2026 aggregation and taken those universities
    to "high" confidence on it.
    """

    def test_year_comes_from_the_url_that_was_fetched(self):
        self.assertEqual(_year_of_page("https://x/rankings/arwu/2025", 2026), 2025)
        self.assertEqual(_year_of_page("https://x/rankings/arwu/2026", 2026), 2026)

    def test_requested_year_is_the_fallback_only_when_the_url_says_nothing(self):
        self.assertEqual(_year_of_page("https://x/rankings/arwu/", 2026), 2026)
        self.assertEqual(_year_of_page("", 2024), 2024)

    def test_candidate_pages_walk_backwards(self):
        pages = _candidate_pages(2026)
        years = [int(p.rsplit("/", 1)[-1]) for p in pages]
        self.assertEqual(years, [2026, 2025, 2024],
                         "the fallback is what makes the year ambiguous; if this "
                         "order changes the year test above has to change with it")
