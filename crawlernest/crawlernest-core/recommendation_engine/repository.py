from __future__ import annotations

import json
from typing import Any, Optional

from .config import RecommendationConfig
from .engine import recommend_universities
from .types import RecommendationCandidate, RecommendationQuery, RecommendationResult


class RecommendationRepository:
    def __init__(self, conn: Any):
        self.conn = conn

    def fetch_candidates(
        self,
        ranking_year: Optional[int] = None,
        country: Optional[str] = None,
    ) -> list[RecommendationCandidate]:
        sql = """
            SELECT
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
                admission_record_count,
                ielts_observation_count
            FROM analytics.v_recommendation_candidates_latest
            WHERE (%s IS NULL OR ranking_year = %s)
              AND (%s IS NULL OR country = %s)
            ORDER BY aggregated_rank NULLS LAST, canonical_university_id
        """
        out: list[RecommendationCandidate] = []
        with self.conn.cursor() as cur:
            cur.execute(sql, (ranking_year, ranking_year, country, country))
            for row in cur.fetchall():
                (
                    canonical_university_id,
                    university_name,
                    country_name,
                    row_year,
                    aggregated_rank,
                    composite_score,
                    coverage_ratio,
                    ielts_min,
                    source_ranks_json,
                    source_scores_json,
                    aggregation_method_version,
                    admission_record_count,
                    ielts_observation_count,
                ) = row
                out.append(
                    RecommendationCandidate(
                        canonical_university_id=int(canonical_university_id),
                        university_name=university_name,
                        country=country_name,
                        ranking_year=row_year,
                        aggregated_rank=int(aggregated_rank) if aggregated_rank is not None else None,
                        aggregated_score=float(composite_score) if composite_score is not None else None,
                        coverage_ratio=float(coverage_ratio or 0.0),
                        ielts_min=float(ielts_min) if ielts_min is not None else None,
                        source_ranks=dict(source_ranks_json or {}),
                        source_scores=dict(source_scores_json or {}),
                        aggregation_method_version=aggregation_method_version,
                        metadata={
                            "admission_record_count": admission_record_count,
                            "ielts_observation_count": ielts_observation_count,
                        },
                    )
                )
        return out

    def create_recommendation_run(
        self,
        query: RecommendationQuery,
        config: RecommendationConfig,
        candidate_count: int,
        run_label: Optional[str] = None,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analytics.recommendation_runs (
                    run_label,
                    recommendation_method_version,
                    ranking_year,
                    preferred_ranking_source,
                    input_candidate_count,
                    query_json,
                    config_json,
                    status
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, 'running')
                RETURNING recommendation_run_id
                """,
                (
                    run_label,
                    config.recommendation_method_version,
                    query.ranking_year,
                    (query.preferred_ranking_source or None),
                    candidate_count,
                    json.dumps(
                        {
                            "country": query.country,
                            "ielts_score": query.ielts_score,
                            "target_rank": query.target_rank,
                            "preferred_ranking_source": query.preferred_ranking_source,
                            "limit": query.limit,
                            "ranking_year": query.ranking_year,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(config.__dict__, ensure_ascii=False),
                ),
            )
            run_id = int(cur.fetchone()[0])
        self.conn.commit()
        return run_id

    def store_results(self, run_id: int, results: list[RecommendationResult]) -> None:
        with self.conn.cursor() as cur:
            for position, result in enumerate(results, start=1):
                cur.execute(
                    """
                    INSERT INTO analytics.recommendation_results (
                        recommendation_run_id,
                        result_position,
                        canonical_university_id,
                        university_name,
                        country,
                        aggregated_rank,
                        ielts_min,
                        matching_score,
                        explanation,
                        score_breakdown_json,
                        aggregation_method_version
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        run_id,
                        position,
                        result.canonical_university_id,
                        result.university_name,
                        result.country,
                        result.aggregated_rank,
                        result.ielts_min,
                        result.matching_score,
                        result.explanation,
                        json.dumps(
                            {
                                "ranking_score": result.score_breakdown.ranking_score,
                                "ielts_fit_score": result.score_breakdown.ielts_fit_score,
                                "completeness_score": result.score_breakdown.completeness_score,
                                "weights_used": result.score_breakdown.weights_used,
                                "effective_rank_used": result.score_breakdown.effective_rank_used,
                                "effective_rank_source": result.score_breakdown.effective_rank_source,
                                "rules_passed": result.score_breakdown.rules_passed,
                            },
                            ensure_ascii=False,
                        ),
                        result.aggregation_method_version,
                    ),
                )
        self.conn.commit()

    def finish_recommendation_run(self, run_id: int, result_count: int, status: str = "finished") -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE analytics.recommendation_runs
                SET status = %s,
                    output_result_count = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE recommendation_run_id = %s
                """,
                (status, result_count, run_id),
            )
        self.conn.commit()

    def run_recommendation_query(
        self,
        query: RecommendationQuery,
        config: RecommendationConfig,
        run_label: Optional[str] = None,
    ) -> list[RecommendationResult]:
        candidates = self.fetch_candidates(ranking_year=query.ranking_year, country=query.country)
        run_id = self.create_recommendation_run(query, config, candidate_count=len(candidates), run_label=run_label)
        try:
            results = recommend_universities(candidates, query, config=config)
            self.store_results(run_id, results)
            self.finish_recommendation_run(run_id, len(results), status="finished")
            return results
        except Exception:
            self.finish_recommendation_run(run_id, 0, status="failed")
            raise
