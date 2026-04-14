from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from crawlernest_admission_crawler.models import WarehouseReadyAdmissionRow
from crawlernest_admission_crawler.postgres_driver import get_psycopg2


@dataclass(slots=True)
class WarehouseLandingWriteSummary:
    row_count: int
    inserted_row_count: int
    skipped_existing_row_count: int
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
        rows.append(
            WarehouseReadyAdmissionRow(
                university_name=str(item["university_name"]),
                normalized_university_name=str(item["normalized_university_name"]),
                source_url=str(item["source_url"]),
                country=item.get("country"),
                ielts_requirement=(
                    None if item.get("ielts_requirement") is None else float(item["ielts_requirement"])
                ),
                toefl_requirement=(
                    None if item.get("toefl_requirement") is None else int(item["toefl_requirement"])
                ),
                extracted_at=datetime.fromisoformat(str(item["extracted_at"])),
                canonical_university_id=(
                    None if item.get("canonical_university_id") is None else int(item["canonical_university_id"])
                ),
                entity_resolution_status=str(item.get("entity_resolution_status", "unresolved")),
                raw_payload=item.get("raw_payload") if isinstance(item.get("raw_payload"), dict) else None,
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
    table_name: str = "admission_records_preview",
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
        inserted, skipped_existing = _insert_rows(
            conn,
            schema_name=schema_name,
            table_name=table_name,
            rows=rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return WarehouseLandingWriteSummary(
        row_count=len(rows),
        inserted_row_count=inserted,
        skipped_existing_row_count=skipped_existing,
        target_location=f"postgresql://{pg_host}:{pg_port}/{pg_database}#{schema_name}.{table_name}",
        table_name=f"{schema_name}.{table_name}",
        mode="persistent",
    )


def warehouse_landing_summary_to_dict(summary: WarehouseLandingWriteSummary) -> dict[str, object]:
    return asdict(summary)


def _insert_rows(
    conn: "psycopg2.extensions.connection",
    *,
    schema_name: str,
    table_name: str,
    rows: list[WarehouseReadyAdmissionRow],
) -> tuple[int, int]:
    inserted = 0
    skipped_existing = 0
    with conn.cursor() as cur:
        _ensure_table(cur, schema_name=schema_name, table_name=table_name)
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO {schema_name}.{table_name} (
                    university_name,
                    normalized_university_name,
                    source_url,
                    country,
                    ielts_requirement,
                    toefl_requirement,
                    extracted_at,
                    canonical_university_id,
                    entity_resolution_status,
                    raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (normalized_university_name, source_url) DO NOTHING
                RETURNING 1
                """,
                (
                    row.university_name,
                    row.normalized_university_name,
                    row.source_url,
                    row.country,
                    row.ielts_requirement,
                    row.toefl_requirement,
                    row.extracted_at,
                    row.canonical_university_id,
                    row.entity_resolution_status,
                    json.dumps(row.raw_payload, ensure_ascii=False) if row.raw_payload is not None else None,
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
            else:
                skipped_existing += 1
    return inserted, skipped_existing


def _ensure_table(
    cur: "psycopg2.extensions.cursor",
    *,
    schema_name: str,
    table_name: str,
) -> None:
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
            id BIGSERIAL PRIMARY KEY,
            university_name TEXT NOT NULL,
            normalized_university_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            country TEXT NULL,
            ielts_requirement DOUBLE PRECISION NULL,
            toefl_requirement INTEGER NULL,
            extracted_at TIMESTAMPTZ NOT NULL,
            canonical_university_id BIGINT NULL,
            entity_resolution_status TEXT NOT NULL,
            raw_payload JSONB NULL,
            UNIQUE (normalized_university_name, source_url)
        )
        """
    )
