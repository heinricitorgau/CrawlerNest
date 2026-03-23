import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from comparison import compare_universities  # noqa: E402
from recommendation_engine import RecommendationCandidate  # noqa: E402


class TestComparisonEngine(unittest.TestCase):
    def test_comparison_prefers_better_aggregated_rank(self):
        oxford = RecommendationCandidate(
            canonical_university_id=1,
            university_name="Oxford",
            country="United Kingdom",
            ranking_year=2026,
            aggregated_rank=3,
            aggregated_score=98.5,
            coverage_ratio=1.0,
            ielts_min=5.5,
            source_ranks={"QS": 2, "THE": 1, "ARWU": 7},
            aggregation_method_version="rank_agg_v1",
        )
        lse = RecommendationCandidate(
            canonical_university_id=2,
            university_name="LSE",
            country="United Kingdom",
            ranking_year=2026,
            aggregated_rank=52,
            aggregated_score=87.4,
            coverage_ratio=1.0,
            ielts_min=5.5,
            source_ranks={"QS": 45, "THE": 50, "ARWU": 151},
            aggregation_method_version="rank_agg_v1",
        )

        result = compare_universities([oxford, lse])

        self.assertEqual(result["better"], "Oxford")
        self.assertEqual(result["comparison"]["ranking"]["winner"], "Oxford")
        self.assertIn("aggregated ranking advantage", result["comparison"]["ranking"]["explanation"])
        self.assertEqual(result["comparison"]["ielts"]["winner"], "Tie")

    def test_comparison_uses_completeness_when_ranking_is_tied(self):
        a = RecommendationCandidate(
            canonical_university_id=1,
            university_name="A University",
            country="United Kingdom",
            ranking_year=2026,
            aggregated_rank=10,
            aggregated_score=95.0,
            coverage_ratio=1.0,
            ielts_min=6.0,
            source_ranks={"QS": 10, "THE": 11, "ARWU": 15},
            aggregation_method_version="rank_agg_v1",
        )
        b = RecommendationCandidate(
            canonical_university_id=2,
            university_name="B University",
            country="United Kingdom",
            ranking_year=2026,
            aggregated_rank=10,
            aggregated_score=95.0,
            coverage_ratio=0.33,
            ielts_min=None,
            source_ranks={"QS": 10},
            aggregation_method_version="rank_agg_v1",
        )

        result = compare_universities([a, b])

        self.assertEqual(result["better"], "A University")
        self.assertEqual(result["comparison"]["ranking"]["winner"], "Tie")
        self.assertEqual(result["comparison"]["data_completeness"]["winner"], "A University")


if __name__ == "__main__":
    unittest.main()
