"""Tests for the_crawler.py utility functions (THE rankings Layer 1 data acquisition).

Covers:
- _to_int()                       : rank/score parsing
- _to_float()                     : score parsing with % stripping
- _pick_first()                   : first-non-None-value picker
- _extract_rows()                 : payload → row list extraction
- _normalize_row()                : raw THE row → normalised dict
- _discover_data_urls()           : HTML → JSON URL discovery
- _extract_rows_from_next_data()  : __NEXT_DATA__ script extraction
- _extract_rows_from_html_tables(): HTML table extraction fallback
"""
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

from the_crawler import (
    _to_int,
    _to_float,
    _pick_first,
    _extract_rows,
    _normalize_row,
    extract_the_ranking_record,
    _discover_data_urls,
    _extract_rows_from_next_data,
    _extract_rows_from_html_tables,
    BASE_URL,
)


# ---------------------------------------------------------------------------
# _to_int
# ---------------------------------------------------------------------------

class TestToInt(unittest.TestCase):
    def test_plain_integer(self):
        self.assertEqual(_to_int(1), 1)
        self.assertEqual(_to_int("42"), 42)

    def test_rank_range_extracts_first_number(self):
        # "51-100" → 51
        self.assertEqual(_to_int("51-100"), 51)
        self.assertEqual(_to_int("201–250"), 201)

    def test_equals_prefix(self):
        self.assertEqual(_to_int("=3"), 3)

    def test_none_and_empty(self):
        self.assertIsNone(_to_int(None))
        self.assertIsNone(_to_int(""))
        self.assertIsNone(_to_int("N/A"))

    def test_float_string(self):
        self.assertEqual(_to_int("7.5"), 7)


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------

class TestToFloat(unittest.TestCase):
    def test_plain_float(self):
        self.assertAlmostEqual(_to_float("85.5"), 85.5)

    def test_percent_stripped(self):
        self.assertAlmostEqual(_to_float("72.3%"), 72.3)

    def test_integer_string(self):
        self.assertAlmostEqual(_to_float("90"), 90.0)

    def test_none_and_empty(self):
        self.assertIsNone(_to_float(None))
        self.assertIsNone(_to_float(""))
        self.assertIsNone(_to_float("N/A"))


# ---------------------------------------------------------------------------
# _pick_first
# ---------------------------------------------------------------------------

class TestPickFirst(unittest.TestCase):
    def test_returns_first_non_none(self):
        row = {"a": None, "b": "", "c": "value"}
        self.assertEqual(_pick_first(row, "a", "b", "c"), "value")

    def test_first_key_wins(self):
        row = {"a": "first", "b": "second"}
        self.assertEqual(_pick_first(row, "a", "b"), "first")

    def test_missing_key_returns_none(self):
        row = {"x": "data"}
        self.assertIsNone(_pick_first(row, "a", "b"))

    def test_empty_row(self):
        self.assertIsNone(_pick_first({}, "a"))

    def test_zero_is_truthy_value(self):
        # 0 is a valid rank – should NOT be skipped
        row = {"rank": 0}
        result = _pick_first(row, "rank")
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# _extract_rows
# ---------------------------------------------------------------------------

class TestExtractRows(unittest.TestCase):
    def test_rows_key(self):
        payload = {"rows": [{"rank": 1, "name": "MIT"}, {"rank": 2, "name": "Stanford"}]}
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "MIT")

    def test_data_key(self):
        payload = {"data": [{"rank": 1, "name": "Oxford"}]}
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 1)

    def test_results_key(self):
        payload = {"results": [{"rank": 1, "name": "Cambridge"}]}
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 1)

    def test_list_payload(self):
        payload = [{"rank": 1, "name": "Caltech"}, {"rank": 2, "name": "ETH"}]
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 2)

    def test_non_dict_items_filtered(self):
        payload = {"rows": [{"rank": 1, "name": "MIT"}, "bad", None, 42]}
        rows = _extract_rows(payload)
        self.assertEqual(len(rows), 1)

    def test_none_payload_returns_empty(self):
        self.assertEqual(_extract_rows(None), [])

    def test_empty_list_returns_empty(self):
        self.assertEqual(_extract_rows([]), [])


# ---------------------------------------------------------------------------
# _normalize_row
# ---------------------------------------------------------------------------

