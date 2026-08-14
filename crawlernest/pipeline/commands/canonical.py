"""Canonical seeding and source-ingestion commands for the CrawlerNest pipeline.

Canonical university seeding, alias seeding, legacy ranking backfill, universe
record diagnostics, and the THE and ARWU ingestion paths. These belong together
rather than in separate canonical and source modules because run-the-rankings
and run-arwu-rankings both call seed_canonical_universities and
backfill_qs_ranking_records_from_legacy.

Each handler takes the parsed argparse namespace and returns a process exit
code. :data:`COMMANDS` is what run_pipeline.py merges into its dispatch table.

Imports of the crawler modules are deferred into the functions that use them.
They come from the hyphenated directories that bootstrap_module_paths puts on
sys.path partway through run_pipeline's import, so importing them at module
level would make this file's import order load-bearing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from pipeline.bootstrap import resolve_repo_paths
    from pipeline.utils.postgres import (
        build_multi_source_pipeline as _build_multi_source_pipeline,
        connect_postgres as _connect_postgres,
    )
    from pipeline.utils.schema import ensure_postgres_schema
except ModuleNotFoundError:  # pragma: no cover - package import compatibility
    from ...pipeline.bootstrap import resolve_repo_paths
    from ...pipeline.utils.postgres import (
        build_multi_source_pipeline as _build_multi_source_pipeline,
        connect_postgres as _connect_postgres,
    )
    from ...pipeline.utils.schema import ensure_postgres_schema

#: Git repository root, for the deferred crawler-package imports.
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

#: Same value run_pipeline.py computes for itself, asked for the same way.
_REPO_ROOT, MODULE_ROOT = resolve_repo_paths(str(Path(__file__).resolve().parents[2] / "run_pipeline.py"))


def load_json_payload(path: Path) -> list[Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return rows
    raise ValueError(f"Unsupported payload format in {path}. Expected a JSON array or an object with a 'rows' array.")


def ingest_rankings_payload(
    source: str,
    payload: list[Any],
    ranking_year: int,
    ranking_type: str,
    source_version: Optional[str],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    batch_id: str | None = None,
) -> Any:
    from models import University
    from multi_source.adapters import ARWUAdapter, QSAdapter, THEAdapter

    source_code = str(source or "").strip().upper()
    if source_code == "QS":
        adapter = QSAdapter(ranking_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = [row if isinstance(row, University) else University.from_dict(row) for row in payload]
    elif source_code == "THE":
        adapter = THEAdapter(default_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = payload
    elif source_code == "ARWU":
        adapter = ARWUAdapter(default_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = payload
    else:
        raise ValueError(f"Unsupported source: {source}. Expected one of QS, THE, ARWU.")

    effective_run_id = batch_id or (
        f"{source_code.lower()}-{ranking_type}-{ranking_year}-"
        f"{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        pipeline = _build_multi_source_pipeline(conn)
        standardized = adapter.adapt(adapter_payload)
        return pipeline.ingest_records(
            standardized,
            batch_id=effective_run_id,
            run_label_prefix=f"{source_code.lower()}_payload_ingest",
            ranking_type=ranking_type,
        )
    finally:
        conn.close()


def run_the_rankings_ingestion(
    *,
    ranking_year: int,
    output_dir: Path,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    skip_seed: bool = False,
) -> dict[str, Any]:
    from the_crawler import crawl_the_rankings

    print(f"[the-rankings] crawling THE world rankings for year={ranking_year}...")
    output_file = crawl_the_rankings(year=ranking_year, output_dir=output_dir)
    payload = load_json_payload(output_file)

    print(f"[the-rankings] ingesting {len(payload)} rows into multi-source pipeline...")
    ingest_summary = ingest_rankings_payload(
        source="THE",
        payload=payload,
        ranking_year=ranking_year,
        ranking_type="world",
        source_version=None,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        batch_id=f"the-{ranking_year}",
    )

    aggregated_rows = int(getattr(ingest_summary, "aggregated_row_count", 0) or 0)
    if not skip_seed:
        print("[the-rankings] seeding canonical entities...")
        seed_canonical_universities(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )

        print("[the-rankings] backfilling ranking records...")
        backfill_summary = backfill_qs_ranking_records_from_legacy(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        aggregated_rows = int(backfill_summary.get("aggregated_rows") or aggregated_rows)

    summary = {
        "rows_crawled": len(payload),
        "matched_count": int(getattr(ingest_summary, "matched_count", 0) or 0),
        "unresolved_count": int(getattr(ingest_summary, "unresolved_count", 0) or 0),
        "aggregated_rows": aggregated_rows,
        "output_file": str(output_file),
    }
    print(
        f"[the-rankings] done. matched={summary['matched_count']} "
        f"unresolved={summary['unresolved_count']} aggregated_rows={summary['aggregated_rows']}"
    )
    return summary


def run_arwu_rankings_ingestion(
    *,
    ranking_year: int,
    output_dir: Path,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    skip_seed: bool = False,
) -> dict[str, Any]:
    from arwu_crawler import crawl_arwu_rankings

    print(f"[arwu-rankings] crawling ARWU world rankings for year={ranking_year}...")
    output_file = crawl_arwu_rankings(year=ranking_year, output_dir=output_dir)
    payload = load_json_payload(output_file)

    print(f"[arwu-rankings] ingesting {len(payload)} rows into multi-source pipeline...")
    ingest_summary = ingest_rankings_payload(
        source="ARWU",
        payload=payload,
        ranking_year=ranking_year,
        ranking_type="world",
        source_version=None,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        batch_id=f"arwu-{ranking_year}",
    )

    aggregated_rows = int(getattr(ingest_summary, "aggregated_row_count", 0) or 0)
    if not skip_seed:
        print("[arwu-rankings] seeding canonical entities...")
        seed_canonical_universities(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )

        print("[arwu-rankings] backfilling ranking records...")
        backfill_summary = backfill_qs_ranking_records_from_legacy(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        aggregated_rows = int(backfill_summary.get("aggregated_rows") or aggregated_rows)

    summary = {
        "rows_crawled": len(payload),
        "matched_count": int(getattr(ingest_summary, "matched_count", 0) or 0),
        "unresolved_count": int(getattr(ingest_summary, "unresolved_count", 0) or 0),
        "aggregated_rows": aggregated_rows,
        "output_file": str(output_file),
    }
    print(
        f"[arwu-rankings] done. matched={summary['matched_count']} "
        f"unresolved={summary['unresolved_count']} aggregated_rows={summary['aggregated_rows']}"
    )
    return summary


def validate_global_multi_source(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    ranking_year: Optional[int] = None,
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        with conn.cursor() as cur:
            params: list[Any] = []
            year_clause = ""
            year_clause_agg = ""
            if ranking_year is not None:
                year_clause = "AND rr.ranking_year = %s"
                year_clause_agg = "AND ar.ranking_year = %s"
                params.append(int(ranking_year))

            cur.execute(
                f"""
                SELECT rs.source_code, COUNT(*)::INT
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.universe_type = 'global'
                  AND rr.universe_key = 'global'
                  {year_clause}
                GROUP BY rs.source_code
                ORDER BY rs.source_code
                """,
                tuple(params),
            )
            source_rows = cur.fetchall()
            source_counts = {str(source_code): int(count) for source_code, count in source_rows}

            cur.execute(
                f"""
                SELECT COUNT(*)::INT
                FROM (
                    SELECT rr.canonical_university_id
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.ranking_source rs
                      ON rs.ranking_source_id = rr.ranking_source_id
                    WHERE rr.universe_type = 'global'
                      AND rr.universe_key = 'global'
                      {year_clause}
                    GROUP BY rr.canonical_university_id
                    HAVING COUNT(DISTINCT rs.source_code) > 1
                ) t
                """,
                tuple(params),
            )
            multi_source_canonical_count = int(cur.fetchone()[0] or 0)

            cur.execute(
                f"""
                SELECT COUNT(*)::INT
                FROM analytics.aggregated_rankings ar
                WHERE ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                  {year_clause_agg}
                  AND (
                      SELECT COUNT(*)
                      FROM jsonb_object_keys(ar.source_ranks_json)
                  ) > 1
                """,
                tuple([int(ranking_year)]) if ranking_year is not None else (),
            )
            aggregated_multi_source_rows = int(cur.fetchone()[0] or 0)

        return {
            "ranking_year": ranking_year,
            "universe_type": "global",
            "universe_key": "global",
            "sources_present": {
                source: source_counts.get(source, 0) > 0
                for source in ("QS", "THE", "ARWU")
            },
            "source_row_counts": source_counts,
            "multi_source_canonical_count": multi_source_canonical_count,
            "aggregated_multi_source_rows": aggregated_multi_source_rows,
        }
    finally:
        conn.close()


def _normalize_display_name_for_canonical(display_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(display_name or "").strip().lower())
    return " ".join(normalized.split())


def _slugify_canonical_name(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(display_name or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


def seed_canonical_from_missing_entities(
    *,
    source_code: str,
    ranking_year: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    seeded = 0
    skipped = 0
    failed = 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT raw_name, country_hint
                FROM analytics.missing_entity_log
                WHERE source_code = %s
                  AND COALESCE(raw_name, '') <> ''
                ORDER BY raw_name ASC, country_hint ASC NULLS LAST
                """,
                (source_code,),
            )
            missing_rows = cur.fetchall()

            for raw_name, country_hint in missing_rows:
                display_name = str(raw_name or "").strip()
                if not display_name:
                    skipped += 1
                    continue

                canonical_slug = _slugify_canonical_name(display_name)
                if not canonical_slug:
                    failed += 1
                    continue

                display_name_normalized = _normalize_display_name_for_canonical(display_name)

                cur.execute(
                    """
                    SELECT canonical_university_id
                    FROM warehouse.canonical_university
                    WHERE canonical_slug = %s
                    """,
                    (canonical_slug,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    skipped += 1
                    continue

                country_id = None
                country_hint_text = str(country_hint or "").strip()
                if country_hint_text:
                    cur.execute(
                        """
                        SELECT country_id
                        FROM warehouse.countries
                        WHERE country_name ILIKE %s
                        LIMIT 1
                        """,
                        (country_hint_text,),
                    )
                    country_row = cur.fetchone()
                    if country_row is not None:
                        country_id = int(country_row[0])
                    else:
                        cur.execute(
                            """
                            INSERT INTO warehouse.countries (country_name)
                            VALUES (%s)
                            ON CONFLICT (country_name) DO NOTHING
                            RETURNING country_id
                            """,
                            (country_hint_text,),
                        )
                        inserted_country = cur.fetchone()
                        if inserted_country is not None:
                            country_id = int(inserted_country[0])
                        else:
                            cur.execute(
                                """
                                SELECT country_id
                                FROM warehouse.countries
                                WHERE country_name ILIKE %s
                                LIMIT 1
                                """,
                                (country_hint_text,),
                            )
                            fallback_country = cur.fetchone()
                            if fallback_country is not None:
                                country_id = int(fallback_country[0])

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                        status
                    )
                    VALUES (%s, %s, %s, %s, 'active')
                    ON CONFLICT (canonical_slug) DO NOTHING
                    RETURNING canonical_university_id
                    """,
                    (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                    ),
                )
                inserted_row = cur.fetchone()
                if inserted_row is not None:
                    seeded += 1
                else:
                    skipped += 1

        conn.commit()
        return {
            "seeded": seeded,
            "skipped": skipped,
            "failed": failed,
            "source_code": source_code,
            "ranking_year": ranking_year,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def seed_canonical_universities(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    seeded = 0
    skipped = 0
    failed = 0
    refreshed_years: list[int] = []
    aggregated_rows = 0

    unresolved_sql = """
        SELECT
            u.university_id,
            u.school_slug,
            u.display_name,
            u.country_id,
            u.city_name,
            u.website_url
        FROM warehouse.universities u
        LEFT JOIN warehouse.canonical_university_link cul
          ON cul.university_id = u.university_id
        WHERE cul.university_id IS NULL
        ORDER BY u.university_id ASC
    """

    total_skipped_sql = """
        SELECT COUNT(*)
        FROM warehouse.universities u
        JOIN warehouse.canonical_university_link cul
          ON cul.university_id = u.university_id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(total_skipped_sql)
            skipped = int(cur.fetchone()[0] or 0)

            cur.execute(unresolved_sql)
            unresolved_rows = cur.fetchall()

            for (
                university_id,
                school_slug,
                display_name,
                country_id,
                city_name,
                website_url,
            ) in unresolved_rows:
                normalized_name = _normalize_display_name_for_canonical(str(display_name or ""))

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                        city_name,
                        website_url,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    ON CONFLICT (canonical_slug) DO NOTHING
                    RETURNING canonical_university_id
                    """,
                    (
                        school_slug,
                        display_name,
                        normalized_name,
                        country_id,
                        city_name,
                        website_url,
                    ),
                )
                row = cur.fetchone()
                if row is not None:
                    canonical_university_id = int(row[0])
                else:
                    cur.execute(
                        """
                        SELECT canonical_university_id
                        FROM warehouse.canonical_university
                        WHERE canonical_slug = %s
                        """,
                        (school_slug,),
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        failed += 1
                        continue
                    canonical_university_id = int(existing[0])

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university_link (
                        canonical_university_id,
                        university_id,
                        link_method,
                        confidence_score,
                        is_primary
                    )
                    VALUES (%s, %s, 'seed_canonical', 1.0000, TRUE)
                    ON CONFLICT (university_id) DO NOTHING
                    RETURNING canonical_university_link_id
                    """,
                    (canonical_university_id, university_id),
                )
                linked = cur.fetchone()
                if linked is not None:
                    seeded += 1
                else:
                    skipped += 1

            cur.execute(
                """
                SELECT DISTINCT ranking_year
                FROM warehouse.ranking_record
                WHERE ranking_type = 'world'
                ORDER BY ranking_year
                """
            )
            years = [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

        if years:
            pipeline = _build_multi_source_pipeline(conn)
            aggregated_rows = pipeline._refresh_aggregations(  # type: ignore[attr-defined]
                years,
                ranking_type="world",
                run_label_prefix="seed_canonical",
            )
            refreshed_years = years

        conn.commit()
        return {
            "seeded": seeded,
            "skipped": skipped,
            "failed": failed,
            "years_aggregated": refreshed_years,
            "aggregated_rows": aggregated_rows,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def backfill_qs_ranking_records_from_legacy(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    backfilled = 0
    skipped = 0
    failed = 0
    refreshed_years: list[int] = []
    aggregated_rows = 0
    run_id = (
        "backfill-qs-ranking-records-"
        f"{dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}"
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.ranking_source (source_code, source_name, source_version)
                VALUES ('QS', 'QS World University Rankings', NULL)
                ON CONFLICT (source_code)
                DO UPDATE SET source_name = EXCLUDED.source_name
                RETURNING ranking_source_id
                """
            )
            row = cur.fetchone()
            if row is not None:
                ranking_source_id = int(row[0])
            else:
                cur.execute(
                    """
                    SELECT ranking_source_id
                    FROM warehouse.ranking_source
                    WHERE source_code = 'QS'
                    """
                )
                existing_source = cur.fetchone()
                if existing_source is None:
                    raise RuntimeError("Unable to resolve QS ranking_source_id for backfill.")
                ranking_source_id = int(existing_source[0])

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key,
                        r.rank_start AS rank_position,
                        r.score,
                        r.source_url,
                        COALESCE(r.metrics_json, '{}'::jsonb) AS metadata
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                SELECT COUNT(*)
                FROM candidate_rows
                """
                ,
                (ranking_source_id,),
            )
            total_candidates = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                SELECT COUNT(*)
                FROM candidate_rows c
                JOIN warehouse.ranking_record rr
                  ON rr.canonical_university_id = c.canonical_university_id
                 AND rr.ranking_source_id = c.ranking_source_id
                 AND rr.ranking_year = c.ranking_year
                 AND rr.ranking_type = c.ranking_type
                 AND rr.universe_type = c.universe_type
                 AND rr.universe_key = c.universe_key
                """
                ,
                (ranking_source_id,),
            )
            skipped = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key,
                        r.rank_start AS rank_position,
                        r.score,
                        r.source_url,
                        COALESCE(r.metrics_json, '{}'::jsonb) AS metadata
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                INSERT INTO warehouse.ranking_record (
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_url,
                    metadata,
                    updated_at,
                    run_id
                )
                SELECT
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_url,
                    metadata,
                    CURRENT_TIMESTAMP,
                    %s
                FROM candidate_rows
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
                    source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP,
                    run_id = EXCLUDED.run_id,
                    ingested_at = CURRENT_TIMESTAMP
                """
                ,
                (ranking_source_id, run_id),
            )

            backfilled = max(0, total_candidates - skipped)

            cur.execute(
                """
                SELECT DISTINCT ranking_year
                FROM warehouse.ranking_record
                WHERE ranking_type = 'world'
                ORDER BY ranking_year
                """
            )
            years = [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

        if years:
            pipeline = _build_multi_source_pipeline(conn)
            aggregated_rows = pipeline._refresh_aggregations(  # type: ignore[attr-defined]
                years,
                ranking_type="world",
                run_label_prefix="backfill_qs_ranking_records",
            )
            refreshed_years = years

        conn.commit()
        return {
            "run_id": run_id,
            "backfilled": backfilled,
            "skipped": skipped,
            "failed": failed,
            "years_aggregated": refreshed_years,
            "aggregated_rows": aggregated_rows,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rebuild_universe_records_diagnostic(
    *,
    ranking_year: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    from qs_universe_registry import iter_all_qs_universes

    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM warehouse.rankings r
                JOIN warehouse.canonical_university_link cul
                  ON cul.university_id = r.university_id
                WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                  AND r.ranking_year = %s
                """,
                (ranking_year,),
            )
            legacy_global_count = int(cur.fetchone()[0] or 0)

            universe_statuses: list[dict[str, Any]] = []
            missing_universes: list[str] = []
            for spec in iter_all_qs_universes():
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM warehouse.ranking_record
                    WHERE ranking_year = %s
                      AND universe_type = %s
                      AND universe_key = %s
                    """,
                    (ranking_year, spec.universe_type, spec.universe_key),
                )
                record_count = int(cur.fetchone()[0] or 0)
                label = f"{spec.universe_type}/{spec.universe_key}"
                universe_statuses.append(
                    {
                        "universe_type": spec.universe_type,
                        "universe_key": spec.universe_key,
                        "record_count": record_count,
                    }
                )
                if record_count == 0:
                    print(f"[rebuild] universe {label} has 0 records — marking for re-crawl")
                    missing_universes.append(label)

        return {
            "ranking_year": ranking_year,
            "legacy_global_count": legacy_global_count,
            "missing_universes": missing_universes,
            "universe_statuses": universe_statuses,
        }
    finally:
        conn.close()


def _seed_university_alias(
    *,
    canonical: str,
    alias: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.alias_seed import (  # noqa: E402
        add_university_alias,
        alias_seed_summary_to_dict,
    )

    summary = add_university_alias(
        canonical_name=canonical,
        alias=alias,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return alias_seed_summary_to_dict(summary)


def _cmd_seed_university_alias(args: argparse.Namespace) -> int:
    """Handler for the ``seed-university-alias`` command."""
    try:
        summary = _seed_university_alias(
            canonical=str(args.canonical),
            alias=str(args.alias),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"[seed-university-alias] aborted: {exc}")
        return 1

    print(
        "[seed-university-alias] "
        f"canonical_id={summary['canonical_university_id']} "
        f"created_canonical={'yes' if summary['created_canonical'] else 'no'} "
        f"created_alias={'yes' if summary['created_alias'] else 'no'}"
    )
    print(
        f"[seed-university-alias] canonical={summary['canonical_name']} "
        f"normalized_canonical={summary['normalized_canonical_name']}"
    )
    print(
        f"[seed-university-alias] alias={summary['alias']} "
        f"normalized_alias={summary['normalized_alias']}"
    )
    return 0


def _cmd_seed_canonical(args: argparse.Namespace) -> int:
    """Handler for the ``seed-canonical`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = seed_canonical_universities(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
    )
    print(
        f"[seed-canonical] seeded={summary['seeded']} "
        f"skipped={summary['skipped']} failed={summary['failed']}"
    )
    print(
        f"[seed-canonical] years_aggregated={summary['years_aggregated']} "
        f"aggregated_rows={summary['aggregated_rows']}"
    )
    return 0


def _cmd_seed_canonical_from_missing(args: argparse.Namespace) -> int:
    """Handler for the ``seed-canonical-from-missing`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = seed_canonical_from_missing_entities(
        source_code=str(args.source or "THE").strip().upper(),
        ranking_year=args.ranking_year,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
    )
    print(
        f"[seed-canonical-from-missing] seeded={summary['seeded']} "
        f"skipped={summary['skipped']} failed={summary['failed']}"
    )
    if summary["source_code"] == "THE":
        print("[seed-canonical-from-missing] re-ingesting THE rankings...")
        the_summary = run_the_rankings_ingestion(
            ranking_year=args.ranking_year,
            output_dir=MODULE_ROOT / "crawlernest-kb" / "databases",
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            skip_seed=True,
        )
        print(
            f"[seed-canonical-from-missing] matched={the_summary['matched_count']} "
            f"unresolved={the_summary['unresolved_count']} "
            f"aggregated_rows={the_summary['aggregated_rows']}"
        )
    return 0


def _cmd_backfill_ranking_records(args: argparse.Namespace) -> int:
    """Handler for the ``backfill-ranking-records`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = backfill_qs_ranking_records_from_legacy(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
    )
    print(
        f"[backfill-ranking-records] run_id={summary['run_id']} "
        f"backfilled={summary['backfilled']} skipped={summary['skipped']} failed={summary['failed']}"
    )
    print(
        f"[backfill-ranking-records] years_aggregated={summary['years_aggregated']} "
        f"aggregated_rows={summary['aggregated_rows']}"
    )
    return 0


def _cmd_rebuild_universe_records(args: argparse.Namespace) -> int:
    """Handler for the ``rebuild-universe-records`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = rebuild_universe_records_diagnostic(
        ranking_year=args.ranking_year,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
    )
    print(
        f"[rebuild] legacy global candidate rows for {summary['ranking_year']}: "
        f"{summary['legacy_global_count']}"
    )
    if summary["missing_universes"]:
        print("[rebuild] universes requiring re-crawl:")
        for label in summary["missing_universes"]:
            print(f"- {label}")
    else:
        print("[rebuild] all configured QS universes have ranking_record rows.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_run_the_rankings(args: argparse.Namespace) -> int:
    """Handler for the ``run-the-rankings`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = run_the_rankings_ingestion(
        ranking_year=args.ranking_year,
        output_dir=Path(args.output_dir),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        skip_seed=bool(args.skip_seed),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_run_arwu_rankings(args: argparse.Namespace) -> int:
    """Handler for the ``run-arwu-rankings`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = run_arwu_rankings_ingestion(
        ranking_year=args.ranking_year,
        output_dir=Path(args.output_dir),
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        skip_seed=bool(args.skip_seed),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate_global_multi_source(args: argparse.Namespace) -> int:
    """Handler for the ``validate-global-multi-source`` command."""
    ensure_postgres_schema(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    summary = validate_global_multi_source(
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        ranking_year=args.ranking_year,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


#: Commands this module owns, merged into run_pipeline's dispatch table.
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "seed-university-alias": _cmd_seed_university_alias,
    "seed-canonical": _cmd_seed_canonical,
    "seed-canonical-from-missing": _cmd_seed_canonical_from_missing,
    "backfill-ranking-records": _cmd_backfill_ranking_records,
    "rebuild-universe-records": _cmd_rebuild_universe_records,
    "run-the-rankings": _cmd_run_the_rankings,
    "run-arwu-rankings": _cmd_run_arwu_rankings,
    "validate-global-multi-source": _cmd_validate_global_multi_source,
}
