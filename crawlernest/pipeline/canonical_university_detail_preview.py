from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from crawlernest.pipeline.ranking_scope import (
    DEFAULT_RANKING_SCHEMA,
    DEFAULT_RANKING_TABLE,
    DEFAULT_SCOPE_PARAMS,
    scope_predicate,
)
from crawlernest_ranking_crawler.normalize import normalize_university_name

try:
    import psycopg2
except ImportError:  # pragma: no cover - handled by caller
    psycopg2 = None  # type: ignore


@dataclass(slots=True)
class IdentitySummary:
    canonical_slug: str
    status: str
    alias_count: int
    country_id: int | None
    city_name: str | None
    website_url: str | None
    matched_by: str
    matched_value: str


@dataclass(slots=True)
class RankingSummary:
    row_count: int
    source_count: int
    sources: list[str]
    ranking_years: list[int]
    best_rank: int | None
    best_source: str | None
    best_ranking_year: int | None


@dataclass(slots=True)
class AdmissionSummary:
    row_count: int
    source_url_count: int
    countries: list[str]
    best_ielts_requirement: float | None
    best_toefl_requirement: int | None
    latest_extracted_at: str | None


@dataclass(slots=True)
class DataAvailability:
    has_ranking_data: bool
    has_admission_data: bool
    missing_sections: list[str]


@dataclass(slots=True)
class CanonicalUniversityDetailPreview:
    canonical_university_id: int
    university_display_name: str
    normalized_university_name: str
    aliases: list[str]
    identity_summary: IdentitySummary
    ranking_summary: RankingSummary | None
    admission_summary: AdmissionSummary | None
    data_availability: DataAvailability


def build_canonical_university_detail_preview(
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    canonical_university_id: int | None = None,
    university_name: str | None = None,
    ranking_schema: str = DEFAULT_RANKING_SCHEMA,
    ranking_table: str = DEFAULT_RANKING_TABLE,
    admission_schema: str = "warehouse",
    admission_table: str = "admission_record",
) -> CanonicalUniversityDetailPreview:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for canonical university detail preview")
    if canonical_university_id is None and not str(university_name or "").strip():
        raise ValueError("either canonical_university_id or university_name must be provided")

    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        _ensure_required_table(conn, schema_name="warehouse", table_name="canonical_university")
        _ensure_required_table(conn, schema_name="warehouse", table_name="university_alias")
        _ensure_required_table(conn, schema_name=ranking_schema, table_name=ranking_table)
        _ensure_required_table(conn, schema_name=admission_schema, table_name=admission_table)

        with conn.cursor() as cur:
            identity_row = _resolve_identity_row(
                cur,
                canonical_university_id=canonical_university_id,
                university_name=university_name,
            )
            if identity_row is None:
                lookup_value = str(university_name or canonical_university_id)
                raise RuntimeError(f"canonical university not found for lookup: {lookup_value}")

            (
                resolved_canonical_id,
                display_name,
                display_name_normalized,
                canonical_slug,
                status,
                country_id,
                city_name,
                website_url,
                matched_by,
                matched_value,
            ) = identity_row

            aliases = _load_aliases(cur, canonical_university_id=int(resolved_canonical_id))
            ranking_summary = _load_ranking_summary(
                cur,
                canonical_university_id=int(resolved_canonical_id),
                ranking_schema=ranking_schema,
                ranking_table=ranking_table,
            )
            admission_summary = _load_admission_summary(
                cur,
                canonical_university_id=int(resolved_canonical_id),
                admission_schema=admission_schema,
                admission_table=admission_table,
            )
    finally:
        conn.close()

    missing_sections: list[str] = []
    if ranking_summary is None:
        missing_sections.append("ranking_summary")
    if admission_summary is None:
        missing_sections.append("admission_summary")

    return CanonicalUniversityDetailPreview(
        canonical_university_id=int(resolved_canonical_id),
        university_display_name=str(display_name),
        normalized_university_name=str(display_name_normalized),
        aliases=aliases,
        identity_summary=IdentitySummary(
            canonical_slug=str(canonical_slug),
            status=str(status),
            alias_count=len(aliases),
            country_id=None if country_id is None else int(country_id),
            city_name=None if city_name is None else str(city_name),
            website_url=None if website_url is None else str(website_url),
            matched_by=str(matched_by),
            matched_value=str(matched_value),
        ),
        ranking_summary=ranking_summary,
        admission_summary=admission_summary,
        data_availability=DataAvailability(
            has_ranking_data=ranking_summary is not None,
            has_admission_data=admission_summary is not None,
            missing_sections=missing_sections,
        ),
    )


