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


class TestRecommendationV3(unittest.TestCase):
    def setUp(self) -> None:
        self.recommender = RuleBasedRecommender(default_recommendation_config())
        self.candidates = [
            RecommendationCandidate(
                canonical_university_id=1,
                university_name="Reach Uni",
                country="United States",
                ranking_year=2026,
                aggregated_rank=40,
                aggregated_score=96.0,
                coverage_ratio=1.0,
                ielts_min=6.5,
                source_ranks={"QS": 38, "THE": 44, "ARWU": 41},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=2,
                university_name="Target Uni",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=95,
                aggregated_score=88.0,
                coverage_ratio=1.0,
                ielts_min=6.0,
                source_ranks={"QS": 98, "THE": 92, "ARWU": 96},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=3,
                university_name="Safety Uni",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=150,
                aggregated_score=79.0,
                coverage_ratio=0.9,
                ielts_min=6.0,
                source_ranks={"QS": 148, "THE": 152},
                aggregation_method_version="rank_agg_v1",
            ),
        ]

    def test_v3_soft_country_preference_and_alignment(self):
        query = RecommendationQuery(
            country="United Kingdom",
            ielts_score=6.5,
            target_rank=100,
            risk_profile="balanced",
            preference_weights={"ranking": 0.45, "ielts": 0.2, "confidence": 0.15, "country_match": 0.2},
            limit=5,
        )
        grouped = self.recommender.recommend_grouped_v3(self.candidates, query)
        payload = grouped_recommendations_to_dict(grouped)

        all_rows = payload["reach"] + payload["target"] + payload["safety"]
        by_name = {row["university_name"]: row for row in all_rows}
        self.assertIn("Reach Uni", by_name)
        self.assertEqual(by_name["Target Uni"]["preference_alignment"], "strong")
        self.assertEqual(payload["metadata"]["country_preference_mode"], "soft_preference")
        self.assertGreater(
            by_name["Target Uni"]["score_breakdown"]["country_match_score"],
            by_name["Reach Uni"]["score_breakdown"]["country_match_score"],
        )

    def test_v3_risk_profile_changes_scores(self):
        conservative = RecommendationQuery(target_rank=100, ielts_score=6.5, risk_profile="conservative", limit=5)
        aggressive = RecommendationQuery(target_rank=100, ielts_score=6.5, risk_profile="aggressive", limit=5)

        conservative_grouped = grouped_recommendations_to_dict(
            self.recommender.recommend_grouped_v3(self.candidates, conservative)
        )
        aggressive_grouped = grouped_recommendations_to_dict(
            self.recommender.recommend_grouped_v3(self.candidates, aggressive)
        )

        conservative_reach = conservative_grouped["reach"][0]
        aggressive_reach = aggressive_grouped["reach"][0]
        self.assertLess(conservative_reach["score"], aggressive_reach["score"])
        self.assertIn("Risk adjustment", aggressive_reach["explanation"])


if __name__ == "__main__":
    unittest.main()
