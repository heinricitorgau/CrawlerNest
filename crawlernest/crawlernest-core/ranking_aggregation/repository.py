from __future__ import annotations

import json
from typing import Any

from .config import AggregationConfig
from .types import AggregatedRankingOutput


class RankingAggregationRepository:
    """
    PostgreSQL persistence adapter for ranking aggregation outputs.
    """

    def __init__(self, conn: Any):
        self.conn = conn

    def create_aggregation_run(
        self,
        year: int,
        config: AggregationConfig,
        input_record_count: int,
        run_label: str | None = None,
        notes: str | None = None,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analytics.aggregation_runs (
                    run_label, ranking_year, aggregation_method_version,
                    status, input_record_count, config_json, notes
                ) VALUES (%s, %s, %s, 'running', %s, %s::jsonb, %s)
                RETURNING aggregation_run_id
                """,
                (
                    run_label,
                    year,
                    config.aggregation_method_version,
                    input_record_count,
                    json.dumps(
                        {
                            "source_weights": config.source_weights,
                            "source_score_scales": config.source_score_scales,
                            "source_rank_fallback_max": config.source_rank_fallback_max,
                            "score_rank_blend": config.score_rank_blend,
                            "tie_epsilon": config.tie_epsilon,
                        },
                        ensure_ascii=False,
                    ),
                    notes,
                ),
            )
            run_id = int(cur.fetchone()[0])
        self.conn.commit()
        return run_id

    def upsert_source_weight_config(self, config: AggregationConfig) -> None:
        with self.conn.cursor() as cur:
            for source_code, weight in sorted(config.source_weights.items()):
                cur.execute(
                    """
                    UPDATE analytics.source_weight_config
                    SET weight = %s,
                        is_active = TRUE
                    WHERE aggregation_method_version = %s
                      AND source_code = %s
                      AND effective_from IS NULL
                    """,
                    (weight, config.aggregation_method_version, source_code),
                )
                if cur.rowcount > 0:
                    continue
                cur.execute(
                    """
                    INSERT INTO analytics.source_weight_config (
                        aggregation_method_version, source_code, weight, is_active
                    ) VALUES (%s, %s, %s, TRUE)
                    """,
                    (config.aggregation_method_version, source_code, weight),
                )
        self.conn.commit()

    def upsert_aggregated_rankings(self, run_id: int, outputs: list[AggregatedRankingOutput]) -> None:
        with self.conn.cursor() as cur:
            for row in outputs:
                cur.execute(
                    """
                    INSERT INTO analytics.aggregated_rankings (
                        aggregation_run_id,
                        canonical_university_id,
                        ranking_year,
                        display_rank,
                        composite_score,
                        coverage_ratio,
                        source_ranks_json,
                        source_normalized_scores_json,
                        source_weights_used_json,
                        aggregation_method_version,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (canonical_university_id, ranking_year, aggregation_method_version)
                    DO UPDATE SET
                        aggregation_run_id = EXCLUDED.aggregation_run_id,
                        display_rank = EXCLUDED.display_rank,
                        composite_score = EXCLUDED.composite_score,
                        coverage_ratio = EXCLUDED.coverage_ratio,
                        source_ranks_json = EXCLUDED.source_ranks_json,
                        source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
                        source_weights_used_json = EXCLUDED.source_weights_used_json,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        run_id,
                        row.canonical_university_id,
                        row.year,
                        row.display_rank,
                        row.composite_score,
                        row.coverage_ratio,
                        json.dumps(row.source_ranks, ensure_ascii=False),
                        json.dumps(row.source_normalized_scores, ensure_ascii=False),
                        json.dumps(row.source_weights_used, ensure_ascii=False),
                        row.aggregation_method_version,
                    ),
                )
        self.conn.commit()

    def finish_aggregation_run(self, run_id: int, output_record_count: int, status: str = "finished") -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE analytics.aggregation_runs
                SET status = %s,
                    output_record_count = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE aggregation_run_id = %s
                """,
                (status, output_record_count, run_id),
            )
        self.conn.commit()
