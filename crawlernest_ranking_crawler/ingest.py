from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from crawlernest_ranking_crawler.validator import validate_ranking_staging_rows


@dataclass(slots=True)
class RankingStagingIngestSummary:
    staging_file: str
    sqlite_db: str
    table_name: str
    total_rows: int
    valid_row_count: int
    invalid_row_count: int
    duplicate_row_count: int
    inserted_row_count: int
    skipped_existing_row_count: int
    mode: str
    error_samples: list[dict[str, Any]]
    duplicate_samples: list[dict[str, Any]]


def ingest_ranking_staging_file(
    staging_file: Path,
    sqlite_db_path: Path,
    *,
    allow_partial: bool = False,
) -> RankingStagingIngestSummary:
    validation = validate_ranking_staging_rows(staging_file)
    summary = validation.summary

    if not allow_partial and (summary.invalid_row_count > 0 or summary.duplicate_row_count > 0):
        raise ValueError(
            "staging validation failed; rerun after fixing invalid/duplicate rows or pass allow_partial=True"
        )

    sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_db_path)
    try:
        _ensure_table(conn)
        inserted_row_count, skipped_existing_row_count = _insert_rows(conn, validation.valid_rows)
    finally:
        conn.close()

    return RankingStagingIngestSummary(
        staging_file=str(staging_file),
        sqlite_db=str(sqlite_db_path),
        table_name="ranking_staging_records",
        total_rows=summary.total_rows,
        valid_row_count=summary.valid_row_count,
        invalid_row_count=summary.invalid_row_count,
        duplicate_row_count=summary.duplicate_row_count,
        inserted_row_count=inserted_row_count,
        skipped_existing_row_count=skipped_existing_row_count,
        mode="partial" if allow_partial else "strict",
        error_samples=summary.error_samples,
        duplicate_samples=summary.duplicate_samples,
    )


def ingest_summary_to_dict(summary: RankingStagingIngestSummary) -> dict[str, Any]:
    return asdict(summary)


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ranking_staging_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_name TEXT NOT NULL,
            normalized_university_name TEXT NOT NULL,
            source TEXT NOT NULL,
            rank INTEGER NOT NULL,
            year INTEGER NOT NULL,
            source_url TEXT,
            extracted_at TEXT NOT NULL,
            UNIQUE(normalized_university_name, source, year, rank)
        )
        """
    )
    conn.commit()


def _insert_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = 0
    skipped_existing = 0
    cursor = conn.cursor()
    try:
        for row in rows:
            cursor.execute(
                """
                INSERT OR IGNORE INTO ranking_staging_records (
                    university_name,
                    normalized_university_name,
                    source,
                    rank,
                    year,
                    source_url,
                    extracted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["university_name"],
                    row["normalized_university_name"],
                    row["source"],
                    row["rank"],
                    row["year"],
                    row.get("source_url"),
                    row["extracted_at"],
                ),
            )
            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped_existing += 1
        conn.commit()
    finally:
        cursor.close()
    return inserted, skipped_existing
