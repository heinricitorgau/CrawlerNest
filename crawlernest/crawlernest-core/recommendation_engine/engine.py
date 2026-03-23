from __future__ import annotations

from typing import Iterable, Optional

from .config import RecommendationConfig, default_recommendation_config
from .types import (
    RecommendationCandidate,
    RecommendationQuery,
    RecommendationResult,
    RecommendationScoreBreakdown,
)


class RuleBasedRecommender:
    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or default_recommendation_config()

    def recommend(
        self,
        candidates: Iterable[RecommendationCandidate],
        query: RecommendationQuery,
    ) -> list[RecommendationResult]:
        rows = list(candidates)
        if not rows:
            return []

        filtered: list[RecommendationCandidate] = []
        for row in rows:
            if self._passes_hard_constraints(row, query):
                filtered.append(row)

        scored: list[RecommendationResult] = []
        for row in filtered:
            breakdown = self._score_candidate(row, query)
            if breakdown is None:
                continue
            explanation = self._build_explanation(row, query, breakdown)
            scored.append(
                RecommendationResult(
                    canonical_university_id=row.canonical_university_id,
                    university_name=row.university_name,
                    country=row.country,
                    aggregated_rank=row.aggregated_rank,
                    ielts_min=row.ielts_min,
                    matching_score=self._composite_from_breakdown(breakdown),
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                )
            )

        scored.sort(
            key=lambda r: (
                -r.matching_score,
                r.aggregated_rank if r.aggregated_rank is not None else 10**9,
                r.canonical_university_id,
            )
        )
        limit = max(1, min(int(query.limit or 10), self.config.max_limit))
        return scored[:limit]

    def _passes_hard_constraints(self, row: RecommendationCandidate, query: RecommendationQuery) -> bool:
        if query.country:
            if (row.country or "").strip().lower() != query.country.strip().lower():
                return False

        effective_rank, _ = self._choose_effective_rank(row, query)
        if query.target_rank is not None:
            if effective_rank is None or effective_rank > int(query.target_rank):
                return False

        if query.ielts_score is not None:
            if row.ielts_min is None:
                return bool(self.config.allow_missing_ielts_requirement)
            if float(query.ielts_score) + 1e-9 < float(row.ielts_min):
                return False

        return True

    def _score_candidate(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> Optional[RecommendationScoreBreakdown]:
        effective_rank, effective_rank_source = self._choose_effective_rank(row, query)
        ranking_score = self._ranking_score(effective_rank, query)
        ielts_fit_score = self._ielts_fit_score(row.ielts_min, query.ielts_score)
        completeness_score = self._completeness_score(row)

        component_weights = {
            "ranking": max(0.0, float(self.config.ranking_weight)),
            "ielts_fit": max(0.0, float(self.config.ielts_fit_weight)),
            "completeness": max(0.0, float(self.config.completeness_weight)),
        }

        available_scores = {
            "ranking": ranking_score,
            "ielts_fit": ielts_fit_score,
            "completeness": completeness_score,
        }
        used_weights = {
            name: weight
            for name, weight in component_weights.items()
            if weight > 0 and available_scores[name] is not None
        }
        if not used_weights:
            return None

        rules_passed: list[str] = []
        if query.country:
            rules_passed.append(f"country={query.country}")
        if query.target_rank is not None and effective_rank is not None:
            rules_passed.append(f"rank<={query.target_rank} via {effective_rank_source} ({effective_rank})")
        if query.ielts_score is not None and row.ielts_min is not None:
            rules_passed.append(f"IELTS {query.ielts_score} >= required {row.ielts_min}")
        elif query.ielts_score is None:
            rules_passed.append("IELTS filter not applied")

        return RecommendationScoreBreakdown(
            ranking_score=round(ranking_score, 4) if ranking_score is not None else None,
            ielts_fit_score=round(ielts_fit_score, 4) if ielts_fit_score is not None else None,
            completeness_score=round(completeness_score, 4) if completeness_score is not None else None,
            weights_used=used_weights,
            effective_rank_used=effective_rank,
            effective_rank_source=effective_rank_source,
            rules_passed=rules_passed,
        )

    def _composite_from_breakdown(self, breakdown: RecommendationScoreBreakdown) -> float:
        score_map = {
            "ranking": breakdown.ranking_score,
            "ielts_fit": breakdown.ielts_fit_score,
            "completeness": breakdown.completeness_score,
        }
        weighted_sum = 0.0
        weight_sum = 0.0
        for key, weight in breakdown.weights_used.items():
            score = score_map.get(key)
            if score is None or weight <= 0:
                continue
            weighted_sum += weight * score
            weight_sum += weight
        if weight_sum <= 0:
            return 0.0
        return round(weighted_sum / weight_sum, 4)

    def _choose_effective_rank(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> tuple[Optional[int], str]:
        preferred = (query.preferred_ranking_source or "").strip().upper()
        if preferred:
            rank = row.source_ranks.get(preferred)
            if rank is not None:
                return int(rank), preferred
        if row.aggregated_rank is not None:
            return int(row.aggregated_rank), "AGGREGATED"
        return None, preferred or "AGGREGATED"

    def _ranking_score(self, rank_value: Optional[int], query: RecommendationQuery) -> Optional[float]:
        if rank_value is None or rank_value <= 0:
            return None
        cap = max(int(self.config.ranking_rank_cap), int(query.target_rank or 0), rank_value)
        return max(0.0, min(100.0, 100.0 * (cap - rank_value + 1) / cap))

    def _ielts_fit_score(self, requirement: Optional[float], user_ielts: Optional[float]) -> Optional[float]:
        if user_ielts is None:
            return None
        if requirement is None:
            return None
        if user_ielts + 1e-9 < requirement:
            return None
        gap = max(0.0, float(user_ielts) - float(requirement))
        tolerance = max(0.1, float(self.config.ielts_gap_tolerance))
        return max(0.0, 100.0 * (1.0 - min(gap / tolerance, 1.0)))

    def _completeness_score(self, row: RecommendationCandidate) -> Optional[float]:
        if self.config.completeness_requires_ielts and row.ielts_min is None:
            return None
        score = 0.0
        if row.aggregated_rank is not None:
            score += 40.0
        if row.ielts_min is not None:
            score += 30.0
        score += 30.0 * max(0.0, min(1.0, float(row.coverage_ratio or 0.0)))
        return min(100.0, score)

    def _build_explanation(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        breakdown: RecommendationScoreBreakdown,
    ) -> str:
        parts: list[str] = []
        if breakdown.effective_rank_used is not None:
            rank_label = "aggregated rank" if breakdown.effective_rank_source == "AGGREGATED" else f"{breakdown.effective_rank_source} rank"
            parts.append(f"{rank_label} #{breakdown.effective_rank_used}")
        if query.ielts_score is not None and row.ielts_min is not None:
            parts.append(f"IELTS requirement {row.ielts_min} matches profile {query.ielts_score}")
        if row.country:
            parts.append(f"country match: {row.country}")
        parts.append(
            "score breakdown: "
            f"ranking={_fmt_score(breakdown.ranking_score)}, "
            f"ielts_fit={_fmt_score(breakdown.ielts_fit_score)}, "
            f"completeness={_fmt_score(breakdown.completeness_score)}, "
            f"final={self._composite_from_breakdown(breakdown):.2f}"
        )
        return "; ".join(parts)


def recommend_universities(
    candidates: list[RecommendationCandidate],
    query: RecommendationQuery,
    config: Optional[RecommendationConfig] = None,
) -> list[RecommendationResult]:
    return RuleBasedRecommender(config=config).recommend(candidates, query)



def _fmt_score(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
