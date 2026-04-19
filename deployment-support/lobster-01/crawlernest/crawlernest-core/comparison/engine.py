from __future__ import annotations

from statistics import mean
from typing import Any, Iterable, Optional, Sequence

from recommendation_engine.types import RecommendationCandidate

SOURCE_ORDER = ("QS", "THE", "ARWU")
MISSING_RANK = 10**9
MISSING_SCORE = float(10**9)
MISSING_SOURCE_PENALTY = 200.0


class UniversityComparisonEngine:
    def compare(self, universities: Sequence[RecommendationCandidate]) -> dict[str, Any]:
        rows = list(universities)
        if len(rows) < 2:
            raise ValueError("At least two universities are required for comparison.")

        ordered = sorted(rows, key=self._ordering_key)
        top_key = self._ordering_key(ordered[0])
        tied_winners = [row for row in ordered if self._ordering_key(row) == top_key]
        winner = ordered[0] if len(tied_winners) == 1 else None

        university_map = {row.university_name: self._serialize_university(row) for row in ordered}
        ranking = self._build_ranking_dimension(ordered)
        ielts = self._build_ielts_dimension(ordered)
        completeness = self._build_completeness_dimension(ordered)
        sources = {
            source: self._build_source_dimension(ordered, source)
            for source in SOURCE_ORDER
        }

        decision_factors = [
            ranking["explanation"],
            ielts["explanation"],
            completeness["explanation"],
            *(sources[source]["explanation"] for source in SOURCE_ORDER),
        ]
        summary = self._build_summary(ordered, winner, ranking, ielts, completeness, sources)

        return {
            "better": winner.university_name if winner is not None else "Tie",
            "summary": summary,
            "order": [row.university_name for row in ordered],
            "comparison": {
                "universities": university_map,
                "ranking": ranking,
                "ielts": ielts,
                "data_completeness": completeness,
                "sources": sources,
                "decision_factors": decision_factors,
            },
        }

    def _ordering_key(self, row: RecommendationCandidate) -> tuple[Any, ...]:
        aggregated_rank = self._safe_rank(row.aggregated_rank)
        average_source_rank = self._average_source_rank(row)
        completeness_count = self._completeness_count(row)
        ielts_value = float(row.ielts_min) if row.ielts_min is not None else MISSING_SCORE
        return (
            row.aggregated_rank is None,
            aggregated_rank,
            average_source_rank >= MISSING_SCORE,
            average_source_rank,
            row.ielts_min is None,
            ielts_value,
            -completeness_count,
            (row.university_name or "").lower(),
            row.canonical_university_id,
        )

    def _build_summary(
        self,
        ordered: Sequence[RecommendationCandidate],
        winner: Optional[RecommendationCandidate],
        ranking: dict[str, Any],
        ielts: dict[str, Any],
        completeness: dict[str, Any],
        sources: dict[str, dict[str, Any]],
    ) -> str:
        if winner is None:
            return (
                "No single university is deterministically ahead because the compared schools are tied on "
                "the configured comparison order."
            )

        runner_up = ordered[1]
        if ranking["winner"] == winner.university_name:
            return ranking["explanation"]
        if any(source_data["winner"] == winner.university_name for source_data in sources.values()):
            return (
                f"{winner.university_name} edges ahead of {runner_up.university_name} because aggregated rank does not "
                f"separate them, but its per-source rankings are stronger."
            )
        if ielts["winner"] == winner.university_name:
            return (
                f"{winner.university_name} is preferred over {runner_up.university_name} because ranking is tied or "
                f"incomplete, and it has the lower IELTS requirement."
            )
        if completeness["winner"] == winner.university_name:
            return (
                f"{winner.university_name} is preferred over {runner_up.university_name} because ranking is tied or "
                f"incomplete, and it has more complete evidence across ranking and admission fields."
            )
        return (
            f"{winner.university_name} is the deterministic winner after applying aggregated rank, source ranks, "
            f"IELTS requirement, and data completeness in order."
        )

    def _build_ranking_dimension(self, universities: Sequence[RecommendationCandidate]) -> dict[str, Any]:
        values = {row.university_name: row.aggregated_rank for row in universities}
        available = [row for row in universities if row.aggregated_rank is not None]
        if not available:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": "Aggregated ranking is missing for all compared universities, so ranking cannot separate them.",
            }

        best_rank = min(int(row.aggregated_rank) for row in available if row.aggregated_rank is not None)
        winners = [row.university_name for row in available if int(row.aggregated_rank) == best_rank]
        if len(available) == 1:
            only = available[0]
            missing_names = [row.university_name for row in universities if row.aggregated_rank is None]
            return {
                "values": values,
                "winner": only.university_name,
                "explanation": (
                    f"{only.university_name} has aggregated rank #{only.aggregated_rank}, while "
                    f"{', '.join(missing_names)} has no aggregated rank data."
                ),
            }
        if len(winners) > 1:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": (
                    f"{' and '.join(winners)} share the best aggregated rank at #{best_rank}, so aggregated ranking "
                    f"does not separate them."
                ),
            }

        winner_name = winners[0]
        runner_up = sorted(
            (row for row in available if row.university_name != winner_name),
            key=lambda row: int(row.aggregated_rank or MISSING_RANK),
        )[0]
        rank_gap = int(runner_up.aggregated_rank) - best_rank
        return {
            "values": values,
            "winner": winner_name,
            "explanation": (
                f"{winner_name} ranks #{best_rank} overall versus {runner_up.university_name} at "
                f"#{runner_up.aggregated_rank}, giving it a {rank_gap}-place aggregated ranking advantage."
            ),
        }

    def _build_ielts_dimension(self, universities: Sequence[RecommendationCandidate]) -> dict[str, Any]:
        values = {row.university_name: row.ielts_min for row in universities}
        available = [row for row in universities if row.ielts_min is not None]
        if not available:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": "IELTS requirement data is missing for all compared universities.",
            }
        best_requirement = min(float(row.ielts_min) for row in available if row.ielts_min is not None)
        winners = [row.university_name for row in available if float(row.ielts_min) == best_requirement]
        if len(available) == 1:
            only = available[0]
            return {
                "values": values,
                "winner": only.university_name,
                "explanation": (
                    f"{only.university_name} lists IELTS {only.ielts_min}, while at least one compared university "
                    f"is missing IELTS data."
                ),
            }
        if len(winners) > 1:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": (
                    f"{' and '.join(winners)} share the lowest listed IELTS requirement at {best_requirement}, "
                    f"so IELTS does not separate them."
                ),
            }

        winner_name = winners[0]
        runner_up = sorted(
            (row for row in available if row.university_name != winner_name),
            key=lambda row: float(row.ielts_min or MISSING_SCORE),
        )[0]
        gap = round(float(runner_up.ielts_min) - best_requirement, 2)
        return {
            "values": values,
            "winner": winner_name,
            "explanation": (
                f"{winner_name} requires IELTS {best_requirement} versus {runner_up.university_name} at "
                f"{runner_up.ielts_min}, making it more accessible by {gap} band points."
            ),
        }

    def _build_completeness_dimension(self, universities: Sequence[RecommendationCandidate]) -> dict[str, Any]:
        values = {row.university_name: self._completeness_snapshot(row) for row in universities}
        counts = {row.university_name: self._completeness_count(row) for row in universities}
        best_count = max(counts.values())
        winners = [name for name, count in counts.items() if count == best_count]
        if len(winners) > 1:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": "The compared universities have the same level of data completeness in the tracked fields.",
            }
        winner_name = winners[0]
        runner_up_name = sorted(
            (name for name in counts if name != winner_name),
            key=lambda name: (-counts[name], name.lower()),
        )[0]
        return {
            "values": values,
            "winner": winner_name,
            "explanation": (
                f"{winner_name} has {counts[winner_name]} of 5 tracked evidence points available, versus "
                f"{runner_up_name} with {counts[runner_up_name]}, so it has the more complete comparison record."
            ),
        }

    def _build_source_dimension(
        self,
        universities: Sequence[RecommendationCandidate],
        source: str,
    ) -> dict[str, Any]:
        values = {
            row.university_name: self._safe_rank(row.source_ranks.get(source))
            if row.source_ranks.get(source) is not None
            else None
            for row in universities
        }
        available = [(row.university_name, self._safe_rank(row.source_ranks.get(source))) for row in universities if row.source_ranks.get(source) is not None]
        if not available:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": f"{source} rank data is missing for all compared universities.",
            }
        best_rank = min(rank for _, rank in available)
        winners = [name for name, rank in available if rank == best_rank]
        if len(available) == 1:
            return {
                "values": values,
                "winner": available[0][0],
                "explanation": f"Only {available[0][0]} has {source} rank data, so {source} favors it by default.",
            }
        if len(winners) > 1:
            return {
                "values": values,
                "winner": "Tie",
                "explanation": f"{' and '.join(winners)} share the best {source} rank at #{best_rank}.",
            }
        winner_name = winners[0]
        runner_up_name, runner_up_rank = sorted(
            ((name, rank) for name, rank in available if name != winner_name),
            key=lambda item: item[1],
        )[0]
        gap = runner_up_rank - best_rank
        return {
            "values": values,
            "winner": winner_name,
            "explanation": (
                f"{winner_name} is stronger in {source} at #{best_rank} versus {runner_up_name} at "
                f"#{runner_up_rank}, a {gap}-place source advantage."
            ),
        }

    def _serialize_university(self, row: RecommendationCandidate) -> dict[str, Any]:
        return {
            "canonical_university_id": row.canonical_university_id,
            "country": row.country,
            "aggregated_rank": row.aggregated_rank,
            "aggregated_score": row.aggregated_score,
            "ielts_min": row.ielts_min,
            "source_ranks": {source: self._safe_rank(row.source_ranks.get(source)) for source in SOURCE_ORDER if row.source_ranks.get(source) is not None},
            "data_completeness": self._completeness_snapshot(row),
            "aggregation_method_version": row.aggregation_method_version,
        }

    def _completeness_snapshot(self, row: RecommendationCandidate) -> dict[str, Any]:
        available_sources = sum(1 for source in SOURCE_ORDER if row.source_ranks.get(source) is not None)
        return {
            "has_aggregated_rank": row.aggregated_rank is not None,
            "has_ielts_requirement": row.ielts_min is not None,
            "available_source_count": available_sources,
            "source_coverage_ratio": round(available_sources / len(SOURCE_ORDER), 4),
            "coverage_ratio": round(float(row.coverage_ratio or 0.0), 4),
        }

    def _completeness_count(self, row: RecommendationCandidate) -> int:
        snapshot = self._completeness_snapshot(row)
        return (
            int(snapshot["has_aggregated_rank"])
            + int(snapshot["has_ielts_requirement"])
            + int(snapshot["available_source_count"])
        )

    def _average_source_rank(self, row: RecommendationCandidate) -> float:
        available = [self._safe_rank(row.source_ranks.get(source)) for source in SOURCE_ORDER if row.source_ranks.get(source) is not None]
        if not available:
            return MISSING_SCORE
        missing_count = len(SOURCE_ORDER) - len(available)
        return float(mean(available)) + (missing_count * MISSING_SOURCE_PENALTY)

    def _safe_rank(self, value: Optional[Any]) -> Optional[int]:
        if value is None:
            return None
        return int(value)


def compare_universities(
    id1: RecommendationCandidate | Iterable[RecommendationCandidate] | str | int,
    id2: RecommendationCandidate | str | int | None = None,
    *others: RecommendationCandidate | str | int,
    repository: Any = None,
    ranking_year: Optional[int] = None,
) -> dict[str, Any]:
    if id2 is None and repository is None and _looks_like_candidate_iterable(id1):
        return UniversityComparisonEngine().compare(list(id1))

    if repository is None:
        raise ValueError("repository is required when compare_universities is called with identifiers.")

    identifiers = [id1, id2, *others]
    resolved = repository.resolve_universities(
        [identifier for identifier in identifiers if identifier is not None],
        ranking_year=ranking_year,
    )
    return UniversityComparisonEngine().compare(resolved)


def _looks_like_candidate_iterable(value: Any) -> bool:
    if isinstance(value, (str, bytes, int)):
        return False
    try:
        items = list(value)
    except TypeError:
        return False
    return all(isinstance(item, RecommendationCandidate) for item in items)
