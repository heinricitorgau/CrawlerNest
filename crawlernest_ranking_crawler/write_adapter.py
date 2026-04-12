from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from crawlernest_ranking_crawler.normalize import NormalizedRankingRow

try:
    import psycopg2
except ImportError:  # pragma: no cover - optional dependency in local dev
    psycopg2 = None  # type: ignore[assignment]


@dataclass(slots=True)
class WriteResult:
    write_target: str
    target_location: str
    table_name: str
    inserted_row_count: int
    skipped_existing_row_count: int
    mode: str


class RankingWriteAdapter(Protocol):
    def write_rows(self, rows: list[NormalizedRankingRow]) -> WriteResult:
        ...


@dataclass(slots=True)
class SQLiteRankingWriteAdapter:
    sqlite_db_path: Path
    table_name: str = "ranking_staging_records"

    def write_rows(self, rows: list[NormalizedRankingRow]) -> WriteResult:
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_db_path)
        try:
            _ensure_sqlite_table(conn, self.table_name)
            inserted, skipped_existing = _insert_sqlite_rows(conn, self.table_name, rows)
        finally:
            conn.close()
        return WriteResult(
            write_target="sqlite",
            target_location=str(self.sqlite_db_path),
            table_name=self.table_name,
            inserted_row_count=inserted,
            skipped_existing_row_count=skipped_existing,
            mode="persistent",
        )


@dataclass(slots=True)
class PostgresRankingWriteAdapter:
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    table_name: str = "ranking_staging_records"

    def write_rows(self, rows: list[NormalizedRankingRow]) -> WriteResult:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for postgres write target")

        conn = psycopg2.connect(
            host=self.pg_host,
            port=self.pg_port,
            database=self.pg_database,
            user=self.pg_user,
            password=self.pg_password,
        )
        try:
            inserted, skipped_existing = _insert_postgres_rows(conn, self.table_name, rows)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return WriteResult(
            write_target="postgres",
            target_location=_postgres_target_location(
                host=self.pg_host,
                port=self.pg_port,
                database=self.pg_database,
                table_name=self.table_name,
            ),
            table_name=self.table_name,
            inserted_row_count=inserted,
            skipped_existing_row_count=skipped_existing,
            mode="persistent",
        )


def _ensure_sqlite_table(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
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


def _insert_sqlite_rows(
    conn: sqlite3.Connection,
    table_name: str,
    rows: list[NormalizedRankingRow],
) -> tuple[int, int]:
    inserted = 0
    skipped_existing = 0
    cursor = conn.cursor()
    try:
        for row in rows:
            cursor.execute(
                f"""
                INSERT OR IGNORE INTO {table_name} (
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
                    row.university_name,
                    row.normalized_university_name,
                    row.source,
                    row.rank,
                    row.year,
                    row.source_url,
                    row.extracted_at.isoformat(),
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


def _row_to_payload(row: NormalizedRankingRow) -> dict[str, object]:
    payload = asdict(row)
    extracted_at = payload.get("extracted_at")
    if isinstance(extracted_at, datetime):
        payload["extracted_at"] = extracted_at.isoformat()
    return payload


def _insert_postgres_rows(
    conn: "psycopg2.extensions.connection",
    table_name: str,
    rows: list[NormalizedRankingRow],
) -> tuple[int, int]:
    inserted = 0
    skipped_existing = 0
    with conn.cursor() as cur:
        _ensure_postgres_table(cur, table_name)
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO {table_name} (
                    university_name,
                    normalized_university_name,
                    source,
                    rank,
                    year,
                    source_url,
                    extracted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (normalized_university_name, source, year, rank) DO NOTHING
                RETURNING 1
                """,
                (
                    row.university_name,
                    row.normalized_university_name,
                    row.source,
                    row.rank,
                    row.year,
                    row.source_url,
                    row.extracted_at,
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
            else:
                skipped_existing += 1
    return inserted, skipped_existing


def _ensure_postgres_table(cur: "psycopg2.extensions.cursor", table_name: str) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id BIGSERIAL PRIMARY KEY,
            university_name TEXT NOT NULL,
            normalized_university_name TEXT NOT NULL,
            source TEXT NOT NULL,
            rank INTEGER NOT NULL,
            year INTEGER NOT NULL,
            source_url TEXT NULL,
            extracted_at TIMESTAMPTZ NOT NULL,
            UNIQUE (normalized_university_name, source, year, rank)
        )
        """
    )


def _postgres_target_location(*, host: str, port: int, database: str, table_name: str) -> str:
    return f"postgresql://{host}:{port}/{database}#{table_name}"
