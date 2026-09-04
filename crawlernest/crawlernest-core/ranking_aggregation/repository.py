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
        universe_type: str,
        universe_key: str,
        config: AggregationConfig,
        input_record_count: int,
        run_label: str | None = None,
        notes: str | None = None,
    ) -> int:
        with self.conn.cursor() as cur:
            # The label is deterministic -- prefix, year, universe -- so a second
            # ingest of the same source and year produces the same one. Inserting
            # blindly made re-ingestion fail on the unique index rather than
            # replace, which meant every correction had to hand-edit run_label
            # before it could run.
            #
            # Reusing the row is what the analytics bridge already does through
            # the same index, so the two writers into this table now behave the
            # same way. The index is a partial one covering
            # multi_source_weighted_v1, which is why the conflict target is
            # written out rather than named.
            cur.execute(
                """
                INSERT INTO analytics.aggregation_runs (
                    run_label, ranking_year, universe_type, universe_key, aggregation_method_version,
                    status, input_record_count, config_json, notes
                ) VALUES (%s, %s, %s, %s, %s, 'running', %s, %s::jsonb, %s)
                ON CONFLICT (run_label)
                    WHERE run_label IS NOT NULL
                      AND aggregation_method_version = 'multi_source_weighted_v1'
                DO UPDATE SET
                    ranking_year = EXCLUDED.ranking_year,
                    universe_type = EXCLUDED.universe_type,
                    universe_key = EXCLUDED.universe_key,
                    status = 'running',
                    started_at = CURRENT_TIMESTAMP,
                    finished_at = NULL,
                    input_record_count = EXCLUDED.input_record_count,
                    output_record_count = 0,
                    config_json = EXCLUDED.config_json,
                    notes = EXCLUDED.notes
                RETURNING aggregation_run_id
                """,
                (
                    run_label,
                    year,
                    universe_type,
                    universe_key,
                    config.aggregation_method_version,
                    input_record_count,
                    json.dumps(
                        {
                            "source_weights": config.source_weights,
                            "source_score_scales": config.source_score_scales,
                            "source_rank_fallback_max": config.source_rank_fallback_max,
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
        """Write one universe's aggregated rows, and retire the ones it no longer has.

        The upsert alone is not enough. A university that loses its last source
        credit -- a reviewer rejects the mapping, the source drops it, the
        resolver re-points it -- simply stops appearing in ``outputs``, and
        without the delete below its previous row survives, still asserting a
        rank from a source that no longer ranks it.

        Two things conspire to hide that. ``aggregation_runs`` rows are keyed by
        run_label, so an ingest with a recurring label reuses the same
        aggregation_run_id; and the row keeps whichever run_id last touched it.
        A stale row therefore carries the *current* run's id, and
        v_aggregated_rankings_latest -- which filters to the latest run -- cannot
        tell it apart from a row that run actually wrote. Found this way: two
        universities kept a THE rank through /api/v1/rankings after the mapping
        that gave it to them was reviewed away.

        The delete is scoped to this universe and this method version, which is
        exactly what one call covers: _refresh_aggregations groups by
        (year, universe_type, universe_key) and aggregates every source at once,
        so ``outputs`` is the complete membership of that universe rather than
        one source's contribution to it. An empty ``outputs`` deletes nothing --
        aggregating no rows is not evidence that a universe is empty.
        """
        if not outputs:
            return

        first = outputs[0]
        kept = [row.canonical_university_id for row in outputs]

        with self.conn.cursor() as cur:
            for row in outputs:
                cur.execute(
                    """
                    INSERT INTO analytics.aggregated_rankings (
                        aggregation_run_id,
                        canonical_university_id,
                        ranking_year,
                        universe_type,
                        universe_key,
                        display_rank,
                        composite_score,
                        coverage_ratio,
                        source_ranks_json,
                        source_normalized_scores_json,
                        source_weights_used_json,
                        aggregation_method_version,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version)
                    DO UPDATE SET
                        aggregation_run_id = EXCLUDED.aggregation_run_id,
                        universe_type = EXCLUDED.universe_type,
                        universe_key = EXCLUDED.universe_key,
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
                        row.universe_type,
                        row.universe_key,
                        row.display_rank,
                        row.composite_score,
                        row.coverage_ratio,
                        json.dumps(row.source_ranks, ensure_ascii=False),
                        json.dumps(row.source_normalized_scores, ensure_ascii=False),
                        json.dumps(row.source_weights_used, ensure_ascii=False),
                        row.aggregation_method_version,
                    ),
                )

            cur.execute(
                """
                DELETE FROM analytics.aggregated_rankings
                 WHERE ranking_year = %s
                   AND universe_type = %s
                   AND universe_key = %s
                   AND aggregation_method_version = %s
                   AND canonical_university_id <> ALL(%s)
                """,
                (
                    first.year,
                    first.universe_type,
                    first.universe_key,
                    first.aggregation_method_version,
                    kept,
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
