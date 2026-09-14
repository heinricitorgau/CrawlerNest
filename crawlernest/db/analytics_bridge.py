from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


SOURCE_NAME_MAP = {
    "QS": "QS World University Rankings",
    "THE": "Times Higher Education World University Rankings",
    "ARWU": "Academic Ranking of World Universities",
}

#: Source importance for rank aggregation. Bound into the aggregation SQL as
#: parameters and reported verbatim in the run's config_json, so what a run says
#: it weighted and what it actually weighted are the same numbers.
#:
#: Only QS carries data today. With one source present the composite is
#: renormalised by the available weight, so these values do not move composite
#: scores or display ranks until THE or ARWU is ingested -- what they do move is
#: coverage_ratio, which is the fraction of configured weight actually behind a
#: row, and is meant to fall when most of the intended evidence is missing.
#:
#: Mirrored by ranking_aggregation.config.default_aggregation_config(), which
#: serves the multi-source path; test_analytics_bridge_weights asserts the two
#: agree.
WEIGHTS = {
    "QS": 0.222,
    "THE": 0.654,
    "ARWU": 0.124,
}

#: Source order used for the SQL parameter triples below. Fixed here rather than
#: relying on dict order at each call site, because a reordering would silently
#: assign THE's weight to QS.
WEIGHT_ORDER = ("QS", "THE", "ARWU")


def _weight_triple() -> tuple[float, ...]:
    return tuple(float(WEIGHTS[source]) for source in WEIGHT_ORDER)


AGGREGATION_METHOD_VERSION = "multi_source_weighted_v1"


@dataclass(frozen=True)
class AnalyticsBridgeSummary:
    ranking_source_count: int
    canonical_university_count: int
    canonical_university_link_count: int
    ranking_record_count: int
    aggregation_run_id: int
    aggregated_rankings_count: int
    latest_view_count: int
    #: Rows for this scope left behind by an earlier run and deleted by this one.
    #: Normally 0. A non-zero value means universities dropped out of the source
    #: data, which is worth seeing rather than silently cleaning up.
    superseded_rankings_removed: int = 0


@dataclass(frozen=True)
class LegacySeedSummary:
    ranking_source_count: int
    canonical_university_count: int
    canonical_university_link_count: int


