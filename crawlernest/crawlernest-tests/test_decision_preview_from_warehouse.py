"""Decision-layer rows built from the warehouse's own aggregated rankings.

warehouse.ranking_decision_preview is what JdbcScopedRankingReadAdapter reads for
recommendation candidates: their per-source ranks, trust score and explain blocks
all come from this table (the scope rank comes from the aggregated view beside it).
Its only loader read warehouse.aggregated_rankings_preview, which is built from the
sample artifact and holds two demo universities -- so filling the table that way
would put MIT and Oxford into the live candidate pool as if they were the corpus.

These pin the loader that reads the real editions instead.
"""

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlernest_ranking_crawler.decision_writer import (  # noqa: E402
    WAREHOUSE_AGGREGATED_SQL,
    aggregated_rows_from_warehouse_records,
    build_decision_row,
)
from crawlernest_ranking_crawler.explain_layer import build_explain  # noqa: E402


def record(name, year, display_rank, sources, method="rank_agg_v2"):
    return (name, year, display_rank, sources, method)


class TestRowsFromTheWarehouse(unittest.TestCase):
    def test_a_row_carries_the_published_rank_and_its_source_ranks(self):
        row = aggregated_rows_from_warehouse_records(
            [record("massachusetts institute of technology", 2026, 2, {"QS": 1, "THE": 2, "ARWU": 3})]
        )[0]

        # The composite position, not a mean of source ranks: the reader falls back
        # to this for a global rank, and it is the rank shown everywhere else.
        self.assertEqual(2.0, row.aggregated_rank)
        self.assertEqual({"ARWU": 3, "QS": 1, "THE": 2}, row.sources)
        self.assertEqual(3, row.source_count)
        self.assertEqual("rank_agg_v2", row.aggregation_method)
        self.assertAlmostEqual(0.816496, row.std_deviation, places=5)

    def test_one_source_has_no_spread(self):
        self.assertEqual(0.0, aggregated_rows_from_warehouse_records(
            [record("only qs", 2026, 40, {"QS": 40})]
        )[0].std_deviation)

    def test_a_null_source_rank_is_not_a_rank(self):
        row = aggregated_rows_from_warehouse_records(
            [record("partial", 2026, 5, {"QS": 5, "THE": None, "ARWU": None})]
        )[0]
        self.assertEqual({"QS": 5}, row.sources)
        self.assertEqual(1, row.source_count)

    def test_a_university_with_no_source_rank_never_becomes_a_candidate(self):
        # The reader takes source ranks from this table; a row with none would
        # enter the pool claiming no sources at all.
        self.assertEqual([], aggregated_rows_from_warehouse_records(
            [record("nothing", 2026, 900, {"QS": None}), record("empty", 2026, 901, {})]
        ))

    def test_both_editions_are_kept_apart(self):
        rows = aggregated_rows_from_warehouse_records([
            record("same university", 2026, 2, {"QS": 1}),
            record("same university", 2025, 4, {"QS": 3}),
        ])
        self.assertEqual([(2026, 2.0), (2025, 4.0)], [(r.ranking_year, r.aggregated_rank) for r in rows])

    def test_a_repeated_name_in_one_edition_keeps_the_first_row(self):
        # The reader joins on display_name_normalized and the table is unique on
        # (name, year); ordered by rank, the first is the better-placed one.
        rows = aggregated_rows_from_warehouse_records([
            record("shared name", 2026, 10, {"QS": 10}),
            record("shared name", 2026, 900, {"QS": 900}),
        ])
        self.assertEqual([10.0], [r.aggregated_rank for r in rows])

    def test_source_names_are_upper_case_and_ordered(self):
        row = aggregated_rows_from_warehouse_records(
            [record("mixed", 2026, 3, {"the": 4, "qs": 2})]
        )[0]
        self.assertEqual(["QS", "THE"], list(row.sources))

    def test_a_row_without_a_name_or_year_is_skipped(self):
        self.assertEqual([], aggregated_rows_from_warehouse_records([
            record("", 2026, 1, {"QS": 1}),
            record("   ", 2026, 1, {"QS": 1}),
            record("no year", None, 1, {"QS": 1}),
        ]))

    def test_json_text_is_read_as_well_as_a_mapping(self):
        row = aggregated_rows_from_warehouse_records(
            [record("text json", 2026, 7, '{"QS": 7, "THE": 9}')]
        )[0]
        self.assertEqual({"QS": 7, "THE": 9}, row.sources)


class TestTheRowsFeedTheDecisionLayerUnchanged(unittest.TestCase):
    def test_a_warehouse_row_produces_the_same_shape_as_a_preview_row(self):
        row = aggregated_rows_from_warehouse_records(
            [record("imperial college london", 2026, 14, {"QS": 14, "THE": 201, "ARWU": 30})]
        )[0]
        decision = build_decision_row(row, build_explain(row))

        self.assertEqual("imperial college london", decision.normalized_university_name)
        self.assertEqual(2026, decision.ranking_year)
        self.assertEqual({"ARWU": 30, "QS": 14, "THE": 201}, decision.sources)
        self.assertEqual(3, decision.source_count)
        self.assertIn(decision.trust_level, {"high", "medium", "low"})
        self.assertGreater(decision.trust_score, 0.0)
        self.assertIn("aggregation_method", decision.aggregation_explain)
        self.assertIn("notes", decision.trust_explain)


class TestTheQueryServesOneUniverse(unittest.TestCase):
    def test_the_sql_reads_the_global_universe_of_the_aggregated_view(self):
        sql = " ".join(WAREHOUSE_AGGREGATED_SQL.split())
        self.assertIn("FROM analytics.v_aggregated_rankings_latest v", sql)
        self.assertIn("JOIN warehouse.canonical_university cu", sql)
        # The join key the reader uses.
        self.assertIn("cu.display_name_normalized", sql)
        self.assertIn("v.universe_type = %s", sql)
        self.assertIn("v.universe_key = %s", sql)
        self.assertNotIn("aggregated_rankings_preview", sql)


if __name__ == "__main__":
    unittest.main()