def detail_preview_to_dict(preview: CanonicalUniversityDetailPreview) -> dict[str, Any]:
    return asdict(preview)


def write_detail_preview(preview: CanonicalUniversityDetailPreview, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(detail_preview_to_dict(preview), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ensure_required_table(
    conn: "psycopg2.extensions.connection",
    *,
    schema_name: str,
    table_name: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            LIMIT 1
            """,
            (schema_name, table_name),
        )
        if cur.fetchone() is None:
            raise RuntimeError(f"required table not found: {schema_name}.{table_name}")


def _resolve_identity_row(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int | None,
    university_name: str | None,
) -> tuple[Any, ...] | None:
    if canonical_university_id is not None:
        cur.execute(
            """
            SELECT
                cu.canonical_university_id,
                cu.display_name,
                cu.display_name_normalized,
                cu.canonical_slug,
                cu.status,
                cu.country_id,
                cu.city_name,
                cu.website_url,
                'canonical_university_id' AS matched_by,
                cu.canonical_university_id::text AS matched_value
            FROM warehouse.canonical_university cu
            WHERE cu.canonical_university_id = %s
            LIMIT 1
            """,
            (canonical_university_id,),
        )
        return cur.fetchone()

    lookup_name = str(university_name or "").strip()
    normalized_lookup = normalize_university_name(lookup_name)

    cur.execute(
        """
        SELECT
            cu.canonical_university_id,
            cu.display_name,
            cu.display_name_normalized,
            cu.canonical_slug,
            cu.status,
            cu.country_id,
            cu.city_name,
            cu.website_url,
            'display_name_normalized' AS matched_by,
            cu.display_name_normalized AS matched_value
        FROM warehouse.canonical_university cu
        WHERE cu.display_name_normalized = %s
        ORDER BY cu.canonical_university_id ASC
        LIMIT 1
        """,
        (normalized_lookup,),
    )
    row = cur.fetchone()
    if row is not None:
        return row

    cur.execute(
        """
        SELECT
            cu.canonical_university_id,
            cu.display_name,
            cu.display_name_normalized,
            cu.canonical_slug,
            cu.status,
            cu.country_id,
            cu.city_name,
            cu.website_url,
            'display_name' AS matched_by,
            cu.display_name AS matched_value
        FROM warehouse.canonical_university cu
        WHERE cu.display_name = %s
        ORDER BY cu.canonical_university_id ASC
        LIMIT 1
        """,
        (lookup_name,),
    )
    row = cur.fetchone()
    if row is not None:
        return row

    cur.execute(
        """
        SELECT
            cu.canonical_university_id,
            cu.display_name,
            cu.display_name_normalized,
            cu.canonical_slug,
            cu.status,
            cu.country_id,
            cu.city_name,
            cu.website_url,
            'alias_normalized' AS matched_by,
            ua.alias_normalized AS matched_value
        FROM warehouse.university_alias ua
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = ua.canonical_university_id
        WHERE ua.alias_normalized = %s
        ORDER BY cu.canonical_university_id ASC, ua.alias_id ASC
        LIMIT 1
        """,
        (normalized_lookup,),
    )
    row = cur.fetchone()
    if row is not None:
        return row

    cur.execute(
        """
        SELECT
            cu.canonical_university_id,
            cu.display_name,
            cu.display_name_normalized,
            cu.canonical_slug,
            cu.status,
            cu.country_id,
            cu.city_name,
            cu.website_url,
            'alias_text' AS matched_by,
            ua.alias_text AS matched_value
        FROM warehouse.university_alias ua
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = ua.canonical_university_id
        WHERE ua.alias_text = %s
        ORDER BY cu.canonical_university_id ASC, ua.alias_id ASC
        LIMIT 1
        """,
        (lookup_name,),
    )
    return cur.fetchone()


def _load_aliases(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int,
) -> list[str]:
    cur.execute(
        """
        SELECT alias_text
        FROM warehouse.university_alias
        WHERE canonical_university_id = %s
        ORDER BY is_primary DESC, is_abbreviation DESC, alias_text ASC
        """,
        (canonical_university_id,),
    )
    return [str(row[0]) for row in cur.fetchall()]


def _load_ranking_summary(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int,
    ranking_schema: str,
    ranking_table: str,
) -> RankingSummary | None:
    scope_sql = scope_predicate("rr", indent=" " * 10)
    cur.execute(
        f"""
        SELECT
            COUNT(*)::INTEGER AS row_count,
            COUNT(DISTINCT src.source_code)::INTEGER AS source_count,
            ARRAY_AGG(DISTINCT src.source_code ORDER BY src.source_code) AS sources,
            ARRAY_AGG(DISTINCT rr.ranking_year ORDER BY rr.ranking_year) AS ranking_years,
            MIN(rr.rank_position)::INTEGER AS best_rank
        FROM {ranking_schema}.{ranking_table} rr
        JOIN warehouse.ranking_source src
          ON src.ranking_source_id = rr.ranking_source_id
        WHERE rr.canonical_university_id = %s
          AND rr.rank_position IS NOT NULL
          AND {scope_sql}
        """,
        (canonical_university_id, *DEFAULT_SCOPE_PARAMS),
    )
    row = cur.fetchone()
    if row is None or int(row[0] or 0) == 0:
        return None

    cur.execute(
        f"""
        SELECT src.source_code, rr.ranking_year
        FROM {ranking_schema}.{ranking_table} rr
        JOIN warehouse.ranking_source src
          ON src.ranking_source_id = rr.ranking_source_id
        WHERE rr.canonical_university_id = %s
          AND rr.rank_position IS NOT NULL
          AND {scope_sql}
        ORDER BY rr.rank_position ASC, rr.ranking_year DESC, src.source_code ASC
        LIMIT 1
        """,
        (canonical_university_id, *DEFAULT_SCOPE_PARAMS),
    )
    best_row = cur.fetchone()
    return RankingSummary(
        row_count=int(row[0]),
        source_count=int(row[1]),
        sources=[str(item) for item in (row[2] or [])],
        ranking_years=[int(item) for item in (row[3] or [])],
        best_rank=None if row[4] is None else int(row[4]),
        best_source=None if best_row is None or best_row[0] is None else str(best_row[0]),
        best_ranking_year=None if best_row is None or best_row[1] is None else int(best_row[1]),
    )


def _load_admission_summary(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int,
    admission_schema: str,
    admission_table: str,
) -> AdmissionSummary | None:
    cur.execute(
        f"""
        SELECT
            COUNT(*)::INTEGER AS row_count,
            COUNT(DISTINCT source_url)::INTEGER AS source_url_count,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT country ORDER BY country), NULL) AS countries,
            MIN(ielts_requirement) AS best_ielts_requirement,
            MIN(toefl_requirement)::INTEGER AS best_toefl_requirement,
            MAX(extracted_at) AS latest_extracted_at
        FROM {admission_schema}.{admission_table}
        WHERE canonical_university_id = %s
        """,
        (canonical_university_id,),
    )
    row = cur.fetchone()
    if row is None or int(row[0] or 0) == 0:
        return None

    return AdmissionSummary(
        row_count=int(row[0]),
        source_url_count=int(row[1]),
        countries=[str(item) for item in (row[2] or [])],
        best_ielts_requirement=None if row[3] is None else float(row[3]),
        best_toefl_requirement=None if row[4] is None else int(row[4]),
        latest_extracted_at=None if row[5] is None else row[5].isoformat(),
    )