def seed_legacy_entities(
    conn: Any,
    *,
    ranking_year: int,
    source_code: str = "QS",
) -> LegacySeedSummary:
    """Seed the entities everything downstream needs before it can resolve.

    warehouse.canonical_university has to exist before the multi-source
    resolver loads its profiles, so this runs first in a pipeline run and the
    ranking_record write follows it.
    """
    source_code = str(source_code or "QS").strip().upper()
    source_name = SOURCE_NAME_MAP.get(source_code, source_code)

    try:
        with conn.cursor() as cur:
            ranking_source_count = _seed_ranking_source(
                cur,
                source_code=source_code,
                source_name=source_name,
                source_version=str(ranking_year),
            )
            canonical_university_count = _seed_canonical_universities(cur)
            canonical_university_link_count = _seed_canonical_university_links(cur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return LegacySeedSummary(
        ranking_source_count=ranking_source_count,
        canonical_university_count=canonical_university_count,
        canonical_university_link_count=canonical_university_link_count,
    )


def aggregate_legacy_analytics(
    conn: Any,
    *,
    ranking_year: int,
    source_code: str = "QS",
    universe_type: str = "global",
    universe_key: str = "global",
) -> AnalyticsBridgeSummary:
    """Aggregate whatever warehouse.ranking_record currently holds.

    Reads that table; never writes it. The multi-source pipeline is its only
    writer, so this has to run after the ingest rather than before it.
    """
    source_code = str(source_code or "QS").strip().upper()
    universe_type = _normalize_scope(universe_type, default="global")
    universe_key = _normalize_scope(universe_key, default="global")
    run_label = (
        f"legacy_bridge_{AGGREGATION_METHOD_VERSION}_{ranking_year}_"
        f"{source_code.lower()}_{universe_type}_{universe_key}"
    )
    config_json = {
        "source": source_code,
        "sources": list(WEIGHTS),
        "weights": WEIGHTS,
        "method": AGGREGATION_METHOD_VERSION,
        "normalization": "1.0 / rank_position",
        "missing_source_handling": "renormalize_by_available_weight",
        "seeded_from": "warehouse.ranking_record",
    }

    try:
        with conn.cursor() as cur:
            _ensure_aggregation_run_conflict_target(cur)

            ranking_record_count = _count_ranking_records(
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
                universe_type=universe_type,
                universe_key=universe_key,
                aggregation_run_id=aggregation_run_id,
            )
            superseded_rankings_removed = _prune_superseded_rankings(
                cur,
                ranking_year=ranking_year,
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
        ranking_source_count=0,
        canonical_university_count=0,
        canonical_university_link_count=0,
        ranking_record_count=ranking_record_count,
        aggregation_run_id=aggregation_run_id,
        aggregated_rankings_count=aggregated_rankings_count,
        latest_view_count=latest_view_count,
        superseded_rankings_removed=superseded_rankings_removed,
    )


def sync_legacy_rankings_to_analytics(
    conn: Any,
    ranking_year: int,
    source_code: str = "QS",
    universe_type: str = "global",
    universe_key: str = "global",
) -> AnalyticsBridgeSummary:
    """Seed the legacy entities, then aggregate.

    No longer writes warehouse.ranking_record. That table had two writers with
    two run_id conventions -- this bridge, joining canonical_slug =
    school_slug, and the multi-source pipeline, resolving through the entity
    resolver -- running one after the other in a single pipeline run, each
    undoing part of the other's work. The multi-source pipeline is now its only
    writer, and reads warehouse.rankings through
    multi_source.legacy_source.load_legacy_ranking_records.

    A pipeline run calls seed_legacy_entities and aggregate_legacy_analytics
    directly, with the ingest between them. This wrapper keeps the two-phase
    call available for scripts and tests that do not write in between.

    The bridge stays idempotent: re-running for the same source, year and
    universe updates deterministic rows rather than duplicating them.
    """
    seed = seed_legacy_entities(
        conn,
        ranking_year=ranking_year,
        source_code=source_code,
    )
    aggregated = aggregate_legacy_analytics(
        conn,
        ranking_year=ranking_year,
        source_code=source_code,
        universe_type=universe_type,
        universe_key=universe_key,
    )
    return AnalyticsBridgeSummary(
        ranking_source_count=seed.ranking_source_count,
        canonical_university_count=seed.canonical_university_count,
        canonical_university_link_count=seed.canonical_university_link_count,
        ranking_record_count=aggregated.ranking_record_count,
        aggregation_run_id=aggregated.aggregation_run_id,
        aggregated_rankings_count=aggregated.aggregated_rankings_count,
        latest_view_count=aggregated.latest_view_count,
        superseded_rankings_removed=aggregated.superseded_rankings_removed,
    )


def _count_ranking_records(
    cur: Any,
    *,
    ranking_year: int,
    source_code: str,
    universe_type: str,
    universe_key: str,
) -> int:
    """How many rows this aggregation is working from.

    Replaces the write count the bridge used to report. The number means the
    same thing to the aggregation run -- its input size -- but it is now read
    from the table rather than being the count of rows just written into it.
    """
    cur.execute(
        """
        SELECT COUNT(*)
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs
          ON rs.ranking_source_id = rr.ranking_source_id
        WHERE rr.ranking_year = %(ranking_year)s
          AND rs.source_code = %(source_code)s
          AND rr.universe_type = %(universe_type)s
          AND rr.universe_key = %(universe_key)s
        """,
        {
            "ranking_year": ranking_year,
            "source_code": source_code,
            "universe_type": universe_type,
            "universe_key": universe_key,
        },
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


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
    # A legacy university whose slug canonical was merged into another links to
    # the survivor. _seed_canonical_universities keeps upserting the merged row
    # by slug (status and merged_into survive its metadata ||), so linking by
    # slug alone would undo the merge on every pipeline run.
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
                CASE
                    WHEN cu.status = 'merged' AND cu.metadata ? 'merged_into'
                        THEN (cu.metadata ->> 'merged_into')::bigint
                    ELSE cu.canonical_university_id
                END,
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


def _ensure_aggregation_run_conflict_target(cur: Any) -> None:
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_aggregation_runs_multi_source_bridge_run_label
            ON analytics.aggregation_runs(run_label)
            WHERE run_label IS NOT NULL
              AND aggregation_method_version = 'multi_source_weighted_v1'
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
          AND aggregation_method_version = 'multi_source_weighted_v1'
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
    universe_type: str,
    universe_key: str,
    aggregation_run_id: int,
) -> int:
    cur.execute(
        """
        WITH ranked_source_rows AS (
            SELECT
                rr.canonical_university_id,
                rr.ranking_year,
                rr.universe_type,
                rr.universe_key,
                upper(rs.source_code) AS source_code,
                rr.rank_position::numeric AS rank_position,
                ROW_NUMBER() OVER (
                    PARTITION BY rr.canonical_university_id, upper(rs.source_code)
                    ORDER BY
                        CASE WHEN lower(COALESCE(rr.ranking_type, '')) = 'world' THEN 0 ELSE 1 END,
                        rr.rank_position ASC NULLS LAST,
                        rr.updated_at DESC NULLS LAST,
                        rr.ranking_record_id DESC
                ) AS source_order
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs
              ON rs.ranking_source_id = rr.ranking_source_id
            WHERE rr.ranking_year = %s
              AND rr.universe_type = %s
              AND rr.universe_key = %s
              AND upper(rs.source_code) IN ('QS', 'THE', 'ARWU')
              AND rr.rank_position IS NOT NULL
        ),
        source_rows AS (
            SELECT *
            FROM ranked_source_rows
            WHERE source_order = 1
        ),
        pivoted AS (
            SELECT
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key,
                MAX(rank_position) FILTER (WHERE source_code = 'QS') AS qs_rank,
                MAX(rank_position) FILTER (WHERE source_code = 'THE') AS the_rank,
                MAX(rank_position) FILTER (WHERE source_code = 'ARWU') AS arwu_rank
            FROM source_rows
            GROUP BY
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key
        ),
        scored AS (
            SELECT
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key,
                qs_rank,
                the_rank,
                arwu_rank,
                CASE WHEN qs_rank IS NOT NULL THEN 1.0 / qs_rank ELSE NULL END AS qs_norm,
                CASE WHEN the_rank IS NOT NULL THEN 1.0 / the_rank ELSE NULL END AS the_norm,
                CASE WHEN arwu_rank IS NOT NULL THEN 1.0 / arwu_rank ELSE NULL END AS arwu_norm,
                (
                    CASE WHEN qs_rank IS NOT NULL THEN %s::numeric ELSE 0 END
                    + CASE WHEN the_rank IS NOT NULL THEN %s::numeric ELSE 0 END
                    + CASE WHEN arwu_rank IS NOT NULL THEN %s::numeric ELSE 0 END
                )::numeric AS available_weight
            FROM pivoted
        ),
        aggregated AS (
            SELECT
                canonical_university_id,
                ranking_year,
                universe_type,
                universe_key,
                (
                    (
                        COALESCE(%s::numeric * qs_norm, 0)
                        + COALESCE(%s::numeric * the_norm, 0)
                        + COALESCE(%s::numeric * arwu_norm, 0)
                    ) / NULLIF(available_weight, 0)
                )::numeric(10,6) AS composite_score,
                available_weight::numeric(8,6) AS coverage_ratio,
                jsonb_build_object(
                    'QS', qs_rank,
                    'THE', the_rank,
                    'ARWU', arwu_rank
                ) AS source_ranks_json,
                jsonb_build_object(
                    'QS', qs_norm,
                    'THE', the_norm,
                    'ARWU', arwu_norm
                ) AS source_normalized_scores_json,
                jsonb_build_object(
                    'QS', CASE WHEN qs_rank IS NOT NULL THEN %s::numeric ELSE NULL END,
                    'THE', CASE WHEN the_rank IS NOT NULL THEN %s::numeric ELSE NULL END,
                    'ARWU', CASE WHEN arwu_rank IS NOT NULL THEN %s::numeric ELSE NULL END
                ) AS source_weights_used_json
            FROM scored
            WHERE available_weight > 0
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    ORDER BY composite_score DESC NULLS LAST, canonical_university_id ASC
                )::integer AS display_rank
            FROM aggregated
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
                composite_score,
                coverage_ratio,
                source_ranks_json,
                source_normalized_scores_json,
                source_weights_used_json,
                %s,
                CURRENT_TIMESTAMP
            FROM ranked
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
            # Three triples, in the order they appear above: available_weight,
            # the composite numerator, and source_weights_used_json. They are
            # bound from WEIGHTS rather than written into the SQL so the weights
            # this run *reports* in config_json and the weights it *applies*
            # cannot drift apart -- they are now the same object.
            *_weight_triple(),
            *_weight_triple(),
            *_weight_triple(),
            aggregation_run_id,
            AGGREGATION_METHOD_VERSION,
        ),
    )
    return int(cur.fetchone()[0] or 0)


def _prune_superseded_rankings(
    cur: Any,
    *,
    ranking_year: int,
    universe_type: str,
    universe_key: str,
    aggregation_run_id: int,
) -> int:
    """Delete rows in this scope that the current run did not produce.

    The upsert above writes one row per university and stamps it with this run's
    id, but it can only touch universities that are *in* this run. A university
    that was aggregated once and has since dropped out of the source data keeps
    its row, its old rank and its old run id forever.

    That is not merely untidy. ``display_rank`` is assigned by ROW_NUMBER over
    the current run, so a leftover row holds a rank the current run has also
    handed to somebody else -- the live table had 163 duplicated ranks from
    exactly this. ``v_aggregated_rankings_latest`` hides them, because it joins
    on the latest run id, but ``AnalyticsService.getRankingTrends`` reads the
    base table and filters only on ``run.status = 'finished'``. A superseded
    row's run finished perfectly well, so that filter does not exclude it and
    the stale rank is served.

    Deleting is safe and is what the table's shape already implies: the unique
    constraint is on (university, year, universe, method) with no run id, so
    this table is current state, not history. History lives in
    ``analytics.aggregation_runs``. Nothing carries a foreign key to
    ``aggregated_ranking_id``.

    Scoped to one year, universe and method version, so a run cannot delete
    another scope's rows or another method's parallel output.
    """
    cur.execute(
        """
        DELETE FROM analytics.aggregated_rankings
        WHERE ranking_year = %s
          AND universe_type = %s
          AND universe_key = %s
          AND aggregation_method_version = %s
          AND aggregation_run_id IS DISTINCT FROM %s
        """,
        (
            ranking_year,
            universe_type,
            universe_key,
            AGGREGATION_METHOD_VERSION,
            aggregation_run_id,
        ),
    )
    return int(cur.rowcount or 0)


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