class TestNormalizeRow(unittest.TestCase):
    def _valid_row(self, **overrides):
        base = {"name": "Test University", "rank": 5, "country": "UK", "score": 80.5}
        base.update(overrides)
        return base

    def test_valid_row_returns_dict(self):
        result = _normalize_row(self._valid_row(), 2026)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Test University")
        self.assertEqual(result["rank"], 5)
        self.assertEqual(result["country"], "UK")
        self.assertAlmostEqual(result["score"], 80.5)
        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["ranking_type"], "world")

    def test_missing_name_returns_none(self):
        row = {"rank": 1, "country": "UK"}
        self.assertIsNone(_normalize_row(row, 2026))

    def test_unparseable_rank_returns_none(self):
        row = {"name": "Some University", "rank": "N/A", "country": "UK"}
        self.assertIsNone(_normalize_row(row, 2026))

    def test_alternate_field_names(self):
        row = {
            "university_name": "Imperial College",
            "rank_order": 10,
            "location": "UK",
            "overall_score": 75.0,
        }
        result = _normalize_row(row, 2026)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Imperial College")
        self.assertEqual(result["rank"], 10)

    def test_score_in_nested_scores_dict(self):
        row = {
            "name": "TU Berlin",
            "rank": 200,
            "scores": {"overall": "65.3"},
        }
        result = _normalize_row(row, 2026)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["score"], 65.3)

    def test_rank_range_string_is_accepted(self):
        row = {"name": "Some Uni", "rank": "51-100", "country": "Germany"}
        result = _normalize_row(row, 2026)
        self.assertIsNotNone(result)
        self.assertEqual(result["rank"], 51)

    def test_metadata_contains_raw_source(self):
        result = _normalize_row(self._valid_row(), 2026)
        self.assertIsNotNone(result)
        self.assertEqual(result["metadata"]["raw_source"], "THE")


# ---------------------------------------------------------------------------
# extract_the_ranking_record
# ---------------------------------------------------------------------------

class TestExtractTheRankingRecord(unittest.TestCase):
    def test_maps_normalized_row(self):
        norm = _normalize_row(
            {"name": "Oxford", "rank": 1, "country": "United Kingdom", "score": 98.2},
            2026,
        )
        self.assertIsNotNone(norm)
        rec = extract_the_ranking_record(norm)  # type: ignore[arg-type]
        self.assertEqual(rec["university_name"], "Oxford")
        self.assertEqual(rec["country"], "United Kingdom")
        self.assertEqual(rec["rank"], 1)
        self.assertAlmostEqual(rec["score"], 98.2)
        self.assertEqual(rec["source"], "THE")
        self.assertEqual(rec["ranking_year"], 2026)

    def test_empty_country_becomes_blank(self):
        norm = _normalize_row({"name": "MIT", "rank": 2}, 2026)
        self.assertIsNotNone(norm)
        rec = extract_the_ranking_record(norm)  # type: ignore[arg-type]
        self.assertEqual(rec["country"], "")


# ---------------------------------------------------------------------------
# _discover_data_urls
# ---------------------------------------------------------------------------

class TestDiscoverDataUrls(unittest.TestCase):
    def test_discovers_direct_year_url(self):
        html = (
            '<script>var u="https://www.timeshighereducation.com/sites/default/files'
            '/the_data_rankings/world_university_rankings_2026_0.json";</script>'
        )
        urls = _discover_data_urls(html, 2026)
        self.assertTrue(any("2026" in u for u in urls), f"Expected 2026 url in {urls}")

    def test_discovers_generic_json_url(self):
        html = (
            '<link rel="preload" href="https://www.timeshighereducation.com/sites/default/files'
            '/the_data_rankings/world_university_rankings_2025.json">'
        )
        urls = _discover_data_urls(html, 2026)
        self.assertTrue(any("the_data_rankings" in u for u in urls), f"Expected data url in {urls}")

    def test_deduplicates_urls(self):
        snippet = (
            '"https://www.timeshighereducation.com/sites/default/files'
            '/the_data_rankings/world_university_rankings_2026.json"'
        )
        html = snippet + " " + snippet
        urls = _discover_data_urls(html, 2026)
        self.assertEqual(len(urls), len(set(urls)))

    def test_empty_html_returns_empty(self):
        self.assertEqual(_discover_data_urls("", 2026), [])

    def test_no_matching_urls_returns_empty(self):
        self.assertEqual(_discover_data_urls("<html>no data here</html>", 2026), [])


