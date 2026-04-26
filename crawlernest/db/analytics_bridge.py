from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


SOURCE_NAME_MAP = {
    "QS": "QS World University Rankings",
    "THE": "Times Higher Education World University Rankings",
    "ARWU": "Academic Ranking of World Universities",
}

AGGREGATION_METHOD_VERSION = "legacy_single_source_v1"


@dataclass(frozen=True)
class AnalyticsBridgeSummary:
    ranking_source_count: int
    canonical_university_count: int
    canonical_university_link_count: int
    ranking_record_count: int
    aggregation_run_id: int
    aggregated_rankings_count: int
    latest_view_count: int


def sync_legacy_rankings_to_analytics(
    conn: Any,
    ranking_year: int,
    source_code: str = "QS",
    universe_type: str = "global",
    universe_key: str = "global",
) -> AnalyticsBridgeSummary:
    """Sync legacy warehouse.rankings rows into analytics-ready native tables.

    The bridge is intentionally idempotent: re-running for the same
    source/year/universe updates deterministic rows instead of duplicating them.
    """
    source_code = str(source_code or "QS").strip().upper()
    universe_type = _normalize_scope(universe_type, default="global")
    universe_key = _normalize_scope(universe_key, default="global")
    source_name = SOURCE_NAME_MAP.get(source_code, source_code)
    run_label = f"legacy_bridge_{ranking_year}_{source_code.lower()}_{universe_type}_{universe_key}"
    config_json = {
        "source": source_code,
        "method": "single_source_passthrough",
        "seeded_from": "warehouse.rankings",
    }

    try:
        with conn.cursor() as cur:
            _ensure_aggregation_run_conflict_target(cur)

            ranking_source_count = _seed_ranking_source(
                cur,
                source_code=source_code,
                source_name=source_name,
                source_version=str(ranking_year),
            )
            canonical_university_count = _seed_canonical_universities(cur)
            canonical_university_link_count = _seed_canonical_university_links(cur)
            ranking_record_count = _sync_ranking_records(
                cur,
                ranking_year=ranking_year,
                source_code=source_code,
                universe_type=universe_type,
                universe_key=universe_key,
            )
            aggregation_run_id = _upsert_aggregation_run(
                cur,
                ranking_year=ranking_year,
                source_code=source_code,
                universe_type=universe_type,
                universe_key=universe_key,
                run_label=run_label,
                config_json=config_json,
                input_record_count=ranking_record_count,
            )
            aggregated_rankings_count = _sync_aggregated_rankings(
                cur,
                ranking_year=ranking_year,
                source_code=source_code,
                universe_type=universe_type,
                universe_key=universe_key,
                aggregation_run_id=aggregation_run_id,
            )
            latest_view_count = _latest_view_count(
                cur,
                ranking_year=ranking_year,
                universe_type=universe_type,
                universe_key=universe_key,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return AnalyticsBridgeSummary(
        ranking_source_count=ranking_source_count,
        canonical_university_count=canonical_university_count,
        canonical_university_link_count=canonical_university_link_count,
        ranking_record_count=ranking_record_count,
        aggregation_run_id=aggregation_run_id,
        aggregated_rankings_count=aggregated_rankings_count,
        latest_view_count=latest_view_count,
    )


def count_analytics_latest_view(
    conn: Any,
    *,
    ranking_year: int,
    universe_type: str = "global",
    universe_key: str = "global",
) -> int:
    with conn.cursor() as cur:
        return _latest_view_count(
            cur,
            ranking_year=ranking_year,
            universe_type=_normalize_scope(universe_type, default="global"),
            universe_key=_normalize_scope(universe_key, default="global"),
        )


def _seed_ranking_source(cur: Any, *, source_code: str, source_name: str, source_version: str) -> int:
    cur.execute(
        """
        INSERT INTO warehouse.ranking_source (
            source_code,
            source_name,
            source_version,
            metadata
        )
        VALUES (
            %s,
            %s,
            %s,
            jsonb_build_object('seeded_from', 'warehouse.rankings')
        )
        ON CONFLICT (source_code) DO UPDATE SET
            source_name = EXCLUDED.source_name,
            source_version = EXCLUDED.source_version,
            is_active = TRUE,
            metadata = COALESCE(warehouse.ranking_source.metadata, '{}'::jsonb)
                || EXCLUDED.metadata
        RETURNING ranking_source_id
        """,
        (source_code, source_name, source_version),
    )
    return int(cur.fetchone()[0])


def _seed_canonical_universities(cur: Any) -> int:
    cur.execute(
        """
        WITH upserted AS (
            INSERT INTO warehouse.canonical_university (
                canonical_slug,
                display_name,
                display_name_normalized,
                country_id,
                city_name,
                website_url,
                metadata
            )
            SELECT
                u.school_slug,
                u.display_name,
                regexp_replace(lower(trim(u.display_name)), '[^a-z0-9]+', ' ', 'g'),
                u.country_id,
                u.city_name,
                u.website_url,
                jsonb_build_object(
                    'seeded_from', 'warehouse.universities',
                    'source_university_id', u.university_id
                )
            FROM warehouse.universities u
            WHERE u.school_slug IS NOT NULL
              AND btrim(u.school_slug) <> ''
              AND u.display_name IS NOT NULL
              AND btrim(u.display_name) <> ''
            ON CONFLICT (canonical_slug) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                display_name_normalized = EXCLUDED.display_name_normalized,
                country_id = COALESCE(EXCLUDED.country_id, warehouse.canonical_university.country_id),
                city_name = COALESCE(EXCLUDED.city_name, warehouse.canonical_university.city_name),
                website_url = COALESCE(EXCLUDED.website_url, warehouse.canonical_university.website_url),
                metadata = COALESCE(warehouse.canonical_university.metadata, '{}'::jsonb)
                    || EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING canonical_university_id
        )
        SELECT COUNT(*) FROM upserted
        """
    )
    return int(cur.fetchone()[0] or 0)


def _seed_canonical_university_links(cur: Any) -> int:
    cur.execute(
        """
        WITH upserted AS (
            INSERT INTO warehouse.canonical_university_link (
                canonical_university_id,
                university_id,
                link_method,
                confidence_score,
                is_primary,
                metadata
            )
            SELECT
                cu.canonical_university_id,
                u.university_id,
                'legacy_bridge',
                1.0000,
                TRUE,
                jsonb_build_object('seeded_from', 'warehouse.universities')
            FROM warehouse.universities u
            JOIN warehouse.canonical_university cu
              ON cu.canonical_slug = u.school_slug
            ON CONFLICT (university_id) DO UPDATE SET
                canonical_university_id = EXCLUDED.canonical_university_id,
                link_method = EXCLUDED.link_method,
                confidence_score = EXCLUDED.confidence_score,
                is_primary = TRUE,
                metadata = COALESCE(warehouse.canonical_university_link.metadata, '{}'::jsonb)
                    || EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING canonical_university_link_id
        )
        SELECT COUNT(*) FROM upserted
        """
    )
    return int(cur.fetchone()[0] or 0)


def _sync_ranking_records(
    cur: Any,
    *,
    ranking_year: int,
    source_code: str,
    universe_type: str,
    universe_key: str,
) -> int:
    cur.execute(
        """
        WITH deduped_rankings AS (
            SELECT DISTINCT ON (
                r.university_id,
                r.ranking_source,
                r.ranking_year,
                r.ranking_type
            )
                r.*
            FROM warehouse.rankings r
            WHERE r.ranking_year = %(ranking_year)s
            ORDER BY
                r.university_id,
                r.ranking_source,
                r.ranking_year,
                r.ranking_type,
                r.rank_start ASC NULLS LAST,
                r.ranking_id DESC
        ),
        upserted AS (
            INSERT INTO warehouse.ranking_record (
                canonical_university_id,
                ranking_source_id,
                ranking_year,
                ranking_type,
                universe_type,
                universe_key,
                rank_position,
                score,
                score_scale,
                source_version,
                source_url,
                metadata,
                run_id,
                updated_at
            )
            SELECT
                cu.canonical_university_id,
                rs.ranking_source_id,
                r.ranking_year,
                COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                %(universe_type)s,
                %(universe_key)s,
                COALESCE(r.rank_start, r.rank_end),
                r.score,
                100,
                r.ranking_year::text,
                r.source_url,
                jsonb_build_object(
                    'seeded_from', 'warehouse.rankings',
                    'legacy_ranking_id', r.ranking_id,
                    'legacy_university_id', r.university_id,
                    'rank_end', r.rank_end,
                    'metrics_json', r.metrics_json
                ),
                %(run_id)s,
                CURRENT_TIMESTAMP
            FROM deduped_rankings r
            JOIN warehouse.universities u
              ON u.university_id = r.university_id
            JOIN warehouse.canonical_university cu
              ON cu.canonical_slug = u.school_slug
            JOIN warehouse.ranking_source rs
              ON rs.source_code = %(source_code)s
            WHERE r.ranking_year = %(ranking_year)s
              AND upper(r.ranking_source) = %(source_code)s
              AND COALESCE(r.rank_start, r.rank_end) IS NOT NULL
            ON CONFLICT (
                canonical_university_id,
                ranking_source_id,
                ranking_year,
                ranking_type,
                universe_type,
                universe_key
            )
            DO UPDATE SET
                rank_position = EXCLUDED.rank_position,
                score = EXCLUDED.score,
                score_scale = EXCLUDED.score_scale,
                source_version = EXCLUDED.source_version,
                source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                metadata = COALESCE(warehouse.ranking_record.metadata, '{}'::jsonb)
                    || EXCLUDED.metadata,
                run_id = EXCLUDED.run_id,
                updated_at = CURRENT_TIMESTAMP
            RETURNING ranking_record_id
        )
        SELECT COUNT(*) FROM upserted
        """,
        {
            "ranking_year": ranking_year,
            "universe_type": universe_type,
            "universe_key": universe_key,
            "run_id": f"legacy_bridge_{ranking_year}_{source_code.lower()}",
            "source_code": source_code,
        },
    )
    return int(cur.fetchone()[0] or 0)


def _ensure_aggregation_run_conflict_target(cur: Any) -> None:
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_runs_run_label
            ON analytics.aggregation_runs(run_label)
            WHERE run_label IS NOT NULL
        """
    )


def _upsert_aggregation_run(
    cur: Any,
    *,
    ranking_year: int,
    source_code: str,
    universe_type: str,
    universe_key: str,
    run_label: str,
    config_json: dict[str, Any],
    input_record_count: int,
) -> int:
    cur.execute(
        """
        INSERT INTO analytics.aggregation_runs (
            run_label,
            ranking_year,
            universe_type,
            universe_key,
            aggregation_method_version,
            status,
            started_at,
            finished_at,
            input_record_count,
            output_record_count,
            config_json,
            notes
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            'finished',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP,
            %s,
            %s,
            %s::jsonb,
            'Auto bridge from warehouse.rankings'
        )
        ON CONFLICT (run_label) WHERE run_label IS NOT NULL
        DO UPDATE SET
            ranking_year = EXCLUDED.ranking_year,
            universe_type = EXCLUDED.universe_type,
            universe_key = EXCLUDED.universe_key,
            aggregation_method_version = EXCLUDED.aggregation_method_version,
            status = 'finished',
            finished_at = CURRENT_TIMESTAMP,
            input_record_count = EXCLUDED.input_record_count,
            output_record_count = EXCLUDED.output_record_count,
            config_json = EXCLUDED.config_json,
            notes = EXCLUDED.notes
        RETURNING aggregation_run_id
        """,
        (
            run_label,
            ranking_year,
            universe_type,
            universe_key,
            AGGREGATION_METHOD_VERSION,
            input_record_count,
            input_record_count,
            json.dumps(config_json, ensure_ascii=False),
        ),
    )
    return int(cur.fetchone()[0])


def _sync_aggregated_rankings(
    cur: Any,
    *,
    ranking_year: int,
    source_code: str,
    universe_type: str,
    universe_key: str,
    aggregation_run_id: int,
) -> int:
    cur.execute(
        """
        WITH source_rows AS (
            SELECT
                rr.canonical_university_id,
                rr.ranking_year,
                rr.universe_type,
                rr.universe_key,
                rr.rank_position,
                rr.score,
                ROW_NUMBER() OVER (
                    ORDER BY rr.rank_position ASC NULLS LAST, rr.canonical_university_id ASC
                )::integer AS display_rank
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs
              ON rs.ranking_source_id = rr.ranking_source_id
            WHERE rr.ranking_year = %s
              AND rr.universe_type = %s
              AND rr.universe_key = %s
              AND rs.source_code = %s
              AND rr.rank_position IS NOT NULL
        ),
        upserted AS (
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
            )
            SELECT
                %s,
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key,
                display_rank,
                COALESCE(score, GREATEST(0, 100 - (rank_position * 2)))::numeric,
                1.0,
                jsonb_build_object(%s, rank_position),
                jsonb_build_object(%s, COALESCE(score, GREATEST(0, 100 - (rank_position * 2)))),
                jsonb_build_object(%s, 1.0),
                %s,
                CURRENT_TIMESTAMP
            FROM source_rows
            ON CONFLICT (
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key,
                aggregation_method_version
            )
            DO UPDATE SET
                aggregation_run_id = EXCLUDED.aggregation_run_id,
                display_rank = EXCLUDED.display_rank,
                composite_score = EXCLUDED.composite_score,
                coverage_ratio = EXCLUDED.coverage_ratio,
                source_ranks_json = EXCLUDED.source_ranks_json,
                source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
                source_weights_used_json = EXCLUDED.source_weights_used_json,
                updated_at = CURRENT_TIMESTAMP
            RETURNING aggregated_ranking_id
        )
        SELECT COUNT(*) FROM upserted
        """,
        (
            ranking_year,
            universe_type,
            universe_key,
            source_code,
            aggregation_run_id,
            source_code,
            source_code,
            source_code,
            AGGREGATION_METHOD_VERSION,
        ),
    )
    return int(cur.fetchone()[0] or 0)


def _latest_view_count(cur: Any, *, ranking_year: int, universe_type: str, universe_key: str) -> int:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM analytics.v_aggregated_rankings_latest
        WHERE ranking_year = %s
          AND universe_type = %s
          AND universe_key = %s
        """,
        (ranking_year, universe_type, universe_key),
    )
    return int(cur.fetchone()[0] or 0)


def _normalize_scope(value: str, *, default: str) -> str:
    text = str(value or "").strip().lower()
    return text or default
