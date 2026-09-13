from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

from recommendation_engine.types import RecommendationCandidate


class ComparisonRepository:
    def __init__(self, conn: Any):
        self.conn = conn

    def resolve_university(
        self,
        identifier: str | int,
        ranking_year: Optional[int] = None,
    ) -> RecommendationCandidate:
        # Required for the same reason as RecommendationRepository.fetch_candidates:
        # without an edition, a university held in two matched twice and the
        # better-ranked edition's row won, setting its old rank against another
        # university's current one.
        if ranking_year is None:
            raise ValueError("resolve_university needs a ranking_year; resolve the default before calling")
        row_id = self._coerce_identifier(identifier)
        text_value = str(identifier).strip()
        normalized_value = self._normalize_lookup(text_value)
        partial_pattern = f"%{text_value}%"
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    v.canonical_university_id,
                    v.university_name,
                    v.country,
                    v.ranking_year,
                    v.aggregated_rank,
                    v.composite_score,
                    v.coverage_ratio,
                    v.ielts_min,
                    v.source_ranks_json,
                    v.source_scores_json,
                    v.aggregation_method_version,
                    CASE
                        WHEN CAST(%s AS BIGINT) IS NOT NULL AND v.canonical_university_id = CAST(%s AS BIGINT) THEN 0
                        WHEN lower(v.university_name) = lower(%s) THEN 1
                        WHEN regexp_replace(lower(v.university_name), '[^a-z0-9]+', ' ', 'g') = %s THEN 2
                        WHEN lower(v.university_name) LIKE lower(%s) THEN 3
                        ELSE 100
                    END AS match_priority
                FROM analytics.v_recommendation_candidates_latest v
                WHERE v.ranking_year = CAST(%s AS INTEGER)
                  AND (
                      (CAST(%s AS BIGINT) IS NOT NULL AND v.canonical_university_id = CAST(%s AS BIGINT))
                      OR lower(v.university_name) = lower(%s)
                      OR regexp_replace(lower(v.university_name), '[^a-z0-9]+', ' ', 'g') = %s
                      OR lower(v.university_name) LIKE lower(%s)
                  )
                ORDER BY match_priority, v.aggregated_rank NULLS LAST, v.canonical_university_id
                LIMIT 5
                """,
                (
                    row_id,
                    row_id,
                    text_value,
                    normalized_value,
                    partial_pattern,
                    ranking_year,
                    row_id,
                    row_id,
                    text_value,
                    normalized_value,
                    partial_pattern,
                ),
            )
            rows = cur.fetchall()

        if not rows:
            raise ValueError(f"University not found for identifier: {identifier}")

        top_priority = int(rows[0][-1])
        best_matches = [row for row in rows if int(row[-1]) == top_priority]
        unique_ids = {int(row[0]) for row in best_matches}
        if len(unique_ids) > 1:
            labels = ", ".join(str(row[1]) for row in best_matches[:3])
            raise ValueError(f"University identifier is ambiguous: {identifier}. Matches: {labels}")

        return self._row_to_candidate(rows[0][:-1])

    def resolve_universities(
        self,
        identifiers: list[str | int],
        ranking_year: Optional[int] = None,
    ) -> list[RecommendationCandidate]:
        resolved: list[RecommendationCandidate] = []
        seen_ids: set[int] = set()
        for identifier in identifiers:
            candidate = self.resolve_university(identifier, ranking_year=ranking_year)
            if candidate.canonical_university_id in seen_ids:
                continue
            seen_ids.add(candidate.canonical_university_id)
            resolved.append(candidate)
        if len(resolved) < 2:
            raise ValueError("Comparison requires at least two distinct universities.")
        return resolved

    def _row_to_candidate(self, row: tuple[Any, ...]) -> RecommendationCandidate:
        (
            canonical_university_id,
            university_name,
            country,
            ranking_year,
            aggregated_rank,
            composite_score,
            coverage_ratio,
            ielts_min,
            source_ranks_json,
            source_scores_json,
            aggregation_method_version,
        ) = row
        return RecommendationCandidate(
            canonical_university_id=int(canonical_university_id),
            university_name=university_name,
            country=country,
            ranking_year=ranking_year,
            aggregated_rank=int(aggregated_rank) if aggregated_rank is not None else None,
            aggregated_score=float(composite_score) if composite_score is not None else None,
            coverage_ratio=float(coverage_ratio or 0.0),
            ielts_min=float(ielts_min) if ielts_min is not None else None,
            source_ranks={key.upper(): int(value) for key, value in dict(source_ranks_json or {}).items() if value is not None},
            source_scores={key.upper(): float(value) for key, value in dict(source_scores_json or {}).items() if value is not None},
            aggregation_method_version=aggregation_method_version,
        )

    def _coerce_identifier(self, identifier: str | int) -> Optional[int]:
        if isinstance(identifier, int):
            return identifier
        text_value = str(identifier).strip()
        if text_value.isdigit():
            return int(text_value)
        return None

    def _normalize_lookup(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = "".join(
            ch for ch in unicodedata.normalize("NFKD", lowered)
            if not unicodedata.combining(ch)
        )
        lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
        return " ".join(lowered.split())
