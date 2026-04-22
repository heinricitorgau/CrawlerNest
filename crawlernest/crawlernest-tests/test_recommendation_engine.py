import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
if str(REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT.parent))

from recommendation_engine import (  # noqa: E402
    GroupedRecommendationResult,
    RecommendationCandidate,
    RecommendationQuery,
    RecommendationRepository,
    RecommendationResult,
    RecommendationScoreBreakdown,
    RuleBasedRecommender,
    default_recommendation_config,
    grouped_recommendations_to_dict,
)
from recommendation_engine.engine import _build_decision_strategy  # noqa: E402
from crawlernest.core.services.recommendation_service import RecommendationService  # noqa: E402


class TestRecommendationEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.recommender = RuleBasedRecommender(default_recommendation_config())
        self.service = RecommendationService.__new__(RecommendationService)
        self.candidates = [
            RecommendationCandidate(
                canonical_university_id=1,
                university_name="University of Oxford",
                country="United Kingdom",
                ranking_year=2026,
                aggregated_rank=3,
                aggregated_score=98.7,
                coverage_ratio=1.0,
                gpa_min=3.5,
                ielts_min=5.5,
                toefl_min=100,
                duolingo_min=120,
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
                gpa_min=3.2,
                ielts_min=6.5,
                toefl_min=90,
                duolingo_min=115,
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
                gpa_min=3.4,
                ielts_min=6.5,
                toefl_min=95,
                duolingo_min=120,
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

    def test_recommendation_output_includes_deadline_info_when_available(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertIn("deadline_info", row)
        self.assertEqual(row["deadline_info"]["recommended_deadline"], "2025-12-01")
        self.assertEqual(row["deadline_info"]["deadline_type"], "early")
        self.assertEqual(row["deadline_info"]["urgency"], "high")
        self.assertIn("takes priority", row["deadline_info"]["reason"])

    def test_recommendation_output_omits_deadline_info_without_admission_data(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example")])
        )
        row = payload["target"][0]
        self.assertNotIn("deadline_info", row)

    def test_recommendation_output_applies_multi_deadline_priority(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "deadline": "2026-04-15",
                            "deadline_candidates": [
                                ("international", "2026-04-15"),
                                ("domestic", "2026-06-30"),
                            ],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["deadline_info"]["recommended_deadline"], "2026-04-15")
        self.assertEqual(row["deadline_info"]["deadline_type"], "international")
        self.assertEqual(row["deadline_info"]["urgency"], "high")
        self.assertTrue(row["deadline_info"]["reason"])

    def test_recommendation_output_includes_ielts_fit_info_comfortably_above(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 7.0},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["ielts_fit_info"]["required_score"], 6.5)
        self.assertEqual(row["ielts_fit_info"]["user_score"], 7.0)
        self.assertEqual(row["ielts_fit_info"]["margin"], 0.5)
        self.assertEqual(row["ielts_fit_info"]["fit_band"], "comfortably_above")
        self.assertEqual(row["ielts_fit_info"]["fit_urgency"], "low")
        self.assertEqual(
            row["ielts_fit_info"]["reason"],
            "IELTS 7.0 is 0.5 above the required 6.5",
        )

    def test_recommendation_output_includes_ielts_fit_info_exact_meet(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 6.5},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["ielts_fit_info"]["margin"], 0.0)
        self.assertEqual(row["ielts_fit_info"]["fit_band"], "meets_requirement")
        self.assertEqual(row["ielts_fit_info"]["fit_urgency"], "medium")
        self.assertEqual(
            row["ielts_fit_info"]["reason"],
            "IELTS 6.5 exactly meets the required 6.5",
        )

    def test_recommendation_output_includes_ielts_fit_info_slightly_below(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 6.0},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["ielts_fit_info"]["margin"], -0.5)
        self.assertEqual(row["ielts_fit_info"]["fit_band"], "slightly_below")
        self.assertEqual(row["ielts_fit_info"]["fit_urgency"], "high")
        self.assertEqual(
            row["ielts_fit_info"]["reason"],
            "IELTS 6.0 is 0.5 below the required 6.5",
        )

    def test_recommendation_output_omits_ielts_fit_info_when_data_missing(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example")])
        )
        row = payload["target"][0]
        self.assertNotIn("ielts_fit_info", row)

    def test_recommendation_output_includes_toefl_fit_info_comfortably_above(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_toefl": 100})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["toefl_fit_info"]["required_score"], 90.0)
        self.assertEqual(row["toefl_fit_info"]["user_score"], 100.0)
        self.assertEqual(row["toefl_fit_info"]["margin"], 10.0)
        self.assertEqual(row["toefl_fit_info"]["fit_band"], "comfortably_above")
        self.assertEqual(row["toefl_fit_info"]["fit_urgency"], "low")
        self.assertEqual(
            row["toefl_fit_info"]["reason"],
            "TOEFL 100 is 10 above the required 90",
        )

    def test_recommendation_output_includes_toefl_fit_info_meets_requirement(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_toefl": 90})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["toefl_fit_info"]["fit_band"], "meets_requirement")
        self.assertEqual(row["toefl_fit_info"]["fit_urgency"], "medium")
        self.assertEqual(
            row["toefl_fit_info"]["reason"],
            "TOEFL 90 exactly meets the required 90",
        )

    def test_recommendation_output_includes_toefl_fit_info_slightly_below(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_toefl": 85})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["toefl_fit_info"]["fit_band"], "slightly_below")
        self.assertEqual(row["toefl_fit_info"]["fit_urgency"], "high")
        self.assertEqual(
            row["toefl_fit_info"]["reason"],
            "TOEFL 85 is 5 below the required 90",
        )

    def test_recommendation_output_includes_gpa_fit_info_comfortably_above(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_gpa": 3.8})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["gpa_fit_info"]["fit_band"], "comfortably_above")
        self.assertEqual(row["gpa_fit_info"]["fit_urgency"], "low")
        self.assertEqual(
            row["gpa_fit_info"]["reason"],
            "GPA 3.8 is 0.3 above the required 3.5",
        )

    def test_recommendation_output_includes_gpa_fit_info_slightly_below(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_gpa": 3.2})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["gpa_fit_info"]["fit_band"], "slightly_below")
        self.assertEqual(row["gpa_fit_info"]["fit_urgency"], "high")
        self.assertEqual(
            row["gpa_fit_info"]["reason"],
            "GPA 3.2 is 0.3 below the required 3.5",
        )

    def test_recommendation_output_omits_gpa_fit_info_for_invalid_scale(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        gpa_min=5.0,
                        metadata={"user_gpa": 3.8},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertNotIn("gpa_fit_info", row)

    def test_recommendation_output_includes_duolingo_fit_info_comfortably_above(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_duolingo": 130})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["duolingo_fit_info"]["fit_band"], "comfortably_above")
        self.assertEqual(row["duolingo_fit_info"]["fit_urgency"], "low")
        self.assertEqual(
            row["duolingo_fit_info"]["reason"],
            "Duolingo 130 is 10 above the required 120",
        )

    def test_recommendation_output_includes_duolingo_fit_info_slightly_below(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_duolingo": 110})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["duolingo_fit_info"]["fit_band"], "slightly_below")
        self.assertEqual(row["duolingo_fit_info"]["fit_urgency"], "high")
        self.assertEqual(
            row["duolingo_fit_info"]["reason"],
            "Duolingo 110 is 10 below the required 120",
        )

    def test_recommendation_output_includes_admission_composite_strong(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [("early", "2025-12-01"), ("final", "2026-04-15")],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["admission_composite"]["admission_readiness"], "strong")
        self.assertEqual(row["admission_composite"]["admission_risk"], "medium")
        self.assertEqual(
            row["admission_composite"]["top_concerns"],
            ["early_deadline", "high_urgency_deadline", "ielts_comfortably_above"],
        )
        self.assertEqual(
            row["admission_composite"]["top_concern_labels"],
            ["Early deadline", "High urgency deadline", "IELTS comfortably above requirement"],
        )

    def test_recommendation_output_includes_admission_composite_moderate(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["admission_composite"]["admission_readiness"], "moderate")
        self.assertEqual(row["admission_composite"]["admission_risk"], "medium")
        self.assertEqual(
            row["admission_composite"]["top_concerns"],
            ["ielts_meets_requirement", "toefl_comfortably_above"],
        )

    def test_recommendation_output_includes_admission_composite_weak_high_risk(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 5.0},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["admission_composite"]["admission_readiness"], "weak")
        self.assertEqual(row["admission_composite"]["admission_risk"], "high")
        self.assertEqual(row["admission_composite"]["top_concerns"], ["ielts_well_below"])

    def test_recommendation_output_includes_admission_composite_unknown_when_no_signals(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example", metadata={})])
        )
        row = payload["target"][0]
        self.assertNotIn("admission_composite", row)

    def test_recommendation_output_includes_decision_output_apply_early(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [("early", "2025-12-01"), ("final", "2026-04-15")],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["decision_output"]["decision_action"], "apply_early")
        self.assertEqual(row["decision_output"]["decision_strength"], "strong")
        self.assertLessEqual(len(row["decision_output"]["recommended_next_steps"]), 3)
        self.assertEqual(
            row["decision_strategy"]["primary_strategy"],
            "Submit early while requirements are already acceptable",
        )
        self.assertIn("Prepare documents immediately", row["decision_strategy"]["supporting_actions"])

    def test_recommendation_output_includes_decision_output_apply(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        gpa_min=3.0,
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "user_gpa": 3.9,
                            "user_duolingo": 130,
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["admission_composite"]["admission_readiness"], "strong")
        self.assertEqual(row["admission_composite"]["admission_risk"], "low")
        self.assertEqual(row["decision_output"]["decision_action"], "apply")
        self.assertEqual(row["decision_output"]["decision_strength"], "strong")

    def test_recommendation_output_includes_decision_output_apply_with_caution(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 6.5, "user_toefl": 100},
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["decision_output"]["decision_action"], "apply_with_caution")
        self.assertEqual(row["decision_output"]["decision_strength"], "moderate")
        self.assertEqual(
            row["decision_strategy"]["primary_strategy"],
            "Apply but expect some risk in current profile",
        )

    def test_recommendation_output_includes_decision_output_improve_profile_first(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[self._build_result("University of Example", metadata={"user_ielts": 5.0})]
            )
        )
        row = payload["target"][0]
        self.assertEqual(row["decision_output"]["decision_action"], "improve_profile_first")
        self.assertEqual(row["decision_output"]["decision_strength"], "strong")
        self.assertEqual(
            row["decision_strategy"]["primary_strategy"],
            "Delay application and improve profile first",
        )

    def test_recommendation_output_includes_decision_output_insufficient_data(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example", metadata={"deadline": None})])
        )
        row = payload["target"][0]
        self.assertNotIn("admission_composite", row)
        self.assertEqual(row["decision_output"]["decision_action"], "insufficient_data")
        self.assertEqual(row["decision_output"]["decision_strength"], "unknown")
        self.assertLessEqual(len(row["decision_output"]["recommended_next_steps"]), 3)
        self.assertEqual(
            row["decision_strategy"]["primary_strategy"],
            "Collect missing requirement information first",
        )

    def test_decision_strategy_injects_surface_concern_actions(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                            "user_gpa": 3.5,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [("early", "2025-12-01"), ("final", "2026-04-15")],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertIn(
            "Pay attention to GPA-sensitive evaluation",
            row["decision_strategy"]["supporting_actions"],
        )
        self.assertIn(
            "Double-check requirement-sensitive components",
            row["decision_strategy"]["risk_mitigation"],
        )
        self.assertEqual(
            row["decision_strategy"]["timeline_hint"],
            "Move quickly so the application is ready before the early deadline",
        )
        self.assertLessEqual(len(row["decision_strategy"]["supporting_actions"]), 3)
        self.assertLessEqual(len(row["decision_strategy"]["risk_mitigation"]), 3)

    def test_decision_strategy_prefers_surface_signals_when_available(self):
        strategy = _build_decision_strategy(
            {
                "decision_output": {
                    "decision_action": "apply_with_caution",
                    "decision_reason": "Synthetic strategy reason",
                },
                "surfaceSignals": [
                    {"concern": "ielts_slightly_below"},
                    {"concern": "gpa_meets_requirement"},
                ],
                "admission_composite": {
                    "top_concerns": ["early_deadline"],
                },
            }
        )
        self.assertIsNotNone(strategy)
        self.assertIn("Pay attention to GPA-sensitive evaluation", strategy["supporting_actions"])
        self.assertIn("Consider retaking IELTS to reduce risk", strategy["risk_mitigation"])
        self.assertNotEqual(
            strategy["timeline_hint"],
            "Move quickly so the application is ready before the early deadline",
        )

    def test_admission_composite_top_concerns_truncates_to_three_in_priority_order(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.0,
                            "user_toefl": 85,
                            "user_gpa": 3.5,
                            "user_duolingo": 130,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [("early", "2025-12-01"), ("final", "2026-04-15")],
                        },
                    )
                ]
            )
        )
        row = payload["target"][0]
        self.assertEqual(
            row["admission_composite"]["top_concerns"],
            ["ielts_slightly_below", "toefl_slightly_below", "early_deadline"],
        )
        self.assertEqual(
            row["admission_composite"]["top_concern_labels"],
            ["IELTS slightly below requirement", "TOEFL slightly below requirement", "Early deadline"],
        )

    def test_service_admission_composite_unknown_token_falls_back_safely(self):
        composite = self.service._build_admission_composite(
            {
                "admission_readiness": "moderate",
                "admission_risk": "medium",
                "top_concerns": ["custom_unknown_token"],
                "reason": "Synthetic reason",
            }
        )
        self.assertEqual(composite["topConcerns"], ["custom_unknown_token"])
        self.assertEqual(composite["topConcernLabels"], ["Custom unknown token"])

    def test_repository_preserves_real_candidate_deadline_metadata(self):
        repo = RecommendationRepository(_FakeConnection([
            (
                7,
                "University of Example",
                "United Kingdom",
                2026,
                42,
                91.2,
                0.85,
                3.5,
                6.5,
                90,
                120,
                {"QS": 42},
                {"QS": 91.2},
                "rank_agg_v1",
                2,
                1,
                "2025-12-01",
                [["early", "2025-12-01"], ["final", "2026-04-15"]],
            )
        ]))
        rows = repo.fetch_candidates(ranking_year=2026, country="United Kingdom")
        self.assertEqual(rows[0].metadata["deadline"], "2025-12-01")
        self.assertEqual(
            rows[0].metadata["deadline_candidates"],
            [["early", "2025-12-01"], ["final", "2026-04-15"]],
        )

    def test_repository_backed_recommendation_output_includes_deadline_info(self):
        repo = RecommendationRepository(_FakeConnection([
            (
                7,
                "University of Example",
                "United Kingdom",
                2026,
                42,
                91.2,
                0.85,
                3.5,
                6.5,
                90,
                120,
                {"QS": 42},
                {"QS": 91.2},
                "rank_agg_v1",
                2,
                1,
                "2025-12-01",
                [["early", "2025-12-01"], ["final", "2026-04-15"]],
            )
        ]))
        candidates = repo.fetch_candidates(ranking_year=2026, country="United Kingdom")
        result = self.recommender.recommend(
            candidates,
            RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=1),
        )
        payload = grouped_recommendations_to_dict(GroupedRecommendationResult(target=result))
        row = payload["target"][0]
        self.assertEqual(row["deadline_info"]["recommended_deadline"], "2025-12-01")
        self.assertEqual(row["deadline_info"]["deadline_type"], "early")
        self.assertEqual(row["deadline_info"]["urgency"], "high")
        self.assertIn("takes priority", row["deadline_info"]["reason"])

    def test_repository_backed_output_omits_deadline_info_without_deadline_metadata(self):
        repo = RecommendationRepository(_FakeConnection([
            (
                7,
                "University of Example",
                "United Kingdom",
                2026,
                42,
                91.2,
                0.85,
                3.5,
                6.5,
                90,
                120,
                {"QS": 42},
                {"QS": 91.2},
                "rank_agg_v1",
                2,
                1,
                None,
                [],
            )
        ]))
        candidates = repo.fetch_candidates(ranking_year=2026, country="United Kingdom")
        result = self.recommender.recommend(
            candidates,
            RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=1),
        )
        payload = grouped_recommendations_to_dict(GroupedRecommendationResult(target=result))
        row = payload["target"][0]
        self.assertNotIn("deadline_info", row)

    def test_repository_backed_plain_deadline_falls_back_to_unknown_type(self):
        repo = RecommendationRepository(_FakeConnection([
            (
                7,
                "University of Example",
                "United Kingdom",
                2026,
                42,
                91.2,
                0.85,
                3.5,
                6.5,
                90,
                120,
                {"QS": 42},
                {"QS": 91.2},
                "rank_agg_v1",
                2,
                1,
                "2025-12-01",
                [],
            )
        ]))
        candidates = repo.fetch_candidates(ranking_year=2026, country="United Kingdom")
        result = self.recommender.recommend(
            candidates,
            RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=1),
        )
        payload = grouped_recommendations_to_dict(GroupedRecommendationResult(target=result))
        row = payload["target"][0]
        self.assertEqual(row["deadline_info"]["recommended_deadline"], "2025-12-01")
        self.assertEqual(row["deadline_info"]["deadline_type"], "unknown")
        self.assertEqual(row["deadline_info"]["urgency"], "unknown")

    def test_service_exposes_deadline_highlight_when_deadline_info_exists(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(items[0]["deadlineInfo"]["recommended_deadline"], "2025-12-01")
        self.assertEqual(
            items[0]["deadlineHighlight"],
            {
                "date": "2025-12-01",
                "type": "early",
                "urgency": "high",
                "message": "Early deadline on 2025-12-01 should be prioritized.",
                "reason": "early deadline takes priority over final deadline",
            },
        )

    def test_service_omits_deadline_highlight_without_deadline_info(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example")])
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertNotIn("deadlineInfo", items[0])
        self.assertNotIn("deadlineHighlight", items[0])

    def test_service_exposes_ielts_fit_highlight_when_ielts_fit_info_exists(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={"user_ielts": 7.0},
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(
            items[0]["ieltsFitInfo"],
            {
                "required_score": 6.5,
                "user_score": 7.0,
                "margin": 0.5,
                "fit_band": "comfortably_above",
                "fit_urgency": "low",
                "reason": "IELTS 7.0 is 0.5 above the required 6.5",
            },
        )
        self.assertEqual(
            items[0]["ieltsFitHighlight"],
            {
                "requiredScore": 6.5,
                "userScore": 7.0,
                "margin": 0.5,
                "fitBand": "comfortably_above",
                "fitUrgency": "low",
                "message": "IELTS +0.5 above requirement",
                "reason": "IELTS 7.0 is 0.5 above the required 6.5",
            },
        )

    def test_service_exposes_multi_requirement_highlights(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "user_gpa": 3.5,
                            "user_duolingo": 130,
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(items[0]["toeflFitHighlight"]["message"], "TOEFL +10 above requirement")
        self.assertEqual(items[0]["gpaFitHighlight"]["message"], "GPA meets requirement")
        self.assertEqual(items[0]["duolingoFitHighlight"]["message"], "Duolingo +10 above requirement")

    def test_service_surface_signals_prioritize_below_threshold_then_deadline(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.0,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(
            [signal["concern"] for signal in items[0]["surfaceSignals"][:2]],
            ["ielts_slightly_below", "early_deadline"],
        )
        self.assertEqual(
            [signal["type"] for signal in items[0]["surfaceSignals"][:2]],
            ["ielts", "deadline"],
        )
        self.assertTrue(items[0]["surfaceSignals"][0]["emphasized"])
        self.assertTrue(items[0]["surfaceSignals"][1]["emphasized"])

    def test_service_surface_signals_prioritize_deadline_then_best_requirement(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(
            [signal["concern"] for signal in items[0]["surfaceSignals"][:2]],
            ["early_deadline", "ielts_comfortably_above"],
        )
        self.assertEqual(
            [signal["type"] for signal in items[0]["surfaceSignals"][:2]],
            ["deadline", "ielts"],
        )

    def test_service_surface_signals_all_comfortably_above_are_stable(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "user_gpa": 3.9,
                            "user_duolingo": 130,
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        items_again, _counts_again = self.service._flatten_grouped_results(payload)
        ordered_types = [signal["type"] for signal in items[0]["surfaceSignals"]]
        ordered_concerns = [signal["concern"] for signal in items[0]["surfaceSignals"]]
        ordered_types_again = [signal["type"] for signal in items_again[0]["surfaceSignals"]]
        self.assertEqual(ordered_types[:2], ["ielts", "toefl"])
        self.assertEqual(ordered_types, ordered_types_again)
        self.assertEqual(
            ordered_concerns,
            [
                "ielts_comfortably_above",
                "toefl_comfortably_above",
                "gpa_comfortably_above",
            ],
        )

    def test_service_surface_signals_missing_data_is_safe(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example")])
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertNotIn("surfaceSignals", items[0])

    def test_service_surface_signals_concerns_match_composite_and_definition(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.0,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        top_concerns = set(items[0]["admissionComposite"]["topConcerns"])
        for signal in items[0]["surfaceSignals"]:
            self.assertIn(signal["concern"], top_concerns)
        self.assertEqual(items[0]["surfaceSignals"][0]["label"], "IELTS slightly below requirement")
        self.assertEqual(items[0]["surfaceSignals"][0]["priorityLevel"], 0)
        self.assertEqual(items[0]["surfaceSignals"][1]["label"], "Early deadline")
        self.assertEqual(items[0]["surfaceSignals"][1]["priorityLevel"], 1)

    def test_service_exposes_admission_composite(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(items[0]["admissionComposite"]["admissionReadiness"], "moderate")
        self.assertEqual(items[0]["admissionComposite"]["admissionRisk"], "medium")
        self.assertEqual(
            items[0]["admissionComposite"]["topConcerns"],
            ["ielts_meets_requirement", "toefl_comfortably_above"],
        )
        self.assertEqual(
            items[0]["admissionComposite"]["topConcernLabels"],
            ["IELTS just meets requirement", "TOEFL comfortably above requirement"],
        )

    def test_service_exposes_decision_output(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertEqual(items[0]["decisionOutput"]["decisionAction"], "apply_early")
        self.assertEqual(items[0]["decisionOutput"]["decisionStrength"], "strong")
        self.assertLessEqual(len(items[0]["decisionOutput"]["recommendedNextSteps"]), 3)
        self.assertEqual(
            items[0]["decisionStrategy"]["primaryStrategy"],
            "Submit early while requirements are already acceptable",
        )
        self.assertLessEqual(len(items[0]["decisionStrategy"]["supportingActions"]), 3)

    def test_service_omits_ielts_fit_highlight_without_ielts_fit_info(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(target=[self._build_result("University of Example")])
        )
        items, _counts = self.service._flatten_grouped_results(payload)
        self.assertNotIn("ieltsFitInfo", items[0])
        self.assertNotIn("ieltsFitHighlight", items[0])
        self.assertNotIn("toeflFitInfo", items[0])
        self.assertNotIn("toeflFitHighlight", items[0])
        self.assertNotIn("gpaFitInfo", items[0])
        self.assertNotIn("gpaFitHighlight", items[0])
        self.assertNotIn("duolingoFitInfo", items[0])
        self.assertNotIn("duolingoFitHighlight", items[0])

    def test_service_assistant_reply_surfaces_deadline_note(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        expected_note = (
            "Deadline note: Early deadline on 2025-12-01 should be prioritized. "
            "Reason: early deadline takes priority over final deadline"
        )
        self.assertIn(expected_note, paragraphs)
        self.assertIn(expected_note, assistant_reply)

    def test_service_assistant_reply_surfaces_ielts_note_and_preserves_deadline_note(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.0,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.0, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        ielts_note = "IELTS note: IELTS 6.0 is 0.5 below the required 6.5, so this option is higher risk."
        deadline_note = (
            "Deadline note: Early deadline on 2025-12-01 should be prioritized. "
            "Reason: early deadline takes priority over final deadline"
        )
        self.assertIn(ielts_note, paragraphs)
        self.assertIn(deadline_note, paragraphs)
        self.assertIn(ielts_note, assistant_reply)
        self.assertIn(deadline_note, assistant_reply)

    def test_service_assistant_reply_limits_requirement_notes_and_preserves_deadline(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 7.0,
                            "user_toefl": 100,
                            "user_gpa": 3.5,
                            "user_duolingo": 130,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(
            country="United Kingdom",
            ielts_score=7.0,
            toefl_score=100,
            gpa_score=3.5,
            duolingo_score=130,
            target_rank=100,
            limit=1,
        )
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        surfaced_notes = [
            p for p in paragraphs
            if p.startswith(("IELTS note:", "TOEFL note:", "GPA note:", "Duolingo note:", "Deadline note:"))
        ]
        self.assertLessEqual(len(surfaced_notes), 2)
        self.assertIn("This option shows a few key considerations.", paragraphs)
        self.assertIn("Deadline note: Early deadline on 2025-12-01 should be prioritized. Reason: early deadline takes priority over final deadline", assistant_reply)
        self.assertIn("GPA note: GPA 3.5 exactly meets the required 3.5.", assistant_reply)
        self.assertNotIn("IELTS note: IELTS 7.0 is 0.5 above the required 6.5.", assistant_reply)
        self.assertNotIn("TOEFL note: TOEFL 100 is 10 above the required 90.", assistant_reply)

    def test_service_assistant_reply_surfaces_admission_composite_note(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, toefl_score=100, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        expected_note = (
            "Admission note: readiness is moderate and risk is medium. "
            "Top concerns: IELTS just meets requirement; TOEFL comfortably above requirement. "
            "Reason: This option has mixed requirement-fit signals, with some scores only meeting the requirement."
        )
        self.assertIn(expected_note, paragraphs)
        self.assertIn(expected_note, assistant_reply)
        self.assertNotIn("ielts_meets_requirement", assistant_reply)
        self.assertNotIn("toefl_comfortably_above", assistant_reply)

    def test_service_assistant_reply_surfaces_decision_output_note(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, toefl_score=100, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        expected_prefix = "Suggested action: Apply early. Confidence: Strong."
        self.assertTrue(any(p.startswith(expected_prefix) for p in paragraphs))
        self.assertIn(expected_prefix, assistant_reply)

    def test_service_assistant_reply_surfaces_decision_strategy_note(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.5,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.5, toefl_score=100, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        expected_prefix = "Strategy: Submit early while requirements are already acceptable."
        self.assertTrue(any(p.startswith(expected_prefix) for p in paragraphs))
        self.assertIn(expected_prefix, assistant_reply)

    def test_service_assistant_reply_prioritizes_below_threshold_then_deadline(self):
        payload = grouped_recommendations_to_dict(
            GroupedRecommendationResult(
                target=[
                    self._build_result(
                        "University of Example",
                        metadata={
                            "user_ielts": 6.0,
                            "user_toefl": 100,
                            "deadline": "2025-12-01",
                            "deadline_candidates": [
                                ("early", "2025-12-01"),
                                ("final", "2026-04-15"),
                            ],
                        },
                    )
                ]
            )
        )
        items, counts = self.service._flatten_grouped_results(payload)
        query = RecommendationQuery(country="United Kingdom", ielts_score=6.0, toefl_score=100, target_rank=100, limit=1)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
        )
        signal_notes = [
            p for p in paragraphs
            if p.startswith(("IELTS note:", "TOEFL note:", "GPA note:", "Duolingo note:", "Deadline note:"))
        ]
        self.assertEqual(
            signal_notes,
            [
                "IELTS note: IELTS 6.0 is 0.5 below the required 6.5, so this option is higher risk.",
                "Deadline note: Early deadline on 2025-12-01 should be prioritized. Reason: early deadline takes priority over final deadline",
            ],
        )
        self.assertNotIn("TOEFL note: TOEFL 100 is 10 above the required 90.", assistant_reply)

    def test_application_plan_builds_with_only_target_items(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item(
                    "University of Example",
                    matching_score=0.87,
                    action="apply",
                    risk="medium",
                    strategy="Proceed with application under current profile",
                )
            ]
        )
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan["reach"]), 0)
        self.assertEqual(len(plan["target"]), 1)
        self.assertEqual(len(plan["safety"]), 0)
        self.assertEqual(
            plan["planSummary"],
            "Balanced plan with 0 reach, 1 target, and 0 safety options.",
        )

    def test_application_plan_without_safety_becomes_high_risk(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item(
                    "Risky One",
                    matching_score=0.72,
                    action="apply_with_caution",
                    risk="high",
                    strategy="Apply but expect some risk in current profile",
                ),
                self._build_service_item(
                    "Risky Two",
                    matching_score=0.74,
                    action="apply_with_caution",
                    risk="medium",
                    strategy="Apply but expect some risk in current profile",
                ),
            ]
        )
        self.assertEqual(plan["riskDistribution"], "Overall plan risk: high (high=1, medium=1, low=0).")
        self.assertEqual(
            plan["recommendedStrategy"],
            "This plan leans risky. Consider adding 1–2 safer options.",
        )

    def test_application_plan_trims_reach_to_max_two(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Reach C", matching_score=0.70, action="apply_with_caution", risk="medium"),
                self._build_service_item("Reach A", matching_score=0.74, action="apply_with_caution", risk="high"),
                self._build_service_item("Reach B", matching_score=0.72, action="apply_with_caution", risk="medium"),
            ]
        )
        self.assertEqual(
            [item["universityName"] for item in plan["reach"]],
            ["Reach A", "Reach B"],
        )
        self.assertEqual(len(plan["reach"]), 2)

    def test_application_plan_ordering_is_deterministic(self):
        items = [
            self._build_service_item("Gamma", matching_score=0.88, action="apply", risk="medium"),
            self._build_service_item("Alpha", matching_score=0.88, action="apply", risk="medium"),
            self._build_service_item("Beta", matching_score=0.88, action="apply", risk="medium"),
        ]
        plan = self.service._build_application_plan(items)
        plan_again = self.service._build_application_plan(list(reversed(items)))
        self.assertEqual(
            [item["universityName"] for item in plan["target"]],
            ["Alpha", "Beta"],
        )
        self.assertEqual(plan["target"], plan_again["target"])

    def test_application_plan_builds_balanced_case(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Reach Option", matching_score=0.72, action="apply_with_caution", risk="medium"),
                self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium"),
                self._build_service_item("Safety Option", matching_score=0.95, action="apply_early", risk="low"),
            ]
        )
        self.assertEqual(
            plan["primaryChoice"],
            {
                "universityName": "Target Option",
                "bucket": "target",
                "reason": "Best balance of fit and manageable risk among target options.",
            },
        )
        self.assertEqual(plan["planConfidence"], "high")
        self.assertEqual(
            plan["planConfidenceReason"],
            "This plan has both target and safety coverage, and the strongest options look stable.",
        )
        self.assertEqual(plan["planWarnings"], [])
        self.assertEqual(plan["riskDistribution"], "Overall plan risk: moderate (high=0, medium=2, low=1).")
        self.assertEqual(
            plan["recommendedStrategy"],
            "This is a balanced plan. Prioritize target schools while keeping reach as upside.",
        )

    def test_application_plan_builds_safe_heavy_case(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Safety One", matching_score=0.96, action="apply", risk="low"),
                self._build_service_item("Safety Two", matching_score=0.94, action="apply_early", risk="low"),
                self._build_service_item("Target One", matching_score=0.82, action="apply", risk="medium"),
            ]
        )
        self.assertEqual(plan["riskDistribution"], "Overall plan risk: low (high=0, medium=1, low=2).")
        self.assertEqual(
            plan["recommendedStrategy"],
            "You can proceed confidently with this plan. Focus on execution and timeline.",
        )

    def test_application_plan_mixed_quality_remains_medium(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Target One", matching_score=0.77, action="apply", risk="medium"),
                self._build_service_item("Safety One", matching_score=0.89, action="apply", risk="low"),
            ]
        )
        self.assertEqual(plan["planConfidence"], "medium")
        self.assertEqual(
            plan["planConfidenceReason"],
            "This plan has some stable structure, but at least one core bucket is weaker or less secure.",
        )

    def test_application_plan_no_safety_warning_and_lower_confidence(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Target One", matching_score=0.84, action="apply", risk="medium"),
                self._build_service_item("Reach One", matching_score=0.72, action="apply_with_caution", risk="high"),
            ]
        )
        self.assertIn("No safety options included", plan["planWarnings"])
        self.assertEqual(plan["planConfidence"], "medium")

    def test_application_plan_no_target_warning_and_primary_choice_falls_back_to_safety(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Safety One", matching_score=0.95, action="apply", risk="low"),
                self._build_service_item("Reach One", matching_score=0.72, action="apply_with_caution", risk="medium"),
            ]
        )
        self.assertIn("Plan lacks stable target options", plan["planWarnings"])
        self.assertEqual(
            plan["primaryChoice"],
            {
                "universityName": "Safety One",
                "bucket": "safety",
                "reason": "Most stable option available in the current plan.",
            },
        )

    def test_application_plan_only_reach_is_low_confidence(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Reach One", matching_score=0.72, action="apply_with_caution", risk="high"),
                self._build_service_item("Reach Two", matching_score=0.70, action="apply_with_caution", risk="medium"),
            ]
        )
        self.assertEqual(
            plan["primaryChoice"],
            {
                "universityName": "Reach One",
                "bucket": "reach",
                "reason": "Highest-upside option available, but the plan is currently risk-heavy.",
            },
        )
        self.assertEqual(
            plan["planWarnings"],
            [
                "No safety options included",
                "Plan lacks stable target options",
                "Plan leans high-risk",
            ],
        )
        self.assertEqual(plan["planConfidence"], "low")
        self.assertEqual(
            plan["planConfidenceReason"],
            "This plan is missing stable coverage or leans too heavily on risky options.",
        )

    def test_application_plan_narrow_plan_warning(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Target One", matching_score=0.84, action="apply", risk="medium"),
            ]
        )
        self.assertIn("Plan is narrow and may need more coverage", plan["planWarnings"])

    def test_application_plan_warning_cap_and_order(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Reach One", matching_score=0.72, action="apply_with_caution", risk="high"),
                self._build_service_item("Reach Two", matching_score=0.70, action="apply_with_caution", risk="medium"),
            ]
        )
        self.assertEqual(
            plan["planWarnings"],
            [
                "No safety options included",
                "Plan lacks stable target options",
                "Plan leans high-risk",
            ],
        )
        self.assertEqual(len(plan["planWarnings"]), 3)

    def test_application_plan_quality_adjustment_is_bounded_to_plus_one(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Target One", matching_score=0.85, action="apply", risk="medium"),
                self._build_service_item("Safety One", matching_score=0.95, action="apply", risk="low"),
            ]
        )
        self.assertEqual(plan["planConfidence"], "high")

    def test_application_plan_quality_adjustment_is_bounded_to_minus_one(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Target One", matching_score=0.77, action="apply", risk="medium"),
                self._build_service_item("Safety One", matching_score=0.89, action="apply", risk="low"),
            ]
        )
        self.assertEqual(plan["planConfidence"], "medium")

    def test_application_plan_note_is_appended_to_assistant_reply(self):
        plan = self.service._build_application_plan(
            [
                self._build_service_item("Reach Option", matching_score=0.72, action="apply_with_caution", risk="medium"),
                self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium"),
                self._build_service_item("Safety Option", matching_score=0.95, action="apply_early", risk="low"),
            ]
        )
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=3),
            counts={"reach": 1, "target": 1, "safety": 1},
            items=[self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium")],
            application_plan=plan,
        )
        self.assertIn("I built a structured application plan.", paragraphs)
        self.assertIn("Reach: Reach Option.", paragraphs)
        self.assertIn("Target: Target Option.", paragraphs)
        self.assertIn("Safety: Safety Option.", paragraphs)
        self.assertIn(plan["recommendedStrategy"], assistant_reply)
        self.assertIn("Primary choice: Target Option. Plan confidence: high.", assistant_reply)
        self.assertIn(plan["planConfidenceReason"], assistant_reply)
        self.assertIn("No major warning signals stand out in the current plan.", assistant_reply)

    def test_application_plans_select_balanced_when_strong(self):
        plans = self.service._build_application_plans(
            [
                self._build_service_item("Reach Option", matching_score=0.72, action="apply_with_caution", risk="medium"),
                self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium"),
                self._build_service_item("Safety Option", matching_score=0.95, action="apply_early", risk="low"),
            ]
        )
        comparison = self.service._build_plan_comparison(plans)
        self.assertEqual(comparison["recommendedPlan"], "balanced")

    def test_application_plans_select_conservative_when_safer(self):
        plans = self.service._build_application_plans(
            [
                self._build_service_item("Reach One", matching_score=0.73, action="apply_with_caution", risk="high"),
                self._build_service_item("Reach Two", matching_score=0.71, action="apply_with_caution", risk="medium"),
                self._build_service_item("Safety One", matching_score=0.95, action="apply", risk="low"),
            ]
        )
        comparison = self.service._build_plan_comparison(plans)
        self.assertEqual(comparison["recommendedPlan"], "conservative")

    def test_application_plans_select_aggressive_when_stronger_upside(self):
        plans = self.service._build_application_plans(
            [
                self._build_service_item("Reach One", matching_score=0.74, action="apply_with_caution", risk="medium"),
                self._build_service_item("Reach Two", matching_score=0.73, action="apply_with_caution", risk="medium"),
                self._build_service_item("Target One", matching_score=0.84, action="apply", risk="medium"),
            ]
        )
        comparison = self.service._build_plan_comparison(plans)
        self.assertEqual(comparison["recommendedPlan"], "aggressive")

    def test_application_plan_invalid_variants_are_rejected(self):
        plans = self.service._build_application_plans(
            [
                self._build_service_item("Target One", matching_score=0.84, action="apply", risk="medium"),
            ]
        )
        self.assertEqual([plan["planName"] for plan in plans], ["balanced"])

    def test_application_plans_are_deterministic(self):
        items = [
            self._build_service_item("Reach One", matching_score=0.74, action="apply_with_caution", risk="medium"),
            self._build_service_item("Target One", matching_score=0.84, action="apply", risk="medium"),
            self._build_service_item("Safety One", matching_score=0.95, action="apply", risk="low"),
        ]
        plans = self.service._build_application_plans(items)
        reversed_plans = self.service._build_application_plans(list(reversed(items)))
        self.assertEqual(plans, reversed_plans)

    def test_multi_plan_note_is_appended_to_assistant_reply(self):
        items = [
            self._build_service_item("Reach Option", matching_score=0.72, action="apply_with_caution", risk="medium"),
            self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium"),
            self._build_service_item("Safety Option", matching_score=0.95, action="apply_early", risk="low"),
        ]
        plan = self.service._build_application_plan(items)
        plans = self.service._build_application_plans(items)
        comparison = self.service._build_plan_comparison(plans)
        assistant_reply, paragraphs = self.service._build_assistant_reply(
            query=RecommendationQuery(country="United Kingdom", ielts_score=6.5, target_rank=100, limit=3),
            counts={"reach": 1, "target": 1, "safety": 1},
            items=[self._build_service_item("Target Option", matching_score=0.84, action="apply", risk="medium")],
            application_plan=plan,
            application_plans=plans,
            plan_comparison=comparison,
        )
        self.assertIn("I built multiple application strategies for you.", paragraphs)
        self.assertIn("Recommended plan: Balanced.", paragraphs)
        self.assertIn(comparison["reason"], assistant_reply)
        self.assertEqual(len(comparison["tradeoffs"]), 2)

    def _build_result(
        self,
        university_name: str,
        gpa_min: float = 3.5,
        ielts_min: float = 6.5,
        toefl_min: float = 90.0,
        duolingo_min: float = 120.0,
        metadata: dict | None = None,
    ) -> RecommendationResult:
        return RecommendationResult(
            canonical_university_id=99,
            university_name=university_name,
            country="United Kingdom",
            aggregated_rank=42,
            gpa_min=gpa_min,
            ielts_min=ielts_min,
            toefl_min=toefl_min,
            duolingo_min=duolingo_min,
            matching_score=0.87,
            category="target",
            preference_alignment="strong",
            recommendation_confidence=82.0,
            confidence_reason="Confidence is stable",
            scoring_version="test",
            decision_policy_version="test",
            explanation_version="test",
            explanation="Recommended because test fixture",
            score_breakdown=RecommendationScoreBreakdown(
                ranking_score=0.8,
                ielts_fit_score=1.0,
                completeness_score=0.9,
                weights_used={"ranking": 0.5},
                contributions={"ranking": 0.4},
                effective_rank_used=42,
                effective_rank_source="AGGREGATED",
                rules_passed=["country=United Kingdom"],
            ),
            aggregation_method_version="rank_agg_v1",
            metadata=metadata or {},
        )

    def _build_service_item(
        self,
        university_name: str,
        *,
        matching_score: float,
        action: str,
        risk: str,
        strategy: str | None = None,
        reason: str | None = None,
    ) -> dict:
        return {
            "universityName": university_name,
            "matchingScore": matching_score,
            "decisionOutput": {
                "decisionAction": action,
                "decisionReason": reason or f"{university_name} reason",
            },
            "decisionStrategy": {
                "primaryStrategy": strategy or f"{university_name} strategy",
            },
            "admissionComposite": {
                "admissionRisk": risk,
            },
        }

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _sql, _params):
        return None

    def fetchall(self):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)


if __name__ == "__main__":
    unittest.main()
