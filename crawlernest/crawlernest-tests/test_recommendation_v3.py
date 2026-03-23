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
        self.elite_uk_candidates = [
            RecommendationCandidate(
                canonical_university_id=11,
                university_name="Imperial College London",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=2,
                aggregated_score=98.0,
                coverage_ratio=0.4,
                ielts_min=5.25,
                source_ranks={"QS": 2},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=12,
                university_name="University of Oxford",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=3,
                aggregated_score=97.0,
                coverage_ratio=0.4,
                ielts_min=5.5,
                source_ranks={"QS": 3},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=13,
                university_name="University of Cambridge",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=5,
                aggregated_score=96.0,
                coverage_ratio=0.4,
                ielts_min=5.5,
                source_ranks={"QS": 5},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=14,
                university_name="UCL",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=9,
                aggregated_score=94.0,
                coverage_ratio=0.4,
                ielts_min=5.25,
                source_ranks={"QS": 9},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=15,
                university_name="The University of Edinburgh",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=27,
                aggregated_score=88.0,
                coverage_ratio=0.4,
                ielts_min=None,
                source_ranks={"QS": 27},
                aggregation_method_version="rank_agg_v1",
            ),
        ]

    def test_v3_hard_country_filter_is_default(self):
        query = RecommendationQuery(
            country="United Kingdom",
            country_policy="hard_filter",
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
        self.assertNotIn("Reach Uni", by_name)
        self.assertEqual(by_name["Target Uni"]["preference_alignment"], "strong")
        self.assertEqual(payload["metadata"]["country_policy"], "hard_filter")
        self.assertEqual(payload["metadata"]["scoring_version"], "hybrid_scoring_v3")
        self.assertIsNotNone(by_name["Target Uni"]["recommendation_confidence"])
        self.assertIn("Confidence is", by_name["Target Uni"]["confidence_reason"])
        self.assertTrue(payload["target"])
        self.assertTrue(payload["safety"])
        self.assertIn("Recommended because", by_name["Target Uni"]["explanation"])

    def test_v3_soft_country_preference_remains_available_when_requested(self):
        query = RecommendationQuery(
            country="United Kingdom",
            country_policy="soft_preference",
            ielts_score=6.5,
            target_rank=100,
            risk_profile="balanced",
            limit=5,
        )
        grouped = self.recommender.recommend_grouped_v3(self.candidates, query)
        payload = grouped_recommendations_to_dict(grouped)

        all_rows = payload["reach"] + payload["target"] + payload["safety"]
        by_name = {row["university_name"]: row for row in all_rows}
        self.assertIn("Reach Uni", by_name)
        self.assertEqual(payload["metadata"]["country_policy"], "soft_preference")
        self.assertLess(
            by_name["Reach Uni"]["score_breakdown"]["country_match_score"],
            by_name["Target Uni"]["score_breakdown"]["country_match_score"],
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
        self.assertIn("aggressive profile", aggressive_reach["explanation"])
        self.assertLess(aggressive_reach["score"] - conservative_reach["score"], 6.0)

    def test_v3_balanced_populates_target_and_safety_when_supported(self):
        grouped = self.recommender.recommend_grouped_v3(
            self.elite_uk_candidates,
            RecommendationQuery(
                country="United Kingdom",
                country_policy="hard_filter",
                target_rank=100,
                ielts_score=6.5,
                risk_profile="balanced",
                limit=5,
            ),
        )
        payload = grouped_recommendations_to_dict(grouped)
        self.assertGreaterEqual(len(payload["target"]), 1)
        self.assertGreaterEqual(len(payload["safety"]), 1)
        self.assertIn("elite filtered pool", payload["target"][0]["explanation"])
        self.assertEqual(payload["safety"][0]["category"], "safety")

    def test_v3_conservative_biases_toward_safer_elite_pool_categories(self):
        grouped = self.recommender.recommend_grouped_v3(
            self.elite_uk_candidates,
            RecommendationQuery(
                country="United Kingdom",
                country_policy="hard_filter",
                target_rank=100,
                ielts_score=6.5,
                risk_profile="conservative",
                limit=10,
            ),
        )
        payload = grouped_recommendations_to_dict(grouped)
        self.assertEqual(len(payload["reach"]), 1)
        self.assertGreaterEqual(len(payload["safety"]), 2)

    def test_v3_confidence_no_longer_reclassifies_edinburgh_like_case(self):
        grouped = self.recommender.recommend_grouped_v3(
            self.elite_uk_candidates,
            RecommendationQuery(
                country="United Kingdom",
                country_policy="hard_filter",
                target_rank=10,
                ielts_score=6.5,
                risk_profile="balanced",
                limit=10,
            ),
        )
        payload = grouped_recommendations_to_dict(grouped)
        edinburgh = next(row for row in payload["safety"] if row["university_name"] == "The University of Edinburgh")
        self.assertEqual(edinburgh["category"], "safety")
        self.assertLess(edinburgh["recommendation_confidence"], 60.0)

    def test_v3_handles_empty_candidate_pool_gracefully(self):
        grouped = self.recommender.recommend_grouped_v3(
            [],
            RecommendationQuery(target_rank=100, ielts_score=6.5, risk_profile="balanced", limit=5),
        )
        payload = grouped_recommendations_to_dict(grouped)
        self.assertEqual(payload["reach"], [])
        self.assertEqual(payload["target"], [])
        self.assertEqual(payload["safety"], [])
        self.assertIn("no_results_reason", payload["metadata"])


if __name__ == "__main__":
    unittest.main()