# ---------------------------------------------------------------------------
# _extract_rows_from_next_data
# ---------------------------------------------------------------------------

class TestExtractRowsFromNextData(unittest.TestCase):
    def _build_html(self, rows):
        payload = {
            "props": {
                "pageProps": {
                    "page": {
                        "rankingsTableConfig": {
                            "rankingsData": {
                                "data": rows
                            }
                        }
                    }
                }
            }
        }
        return (
            f'<script id="__NEXT_DATA__" type="application/json">'
            f'{json.dumps(payload)}'
            f'</script>'
        )

    def test_extracts_rows_from_valid_structure(self):
        rows = [{"name": "MIT", "rank": 1}, {"name": "Stanford", "rank": 2}]
        html = self._build_html(rows)
        result = _extract_rows_from_next_data(html)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "MIT")

    def test_filters_non_dict_items(self):
        rows = [{"name": "MIT", "rank": 1}, "not a dict", None]
        html = self._build_html(rows)
        result = _extract_rows_from_next_data(html)
        self.assertEqual(len(result), 1)

    def test_no_script_tag_returns_empty(self):
        self.assertEqual(_extract_rows_from_next_data("<html>plain page</html>"), [])

    def test_invalid_json_returns_empty(self):
        html = '<script id="__NEXT_DATA__" type="application/json">not json</script>'
        self.assertEqual(_extract_rows_from_next_data(html), [])

    def test_missing_nested_key_returns_empty(self):
        payload = {"props": {"pageProps": {}}}
        html = (
            f'<script id="__NEXT_DATA__" type="application/json">'
            f'{json.dumps(payload)}'
            f'</script>'
        )
        self.assertEqual(_extract_rows_from_next_data(html), [])


# ---------------------------------------------------------------------------
# _extract_rows_from_html_tables
# ---------------------------------------------------------------------------

class TestExtractRowsFromHtmlTables(unittest.TestCase):
    def _make_table(self, rows: list[list[str]]) -> str:
        header = rows[0]
        data_rows = rows[1:]
        th_cells = "".join(f"<th>{c}</th>" for c in header)
        tr_rows = "\n".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in data_rows
        )
        return f"<table><tr>{th_cells}</tr>{tr_rows}</table>"

    def test_extracts_ranking_table(self):
        table_html = self._make_table([
            ["Rank", "Institution", "Country"],
            ["1", "MIT", "United States"],
            ["2", "Stanford", "United States"],
        ])
        rows = _extract_rows_from_html_tables(table_html, 2026, "https://example.com/rankings")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "MIT")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["country"], "United States")

    def test_table_without_required_columns_is_skipped(self):
        table_html = self._make_table([
            ["Subject", "Score"],
            ["Physics", "A"],
        ])
        rows = _extract_rows_from_html_tables(table_html, 2026, "https://example.com")
        self.assertEqual(rows, [])

    def test_skips_rows_with_unparseable_rank(self):
        table_html = self._make_table([
            ["Rank", "Institution", "Country"],
            ["N/A", "Unknown Uni", "UK"],
            ["5", "Valid Uni", "Germany"],
        ])
        rows = _extract_rows_from_html_tables(table_html, 2026, "https://example.com")
        valid = [r for r in rows if r["name"] == "Valid Uni"]
        self.assertEqual(len(valid), 1)
        invalid = [r for r in rows if r["name"] == "Unknown Uni"]
        self.assertEqual(len(invalid), 0)

    def test_empty_html_returns_empty(self):
        self.assertEqual(_extract_rows_from_html_tables("", 2026, "https://example.com"), [])

    def test_year_and_ranking_type_populated(self):
        table_html = self._make_table([
            ["Rank", "University", "Country"],
            ["1", "Oxford", "UK"],
        ])
        rows = _extract_rows_from_html_tables(table_html, 2025, "https://example.com")
        self.assertEqual(rows[0]["year"], 2025)
        self.assertEqual(rows[0]["ranking_type"], "world")


if __name__ == "__main__":
    unittest.main()
