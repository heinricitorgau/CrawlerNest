from __future__ import annotations

import json
from typing import Any

from ranking_aggregation.types import RankingRecordInput

from .integrator import IntegrationDiagnostics
from .reviews import MappingReview
from .types import StandardizedRankingRecord, UnifiedRankingRecord


class MultiSourceRepository:
    """
    PostgreSQL repository for multi-source ingestion.
    Expects psycopg2-like connection.
    """

    def __init__(self, conn: Any):
        self.conn = conn

    def upsert_ranking_sources(self, sources: list[tuple[str, str, str | None]]) -> dict[str, int]:
        # (source_code, source_name, source_version)
        source_codes = sorted(set([s[0] for s in sources if s and s[0]]))
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.ranking_source (source_code, source_name, source_version)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_code)
                DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_source.source_version)
                """,
                [(code, name, version) for code, name, version in sources],
            )
            cur.execute(
                """
                SELECT ranking_source_id, source_code
                FROM warehouse.ranking_source
                WHERE source_code = ANY(%s)
                """,
                (source_codes,),
            )
            rows = cur.fetchall()
        self.conn.commit()
        return {str(code): int(source_id) for source_id, code in rows}

    def load_mapping_reviews(self, source_id_map: dict[str, int]) -> dict[tuple[str, str], MappingReview]:
        """
        Read the standing human decisions for the sources in this run.

        Read-only by design: the pipeline never writes warehouse.mapping_review.
        Returns {} when the table is absent so that a database bootstrapped
        before this schema landed still ingests rather than crashing.
        """
        if not source_id_map:
            return {}

        code_by_id = {int(source_id): str(code) for code, source_id in source_id_map.items()}

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'warehouse'
                  AND table_name = 'mapping_review'
                LIMIT 1
                """
            )
            if cur.fetchone() is None:
                return {}

            cur.execute(
                """
                SELECT
                    ranking_source_id,
                    source_entity_id,
                    decision,
                    decided_canonical_university_id,
                    decided_by,
                    note
                FROM warehouse.mapping_review
                WHERE ranking_source_id = ANY(%s)
                """,
                (sorted(code_by_id),),
            )
            rows = cur.fetchall()

        reviews: dict[tuple[str, str], MappingReview] = {}
        for source_id, entity_id, decision, decided_id, decided_by, note in rows:
            source_code = code_by_id.get(int(source_id))
            if source_code is None:
                continue
            review = MappingReview(
                source_code=source_code,
                source_entity_id=str(entity_id),
                decision=str(decision),
                decided_canonical_university_id=None if decided_id is None else int(decided_id),
                decided_by=str(decided_by or "unknown"),
                note=None if note is None else str(note),
            )
            reviews[review.key] = review
        return reviews

    def upsert_source_university_mappings(self, unified_rows: list[UnifiedRankingRecord], source_id_map: dict[str, int]) -> None:
        params: list[tuple[Any, ...]] = []
        for row in unified_rows:
            if row.canonical_university_id is None:
                continue
            ranking_source_id = source_id_map.get(row.source)
            if ranking_source_id is None:
                continue
            params.append(
                (
                    ranking_source_id,
                    row.source_entity_id,
                    row.canonical_university_id,
                    row.matching_method,
                    row.confidence_score,
                    json.dumps(row.metadata, ensure_ascii=False),
                )
            )
        if not params:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.source_university_mapping (
                    ranking_source_id, source_entity_id, canonical_university_id,
                    match_method, confidence_score, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (ranking_source_id, source_entity_id)
                DO UPDATE SET
                    canonical_university_id = EXCLUDED.canonical_university_id,
                    match_method = EXCLUDED.match_method,
                    confidence_score = EXCLUDED.confidence_score,
                    metadata = EXCLUDED.metadata,
                    -- A row this run writes is live by definition; without this
                    -- an entity rejected once could never be reinstated by a
                    -- later confirm or remap.
                    is_active = TRUE,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                params,
            )
        self.conn.commit()

    def deactivate_rejected_mappings(
        self,
        rejected_keys: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        source_id_map: dict[str, int],
    ) -> int:
        """
        Retire the mappings a reviewer threw out.

        upsert_source_university_mappings skips rows whose canonical id is None,
        so a rejected entity is simply never written again and its old row
        survives untouched -- still asserting the match a person just rejected.
        The ranking records are already gone by then, so nothing user-facing is
        wrong, but the mapping table would keep offering the same rejected pair
        up for review forever.

        canonical_university_id is NOT NULL in this table, so the row is
        deactivated rather than blanked.
        """
        params = [
            (source_id_map[source_code], source_entity_id)
            for source_code, source_entity_id in rejected_keys
            if source_code in source_id_map
        ]
        if not params:
            return 0
        deactivated = 0
        with self.conn.cursor() as cur:
            for ranking_source_id, source_entity_id in params:
                cur.execute(
                    """
                    UPDATE warehouse.source_university_mapping
                    SET is_active = FALSE,
                        last_seen_at = CURRENT_TIMESTAMP
                    WHERE ranking_source_id = %s
                      AND source_entity_id = %s
                      AND is_active
                    """,
                    (ranking_source_id, source_entity_id),
                )
                deactivated += max(0, cur.rowcount)
        self.conn.commit()
        return deactivated

    def prune_superseded_records(
        self,
        *,
        ranking_source_id: int,
        ranking_year: int,
        ranking_type: str,
        run_id: str,
    ) -> int:
        """Drop this source's rows for this year that the current run did not write.

        The upsert stamps every row it touches with the run id, but it can only
        touch universities the payload contains. Re-ingesting a smaller or
        corrected payload therefore leaves the ones that dropped out behind, with
        their old rank, forever -- and they are indistinguishable downstream from
        rows the source still publishes.

        This is the same rule the analytics bridge applies to
        analytics.aggregated_rankings, for the same reason: these tables are
        current state, and history lives in the run tables.

        Scoped to one source, year and ranking type, so a run cannot delete
        another source's rows or another year's.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM warehouse.ranking_record
                WHERE ranking_source_id = %s
                  AND ranking_year = %s
                  AND ranking_type = %s
                  AND run_id IS DISTINCT FROM %s
                """,
                (ranking_source_id, ranking_year, ranking_type, run_id),
            )
            removed = int(cur.rowcount or 0)
        self.conn.commit()
        return removed

    def upsert_ranking_records(
        self,
        unified_rows: list[UnifiedRankingRecord],
        source_id_map: dict[str, int],
        run_id: str | None = None,
    ) -> int:
        params: list[tuple[Any, ...]] = []
        for row in unified_rows:
            if row.canonical_university_id is None:
                continue
            ranking_source_id = source_id_map.get(row.source)
            if ranking_source_id is None:
                continue
            params.append(
                (
                    row.canonical_university_id,
                    ranking_source_id,
                    row.year,
                    row.ranking_type,
                    getattr(row, "universe_type", "global"),
                    getattr(row, "universe_key", "global"),
                    row.rank,
                    row.score,
                    row.source_version,
                    row.source_url,
                    json.dumps(row.metadata, ensure_ascii=False),
                    run_id,
                )
            )
        if not params:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.ranking_record (
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_version,
                    source_url,
                    metadata,
                    updated_at,
                    run_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP, %s)
                ON CONFLICT (canonical_university_id, ranking_source_id, ranking_year, ranking_type, universe_type, universe_key)
                DO UPDATE SET
                    universe_type = EXCLUDED.universe_type,
                    universe_key = EXCLUDED.universe_key,
                    rank_position = EXCLUDED.rank_position,
                    score = EXCLUDED.score,
                    source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_record.source_version),
                    source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP,
                    run_id = EXCLUDED.run_id,
                    ingested_at = CURRENT_TIMESTAMP
                """,
                params,
            )
        self.conn.commit()
        return len(params)

    def log_ingestion(self, source_code: str, diagnostics: IntegrationDiagnostics, inserted_count: int, updated_count: int, batch_id: str | None = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analytics.source_ingestion_log (
                    source_code, batch_id, finished_at, records_in,
                    matched_count, unresolved_count, inserted_count, updated_count, details_json
                ) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    source_code,
                    batch_id,
                    diagnostics.total_records,
                    diagnostics.total_records - diagnostics.unresolved_count,
                    diagnostics.unresolved_count,
                    inserted_count,
                    updated_count,
                    json.dumps(
                        {
                            "unique_resolution_keys": diagnostics.unique_resolution_keys,
                            "duplicate_resolution_saves": diagnostics.duplicate_resolution_saves,
                            "by_source_count": diagnostics.by_source_count,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        self.conn.commit()

    def log_missing_entities(self, raw_rows: list[StandardizedRankingRecord], unified_rows: list[UnifiedRankingRecord]) -> None:
        params: list[tuple[Any, ...]] = []
        for raw, unified in zip(raw_rows, unified_rows):
            if unified.canonical_university_id is not None:
                continue
            params.append(
                (
                    raw.source,
                    raw.source_entity_id,
                    raw.university_name,
                    unified.metadata.get("normalized_name") if isinstance(unified.metadata, dict) else None,
                    raw.country_hint,
                    raw.ranking_year,
                    raw.ranking_type,
                    json.dumps({"matching_method": unified.matching_method}, ensure_ascii=False),
                )
            )
        if not params:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO analytics.missing_entity_log (
                    source_code, source_entity_id, raw_name, normalized_name,
                    country_hint, ranking_year, ranking_type, details_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                params,
            )
        self.conn.commit()

    def log_merge_diagnostics(self, diagnostics: IntegrationDiagnostics, batch_id: str | None = None) -> None:
        with self.conn.cursor() as cur:
            for source_code, cnt in diagnostics.by_source_count.items():
                cur.execute(
                    """
                    INSERT INTO analytics.merge_diagnostics (
                        batch_id,
                        source_code,
                        total_records,
                        unique_resolution_keys,
                        duplicate_resolution_saves,
                        avg_candidates,
                        details_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        batch_id,
                        source_code,
                        cnt,
                        diagnostics.unique_resolution_keys,
                        diagnostics.duplicate_resolution_saves,
                        None,
                        json.dumps(
                            {
                                "unresolved_count": diagnostics.unresolved_count,
                                "by_source_count": diagnostics.by_source_count,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
        self.conn.commit()

    def fetch_ranking_inputs(self, years: list[int], ranking_type: str = "world") -> list[RankingRecordInput]:
        if not years:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rr.canonical_university_id,
                    rs.source_code,
                    rr.ranking_year,
                    rr.universe_type,
                    rr.universe_key,
                    rr.rank_position,
                    rr.score,
                    rr.metadata
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.ranking_year = ANY(%s)
                  AND rr.ranking_type = %s
                ORDER BY rr.ranking_year, rr.universe_type, rr.universe_key, rr.canonical_university_id, rs.source_code
                """,
                (years, ranking_type),
            )
            rows = cur.fetchall()
        return [
            RankingRecordInput(
                canonical_university_id=int(canonical_university_id),
                source=str(source_code),
                year=int(ranking_year),
                universe_type=str(universe_type or "global"),
                universe_key=str(universe_key or "global"),
                rank=rank_position,
                score=float(score) if score is not None else None,
                metadata_json=dict(metadata or {}),
            )
            for canonical_university_id, source_code, ranking_year, universe_type, universe_key, rank_position, score, metadata in rows
        ]
