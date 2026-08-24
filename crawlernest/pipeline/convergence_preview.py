from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import psycopg2
except ImportError:  # pragma: no cover - handled by caller
    psycopg2 = None  # type: ignore


@dataclass(slots=True)
class RankingPreviewSummary:
    row_count: int
    source_count: int
    sources: list[str]
    ranking_years: list[int]
    best_rank: int | None
    best_source: str | None
    best_ranking_year: int | None


@dataclass(slots=True)
class AdmissionPreviewSummary:
    row_count: int
    source_url_count: int
    countries: list[str]
    best_ielts_requirement: float | None
    best_toefl_requirement: int | None
    latest_extracted_at: str | None


@dataclass(slots=True)
class ConvergencePreviewRow:
    canonical_university_id: int
    university_display_name: str
    ranking_summary: RankingPreviewSummary | None
    admission_summary: AdmissionPreviewSummary | None
    missing_data: list[str]


def build_convergence_preview(
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    ranking_schema: str = "warehouse",
    ranking_table: str = "ranking_record",
    admission_schema: str = "warehouse",
    admission_table: str = "admission_record",
    limit: int = 50,
) -> list[ConvergencePreviewRow]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for convergence preview")

    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        _ensure_required_table(conn, schema_name=ranking_schema, table_name=ranking_table)
        # ranking_record stores the source as a FK, so the registry it points at
        # is as required as the fact table itself.
        _ensure_required_table(conn, schema_name=ranking_schema, table_name="ranking_source")
        _ensure_required_table(conn, schema_name=admission_schema, table_name=admission_table)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH ranking_rows AS (
                    SELECT
                        rr.canonical_university_id,
                        src.source_code AS source,
                        rr.ranking_year,
                        rr.rank_position
                    FROM {ranking_schema}.{ranking_table} rr
                    JOIN {ranking_schema}.ranking_source src
                      ON src.ranking_source_id = rr.ranking_source_id
                ),
                ranking_summary AS (
                    SELECT
                        canonical_university_id,
                        COUNT(*)::INTEGER AS row_count,
                        COUNT(DISTINCT source)::INTEGER AS source_count,
                        ARRAY_AGG(DISTINCT source ORDER BY source) AS sources,
                        ARRAY_AGG(DISTINCT ranking_year ORDER BY ranking_year) AS ranking_years,
                        MIN(rank_position)::INTEGER AS best_rank
                    FROM ranking_rows
                    GROUP BY canonical_university_id
                ),
                ranking_best AS (
                    SELECT DISTINCT ON (canonical_university_id)
                        canonical_university_id,
                        source AS best_source,
                        ranking_year AS best_ranking_year
                    FROM ranking_rows
                    WHERE rank_position IS NOT NULL
                    ORDER BY canonical_university_id, rank_position ASC, ranking_year DESC, source ASC
                ),
                admission_summary AS (
                    SELECT
                        ar.canonical_university_id,
                        COUNT(*)::INTEGER AS row_count,
                        COUNT(DISTINCT ar.source_url)::INTEGER AS source_url_count,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT ar.country ORDER BY ar.country), NULL) AS countries,
                        MIN(ar.ielts_requirement) AS best_ielts_requirement,
                        MIN(ar.toefl_requirement)::INTEGER AS best_toefl_requirement,
                        MAX(ar.extracted_at) AS latest_extracted_at
                    FROM {admission_schema}.{admission_table} ar
                    WHERE ar.canonical_university_id IS NOT NULL
                    GROUP BY ar.canonical_university_id
                )
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    rs.row_count,
                    rs.source_count,
                    rs.sources,
                    rs.ranking_years,
                    rs.best_rank,
                    rb.best_source,
                    rb.best_ranking_year,
                    ads.row_count,
                    ads.source_url_count,
                    ads.countries,
                    ads.best_ielts_requirement,
                    ads.best_toefl_requirement,
                    ads.latest_extracted_at
                FROM warehouse.canonical_university cu
                LEFT JOIN ranking_summary rs
                    ON rs.canonical_university_id = cu.canonical_university_id
                LEFT JOIN ranking_best rb
                    ON rb.canonical_university_id = cu.canonical_university_id
                LEFT JOIN admission_summary ads
                    ON ads.canonical_university_id = cu.canonical_university_id
                WHERE rs.canonical_university_id IS NOT NULL
                   OR ads.canonical_university_id IS NOT NULL
                ORDER BY
                    CASE
                        WHEN rs.canonical_university_id IS NOT NULL AND ads.canonical_university_id IS NOT NULL THEN 0
                        WHEN rs.canonical_university_id IS NOT NULL THEN 1
                        ELSE 2
                    END ASC,
                    cu.display_name ASC,
                    cu.canonical_university_id ASC
                LIMIT %s
                """,
                (max(1, limit),),
            )
            raw_rows = cur.fetchall()
    finally:
        conn.close()

    return [_row_from_tuple(row) for row in raw_rows]


def convergence_rows_to_dicts(rows: list[ConvergencePreviewRow]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def write_convergence_preview(rows: list[ConvergencePreviewRow], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(convergence_rows_to_dicts(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_terminal_summary(rows: list[ConvergencePreviewRow]) -> dict[str, int]:
    both_count = 0
    ranking_only_count = 0
    admission_only_count = 0
    for row in rows:
        if not row.missing_data:
            both_count += 1
        elif row.missing_data == ["admission"]:
            ranking_only_count += 1
        elif row.missing_data == ["ranking"]:
            admission_only_count += 1
    return {
        "row_count": len(rows),
        "both_count": both_count,
        "ranking_only_count": ranking_only_count,
        "admission_only_count": admission_only_count,
    }


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


def _row_from_tuple(row: tuple[Any, ...]) -> ConvergencePreviewRow:
    canonical_university_id = int(row[0])
    display_name = str(row[1])

    ranking_summary: RankingPreviewSummary | None = None
    if row[2] is not None:
        ranking_summary = RankingPreviewSummary(
            row_count=int(row[2]),
            source_count=int(row[3]),
            sources=[str(item) for item in (row[4] or [])],
            ranking_years=[int(item) for item in (row[5] or [])],
            best_rank=None if row[6] is None else int(row[6]),
            best_source=None if row[7] is None else str(row[7]),
            best_ranking_year=None if row[8] is None else int(row[8]),
        )

    admission_summary: AdmissionPreviewSummary | None = None
    if row[9] is not None:
        admission_summary = AdmissionPreviewSummary(
            row_count=int(row[9]),
            source_url_count=int(row[10]),
            countries=[str(item) for item in (row[11] or [])],
            best_ielts_requirement=None if row[12] is None else float(row[12]),
            best_toefl_requirement=None if row[13] is None else int(row[13]),
            latest_extracted_at=None if row[14] is None else row[14].isoformat(),
        )

    missing_data: list[str] = []
    if ranking_summary is None:
        missing_data.append("ranking")
    if admission_summary is None:
        missing_data.append("admission")

    return ConvergencePreviewRow(
        canonical_university_id=canonical_university_id,
        university_display_name=display_name,
        ranking_summary=ranking_summary,
        admission_summary=admission_summary,
        missing_data=missing_data,
    )
