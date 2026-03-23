import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from recommendation_engine import (  # noqa: E402
    RecommendationCandidate,
    RecommendationQuery,
    RuleBasedRecommender,
    default_recommendation_config,
    grouped_recommendations_to_dict,
)


class TestRecommendationV2(unittest.TestCase):
    def setUp(self) -> None:
        self.recommender = RuleBasedRecommender(default_recommendation_config())
        self.candidates = [
            RecommendationCandidate(
                canonical_university_id=1,
                university_name="Reach Uni",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=45,
                aggregated_score=95.0,
                coverage_ratio=1.0,
                ielts_min=6.5,
                source_ranks={"QS": 40, "THE": 50, "ARWU": 55},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=2,
                university_name="Target Uni",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=92,
                aggregated_score=88.0,
                coverage_ratio=1.0,
                ielts_min=6.0,
                source_ranks={"QS": 95, "THE": 90, "ARWU": 93},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=3,
                university_name="Safety Uni",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=145,
                aggregated_score=77.0,
                coverage_ratio=0.8,
                ielts_min=6.0,
                source_ranks={"QS": 150, "THE": 140},
                aggregation_method_version="rank_agg_v1",
            ),
        ]

    def test_grouped_recommendations_assign_categories(self):
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, risk_profile="balanced", limit=5)
        grouped = self.recommender.recommend_grouped(self.candidates, query)
        payload = grouped_recommendations_to_dict(grouped)

        self.assertEqual(payload["reach"][0]["category"], "reach")
        self.assertEqual(payload["target"][0]["category"], "target")
        self.assertEqual(payload["safety"][0]["category"], "safety")
        self.assertIn("Classified as Target", payload["target"][0]["explanation"])


if __name__ == "__main__":
    unittest.main()
