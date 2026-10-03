"""Write resolved admission rows into warehouse.admission_record.

The upsert replaces what the source currently says rather than declining to
touch what it said last time. The previous version used
``ON CONFLICT DO NOTHING``, which meant a page crawled a hundred times stayed
at whatever the first crawl found -- and entry requirements change every year,
so a frozen row is worse than a missing one. This is the same rule
warehouse.ranking_record follows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.models import (
    UNKNOWN_DEGREE_LEVEL,
    WarehouseReadyAdmissionRow,
)
from crawlernest_admission_crawler.postgres_driver import get_psycopg2
from crawlernest_admission_crawler.source_identity import (
    SOURCE_CODE,
    admission_programme_key,
    admission_source_entity_id,
)
from crawlernest_admission_crawler.warehouse_mapper import (
    fetch_mode_for,
    fetched_at_for,
    intake_year_basis_for,
    requirement_scope_for,
)


@dataclass(slots=True)
class WarehouseLandingWriteSummary:
    row_count: int
    inserted_row_count: int
    updated_row_count: int
    before_row_count: int
    after_row_count: int
    target_location: str
    table_name: str
    mode: str


def load_warehouse_preview_rows(preview_file: Path) -> list[WarehouseReadyAdmissionRow]:
    payload = json.loads(preview_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("warehouse preview artifact must be a JSON array")

    rows: list[WarehouseReadyAdmissionRow] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("warehouse preview artifact rows must be JSON objects")
        source_url = str(item["source_url"])
        faculty = str(item["faculty"]).strip() or None if item.get("faculty") else None
        programme_name = str(item["programme_name"]).strip() or None if item.get("programme_name") else None
        intake_year = _optional_int(item.get("intake_year"))
        rows.append(
            WarehouseReadyAdmissionRow(
                university_name=str(item["university_name"]),
                normalized_university_name=str(item["normalized_university_name"]),
                source_url=source_url,
                country=item.get("country"),
                ielts_requirement=_optional_float(item.get("ielts_requirement")),
                toefl_requirement=_optional_int(item.get("toefl_requirement")),
                extracted_at=datetime.fromisoformat(str(item["extracted_at"])),
                source_entity_id=(
                    str(item["source_entity_id"])
                    if item.get("source_entity_id")
                    else admission_source_entity_id(source_url)
                ),
                duolingo_requirement=_optional_int(item.get("duolingo_requirement")),
                gpa_requirement=_optional_float(item.get("gpa_requirement")),
                application_deadline=_optional_date(item.get("application_deadline")),
                degree_level=str(item.get("degree_level") or UNKNOWN_DEGREE_LEVEL),
                canonical_university_id=_optional_int(item.get("canonical_university_id")),
                entity_resolution_status=str(item.get("entity_resolution_status", "unresolved")),
                raw_payload=item.get("raw_payload") if isinstance(item.get("raw_payload"), dict) else None,
                faculty=faculty,
                programme_name=programme_name,
                requirement_scope=requirement_scope_for(
                    faculty=faculty,
                    programme_name=programme_name,
                    declared=item.get("requirement_scope"),
                ),
                intake_year=intake_year,
                intake_year_basis=intake_year_basis_for(intake_year, item.get("intake_year_basis")),
                # The same checks as the staging path, so a hand-edited preview
                # cannot land a live row with no time or a naive timestamp.
                fetched_at=fetched_at_for(item),
                fetch_mode=fetch_mode_for(item),
            )
        )
    return rows


def write_warehouse_landing_rows(
    rows: list[WarehouseReadyAdmissionRow],
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    schema_name: str = "warehouse",
    table_name: str = "admission_record",
) -> WarehouseLandingWriteSummary:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        before_row_count = _count_rows(conn, schema_name=schema_name, table_name=table_name)
        inserted, updated = _upsert_rows(
            conn,
            schema_name=schema_name,
            table_name=table_name,
            rows=rows,
        )
        conn.commit()
        after_row_count = _count_rows(conn, schema_name=schema_name, table_name=table_name)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    verified_inserted = after_row_count - before_row_count
    if verified_inserted < 0:
        raise RuntimeError(
            f"admission row count decreased unexpectedly for {schema_name}.{table_name}: "
            f"before={before_row_count}, after={after_row_count}"
        )
    # Only the inserts move the row count; the updates are what the upsert
    # exists for. Comparing the total written against the delta, as this used
    # to, would fail every run that corrected an existing row.
    if verified_inserted != inserted:
        raise RuntimeError(
            f"admission write summary mismatch for {schema_name}.{table_name}: "
            f"writer_inserted={inserted}, verified_inserted={verified_inserted}, "
            f"before={before_row_count}, after={after_row_count}"
        )

    return WarehouseLandingWriteSummary(
        row_count=len(rows),
        inserted_row_count=inserted,
        updated_row_count=updated,
        before_row_count=before_row_count,
        after_row_count=after_row_count,
        target_location=f"postgresql://{pg_host}:{pg_port}/{pg_database}#{schema_name}.{table_name}",
        table_name=f"{schema_name}.{table_name}",
        mode="persistent",
    )


def warehouse_landing_summary_to_dict(summary: WarehouseLandingWriteSummary) -> dict[str, object]:
    return asdict(summary)


def _upsert_rows(
    conn: "psycopg2.extensions.connection",
    *,
    schema_name: str,
    table_name: str,
    rows: list[WarehouseReadyAdmissionRow],
) -> tuple[int, int]:
    """Insert or replace each row. Returns (inserted, updated).

    The conflict target is the table's natural key: page, degree level,
    programme and intake. Two programmes on one page, or one programme's 2026
    and 2027 intakes, are separate rows; a re-crawl of the same one replaces it.

    Resolution columns are reset along with the rest: the rows are resolved by
    resolve-admission-entities after landing, and a row keeping the previous
    run's source_mapping_id would name a mapping nobody re-checked.

    ``xmax = 0`` is true only for a tuple this statement inserted, which is how
    an upsert reports which branch it took without a second round trip.
    """
    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        _require_table(cur, schema_name=schema_name, table_name=table_name)
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO {schema_name}.{table_name} (
                    source_code,
                    source_entity_id,
                    source_url,
                    university_name,
                    normalized_university_name,
                    country,
                    canonical_university_id,
                    source_mapping_id,
                    entity_resolution_status,
                    degree_level,
                    faculty,
                    programme_name,
                    programme_key,
                    requirement_scope,
                    intake_year,
                    intake_year_basis,
                    ielts_requirement,
                    toefl_requirement,
                    duolingo_requirement,
                    gpa_requirement,
                    application_deadline,
                    raw_payload,
                    fetched_at,
                    fetch_mode,
                    extracted_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s
                )
                ON CONFLICT (source_code, source_entity_id, degree_level, programme_key, intake_year)
                DO UPDATE SET
                    source_url = EXCLUDED.source_url,
                    university_name = EXCLUDED.university_name,
                    normalized_university_name = EXCLUDED.normalized_university_name,
                    country = EXCLUDED.country,
                    canonical_university_id = EXCLUDED.canonical_university_id,
                    source_mapping_id = EXCLUDED.source_mapping_id,
                    entity_resolution_status = EXCLUDED.entity_resolution_status,
                    faculty = EXCLUDED.faculty,
                    programme_name = EXCLUDED.programme_name,
                    requirement_scope = EXCLUDED.requirement_scope,
                    intake_year_basis = EXCLUDED.intake_year_basis,
                    ielts_requirement = EXCLUDED.ielts_requirement,
                    toefl_requirement = EXCLUDED.toefl_requirement,
                    duolingo_requirement = EXCLUDED.duolingo_requirement,
                    gpa_requirement = EXCLUDED.gpa_requirement,
                    application_deadline = EXCLUDED.application_deadline,
                    raw_payload = EXCLUDED.raw_payload,
                    fetched_at = EXCLUDED.fetched_at,
                    fetch_mode = EXCLUDED.fetch_mode,
                    extracted_at = EXCLUDED.extracted_at,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING (xmax = 0) AS was_inserted
                """,
                (
                    SOURCE_CODE,
                    row.source_entity_id or admission_source_entity_id(row.source_url),
                    row.source_url,
                    row.university_name,
                    row.normalized_university_name,
                    row.country,
                    row.canonical_university_id,
                    row.entity_resolution_status,
                    row.degree_level or UNKNOWN_DEGREE_LEVEL,
                    row.faculty,
                    row.programme_name,
                    admission_programme_key(row.faculty, row.programme_name),
                    row.requirement_scope,
                    row.intake_year,
                    row.intake_year_basis,
                    row.ielts_requirement,
                    row.toefl_requirement,
                    row.duolingo_requirement,
                    row.gpa_requirement,
                    row.application_deadline,
                    json.dumps(row.raw_payload, ensure_ascii=False) if row.raw_payload is not None else None,
                    row.fetched_at,
                    row.fetch_mode,
                    row.extracted_at,
                ),
            )
            result = cur.fetchone()
            if result is not None and result[0]:
                inserted += 1
            else:
                updated += 1
    return inserted, updated


def _require_table(
    cur: "psycopg2.extensions.cursor",
    *,
    schema_name: str,
    table_name: str,
) -> None:
    """Fail loudly rather than conjuring a table.

    This used to CREATE TABLE IF NOT EXISTS with its own copy of the DDL. A
    second definition of a table is a second definition to keep in step, and
    the one that loses is whichever the writer creates first on a fresh
    database -- silently, without the columns and constraints the schema file
    would have given it.
    """
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
        raise RuntimeError(
            f"{schema_name}.{table_name} does not exist. Run: "
            "python3 -m crawlernest.run_pipeline bootstrap-postgres"
        )


def _count_rows(
    conn: "psycopg2.extensions.connection",
    *,
    schema_name: str,
    table_name: str,
) -> int:
    with conn.cursor() as cur:
        _require_table(cur, schema_name=schema_name, table_name=table_name)
        cur.execute(f"SELECT COUNT(*) FROM {schema_name}.{table_name}")
        row = cur.fetchone()
    return 0 if row is None else int(row[0])


def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    return date.fromisoformat(text) if text else None


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
