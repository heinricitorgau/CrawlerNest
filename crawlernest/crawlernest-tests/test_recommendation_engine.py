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
)


class TestRecommendationEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.recommender = RuleBasedRecommender(default_recommendation_config())
        self.candidates = [
            RecommendationCandidate(
                canonical_university_id=1,
                university_name="University of Oxford",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=3,
                aggregated_score=98.7,
                coverage_ratio=1.0,
                ielts_min=5.5,
                source_ranks={"QS": 3, "THE": 1},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=2,
                university_name="University of Birmingham",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=76,
                aggregated_score=84.2,
                coverage_ratio=0.75,
                ielts_min=6.5,
                source_ranks={"QS": 80},
                aggregation_method_version="rank_agg_v1",
            ),
            RecommendationCandidate(
                canonical_university_id=3,
                university_name="University of Toronto",
                country="Canada",
                ranking_year=2026,
                aggregated_rank=18,
                aggregated_score=94.1,
                coverage_ratio=1.0,
                ielts_min=6.5,
                source_ranks={"QS": 17},
                aggregation_method_version="rank_agg_v1",
            ),
        ]

    def test_hard_filters_country_ielts_and_rank(self):
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=10)
        results = self.recommender.recommend(self.candidates, query)
        names = [row.university_name for row in results]
        self.assertEqual(set(names), {"University of Oxford", "University of Birmingham"})
        self.assertNotIn("University of Toronto", names)

    def test_preferred_source_rank_is_used_when_available(self):
        query = RecommendationQuery(
            country="United Kingdom",
            ielts_score=6.5,
            target_rank=100,
            preferred_ranking_source="QS",
            limit=10,
        )
        results = self.recommender.recommend(self.candidates, query)
        self.assertTrue(results)
        by_name = {row.university_name: row for row in results}
        self.assertEqual(by_name["University of Oxford"].score_breakdown.effective_rank_source, "QS")
        self.assertEqual(by_name["University of Oxford"].score_breakdown.effective_rank_used, 3)

    def test_aggregated_rank_is_used_by_default(self):
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=10)
        results = self.recommender.recommend(self.candidates, query)
        self.assertTrue(results)
        by_name = {row.university_name: row for row in results}
        self.assertEqual(by_name["University of Oxford"].score_breakdown.effective_rank_source, "AGGREGATED")
        self.assertEqual(by_name["University of Oxford"].score_breakdown.effective_rank_used, 3)

    def test_explanation_and_rules_are_present(self):
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=1)
        result = self.recommender.recommend(self.candidates, query)[0]
        self.assertIn("score breakdown", result.explanation)
        self.assertTrue(result.score_breakdown.rules_passed)
        self.assertIn("country=United Kingdom", result.score_breakdown.rules_passed)


if __name__ == "__main__":
    unittest.main()
