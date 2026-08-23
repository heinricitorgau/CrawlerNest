from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.models import NormalizedAdmissionRow
from crawlernest_admission_crawler.postgres_driver import get_psycopg2
from crawlernest_admission_crawler.validator import (
    AdmissionStagingValidationResult,
    validate_admission_staging_rows,
)


@dataclass(slots=True)
class AdmissionStagingIngestSummary:
    write_target: str
    mode: str
    target_location: str
    table_name: str
    valid_row_count: int
    invalid_row_count: int
    duplicate_row_count: int
    inserted_row_count: int
    skipped_existing_row_count: int


def write_normalized_admission_rows_to_jsonl(
    rows: list[NormalizedAdmissionRow],
    output_path: Path,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(_row_to_staging_payload(row), ensure_ascii=False) for row in rows]
    serialized = "\n".join(lines)
    if lines:
        serialized += "\n"
    output_path.write_text(serialized, encoding="utf-8")
    return len(rows)


def ingest_admission_staging_file(
    staging_file: Path,
    sqlite_db_file: Path,
    *,
    allow_partial: bool,
    write_target: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    staging_table: str = "admission_staging_records",
) -> AdmissionStagingIngestSummary:
    validation_result = validate_admission_staging_rows(staging_file)
    _ensure_ingestable(validation_result, allow_partial=allow_partial)

    valid_rows = validation_result.valid_rows
    if write_target == "sqlite":
        inserted, skipped = _ingest_to_sqlite(sqlite_db_file, valid_rows)
        return AdmissionStagingIngestSummary(
            write_target="sqlite",
            mode="persistent",
            target_location=str(sqlite_db_file),
            table_name="admission_staging_records",
            valid_row_count=validation_result.summary.valid_row_count,
            invalid_row_count=validation_result.summary.invalid_row_count,
            duplicate_row_count=validation_result.summary.duplicate_row_count,
            inserted_row_count=inserted,
            skipped_existing_row_count=skipped,
        )

    if write_target == "postgres":
        inserted, skipped = _ingest_to_postgres(
            valid_rows,
            table_name=staging_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        return AdmissionStagingIngestSummary(
            write_target="postgres",
            mode="persistent",
            target_location=f"postgresql://{pg_host}:{pg_port}/{pg_database}#{staging_table}",
            table_name=staging_table,
            valid_row_count=validation_result.summary.valid_row_count,
            invalid_row_count=validation_result.summary.invalid_row_count,
            duplicate_row_count=validation_result.summary.duplicate_row_count,
            inserted_row_count=inserted,
            skipped_existing_row_count=skipped,
        )

    raise ValueError(f"Unsupported admission staging write target: {write_target}")


def ingest_summary_to_dict(summary: AdmissionStagingIngestSummary) -> dict[str, Any]:
    return asdict(summary)


def _row_to_staging_payload(row: NormalizedAdmissionRow) -> dict[str, object]:
    payload = asdict(row)
    extracted_at = payload.get("extracted_at")
    if isinstance(extracted_at, datetime):
        payload["extracted_at"] = extracted_at.isoformat()
    deadline = payload.get("application_deadline")
    if isinstance(deadline, (datetime, date)):
        payload["application_deadline"] = deadline.isoformat()
    return payload


def _ensure_ingestable(result: AdmissionStagingValidationResult, *, allow_partial: bool) -> None:
    if not allow_partial and (
        result.summary.invalid_row_count > 0 or result.summary.duplicate_row_count > 0
    ):
        raise ValueError("admission staging file contains invalid or duplicate rows")


def _ingest_to_sqlite(sqlite_db_file: Path, rows: list[dict[str, Any]]) -> tuple[int, int]:
    sqlite_db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_db_file)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admission_staging_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                university_name TEXT NOT NULL,
                normalized_university_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                country TEXT NULL,
                ielts_requirement REAL NULL,
                toefl_requirement INTEGER NULL,
                extracted_at TEXT NOT NULL,
                duolingo_requirement INTEGER NULL,
                gpa_requirement REAL NULL,
                application_deadline TEXT NULL,
                degree_level TEXT NOT NULL DEFAULT 'unknown',
                raw_payload TEXT NULL,
                UNIQUE(source_url, degree_level)
            )
            """
        )
        inserted = 0
        skipped = 0
        for row in rows:
            cur.execute(
                """
                INSERT OR IGNORE INTO admission_staging_records (
                    university_name,
                    normalized_university_name,
                    source_url,
                    country,
                    ielts_requirement,
                    toefl_requirement,
                    extracted_at,
                    duolingo_requirement,
                    gpa_requirement,
                    application_deadline,
                    degree_level,
                    raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["university_name"],
                    row["normalized_university_name"],
                    row["source_url"],
                    row.get("country"),
                    row.get("ielts_requirement"),
                    row.get("toefl_requirement"),
                    row["extracted_at"],
                    row.get("duolingo_requirement"),
                    row.get("gpa_requirement"),
                    row.get("application_deadline"),
                    row.get("degree_level") or "unknown",
                    json.dumps(row.get("raw_payload"), ensure_ascii=False) if row.get("raw_payload") is not None else None,
                ),
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        conn.commit()
        return inserted, skipped
    finally:
        conn.close()


def _ingest_to_postgres(
    rows: list[dict[str, Any]],
    *,
    table_name: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> tuple[int, int]:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        inserted = 0
        skipped = 0
        with conn.cursor() as cur:
            _ensure_postgres_staging_table(cur, table_name=table_name)
            for row in rows:
                cur.execute(
                    f"""
                    INSERT INTO {table_name} (
                        university_name,
                        normalized_university_name,
                        source_url,
                        country,
                        ielts_requirement,
                        toefl_requirement,
                        extracted_at,
                        duolingo_requirement,
                        gpa_requirement,
                        application_deadline,
                        degree_level,
                        raw_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (source_url, degree_level) DO NOTHING
                    RETURNING 1
                    """,
                    (
                        row["university_name"],
                        row["normalized_university_name"],
                        row["source_url"],
                        row.get("country"),
                        row.get("ielts_requirement"),
                        row.get("toefl_requirement"),
                        datetime.fromisoformat(str(row["extracted_at"])),
                        row.get("duolingo_requirement"),
                        row.get("gpa_requirement"),
                        row.get("application_deadline"),
                        row.get("degree_level") or "unknown",
                        json.dumps(row.get("raw_payload"), ensure_ascii=False)
                        if row.get("raw_payload") is not None
                        else None,
                    ),
                )
                if cur.fetchone() is not None:
                    inserted += 1
                else:
                    skipped += 1
        conn.commit()
        return inserted, skipped
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_postgres_staging_table(
    cur: "psycopg2.extensions.cursor",
    *,
    table_name: str,
) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            university_name TEXT NOT NULL,
            normalized_university_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            country TEXT NULL,
            ielts_requirement DOUBLE PRECISION NULL,
            toefl_requirement INTEGER NULL,
            extracted_at TIMESTAMPTZ NOT NULL,
            duolingo_requirement INTEGER NULL,
            gpa_requirement DOUBLE PRECISION NULL,
            application_deadline DATE NULL,
            degree_level TEXT NOT NULL DEFAULT 'unknown',
            raw_payload JSONB NULL,
            UNIQUE (source_url, degree_level)
        )
        """
    )
