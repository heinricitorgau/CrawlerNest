import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from ranking_aggregation import RankingAggregator, RankingRecordInput  # noqa: E402


class RankingAggregationTest(unittest.TestCase):
    def test_display_rank_uses_weighted_normalized_composite_score(self):
        records = [
            RankingRecordInput(
                canonical_university_id=1,
                source="QS",
                year=2026,
                rank=1,
                score=20.0,
            ),
            RankingRecordInput(
                canonical_university_id=1,
                source="THE",
                year=2026,
                rank=100,
                score=20.0,
            ),
            RankingRecordInput(
                canonical_university_id=2,
                source="QS",
                year=2026,
                rank=10,
                score=95.0,
            ),
            RankingRecordInput(
                canonical_university_id=2,
                source="THE",
                year=2026,
                rank=10,
                score=95.0,
            ),
        ]

        outputs = RankingAggregator().aggregate_rankings(records)
        by_id = {row.canonical_university_id: row for row in outputs}

        # (0.222 * 1/1 + 0.654 * 1/100) / (0.222 + 0.654)
        self.assertAlmostEqual(by_id[1].composite_score or 0.0, 0.26089, places=5)
        # Both sources agree at rank 10, so renormalisation returns 1/10 whatever
        # the weights are -- this one is deliberately weight-independent.
        self.assertAlmostEqual(by_id[2].composite_score or 0.0, 0.1, places=6)
        self.assertEqual(1, by_id[1].display_rank)
        self.assertEqual(2, by_id[2].display_rank)
        self.assertEqual({"QS": 1.0, "THE": 100.0, "ARWU": None}, by_id[1].source_ranks)
        self.assertEqual({"QS": 0.222, "THE": 0.654, "ARWU": None}, by_id[1].source_weights_used)

    def test_aggregation_is_universe_isolated_and_one_row_per_university(self):
        records = [
            RankingRecordInput(
                canonical_university_id=10,
                source="QS",
                year=2026,
                universe_type="global",
                universe_key="global",
                rank=3,
            ),
            RankingRecordInput(
                canonical_university_id=10,
                source="THE",
                year=2026,
                universe_type="global",
                universe_key="global",
                rank=5,
            ),
            RankingRecordInput(
                canonical_university_id=10,
                source="QS",
                year=2026,
                universe_type="region",
                universe_key="europe",
                rank=1,
            ),
            RankingRecordInput(
                canonical_university_id=11,
                source="QS",
                year=2026,
                universe_type="region",
                universe_key="europe",
                rank=2,
            ),
        ]

        outputs = RankingAggregator().aggregate_rankings(records)

        self.assertEqual(3, len(outputs))
        by_universe = {}
        for row in outputs:
            by_universe.setdefault((row.universe_type, row.universe_key), []).append(row)

        self.assertEqual(1, len(by_universe[("global", "global")]))
        self.assertEqual(2, len(by_universe[("region", "europe")]))
        europe_rows = sorted(by_universe[("region", "europe")], key=lambda row: row.display_rank or 9999)
        self.assertEqual([1, 2], [row.display_rank for row in europe_rows])


if __name__ == "__main__":
    unittest.main()
