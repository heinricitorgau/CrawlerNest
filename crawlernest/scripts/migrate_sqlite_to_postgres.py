#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import Json, execute_values
except ImportError as exc:
    raise SystemExit("psycopg2 is required. Install with `pip install psycopg2-binary`.") from exc


TABLE_MIGRATION_ORDER = [
    "crawl_runs",
    "countries",
    "universities",
    "university_aliases",
    "raw_source_records",
    "rankings",
    "admission_requirements",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate CrawlerNest data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", required=True)
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--truncate-first", action="store_true")
    return parser


def _sqlite_rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    return cur.fetchall()


def _safe_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return Json(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return Json(json.loads(s))
        except Exception:
            return s
    return v


def _truncate(cur: Any) -> None:
    cur.execute(
        """
        TRUNCATE TABLE
            warehouse.admission_requirements,
            warehouse.rankings,
            staging.raw_source_records,
            warehouse.university_aliases,
            warehouse.universities,
            warehouse.countries,
            warehouse.crawl_runs
        RESTART IDENTITY CASCADE
        """
    )


def migrate(sqlite_path: Path, pg_conn: Any, truncate_first: bool) -> None:
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    try:
        with pg_conn.cursor() as cur:
            if truncate_first:
                _truncate(cur)
                pg_conn.commit()

            for table in TABLE_MIGRATION_ORDER:
                rows = _sqlite_rows(sqlite_conn, table)
                if not rows:
                    print(f"[skip] {table}: 0 rows")
                    continue

                if table == "crawl_runs":
                    values = [
                        (
                            r["crawl_run_id"], r["source_name"], r["ranking_type"], r["started_at"],
                            r["finished_at"], r["status"], r["notes"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.crawl_runs
                        (crawl_run_id, source_name, ranking_type, started_at, finished_at, status, notes)
                        VALUES %s
                        ON CONFLICT (crawl_run_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "countries":
                    values = [
                        (
                            r["country_id"], r["country_code"], r["country_name"], r["region_name"], r["created_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.countries
                        (country_id, country_code, country_name, region_name, created_at)
                        VALUES %s
                        ON CONFLICT (country_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "universities":
                    values = [
                        (
                            r["university_id"], r["school_slug"], r["display_name"], r["canonical_name"],
                            r["country_id"], r["city_name"], r["website_url"], r["qs_profile_path"],
                            None, None, r["created_at"], r["updated_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.universities
                        (university_id, school_slug, display_name, canonical_name, country_id, city_name,
                         website_url, qs_profile_path, embedding, metadata, created_at, updated_at)
                        VALUES %s
                        ON CONFLICT (university_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "university_aliases":
                    values = [
                        (
                            r["alias_id"], r["university_id"], r["source_name"], r["source_school_name"],
                            r["match_type"], r["confidence_score"], r["created_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.university_aliases
                        (alias_id, university_id, source_name, source_school_name, match_type, confidence_score, created_at)
                        VALUES %s
                        ON CONFLICT (alias_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "raw_source_records":
                    values = [
                        (
                            r["raw_id"], r["crawl_run_id"], r["source_name"], r["record_type"], r["ranking_type"],
                            r["source_url"], _safe_json(r["raw_json"]), r["raw_text"], r["fetched_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO staging.raw_source_records
                        (raw_id, crawl_run_id, source_name, record_type, ranking_type, source_url, raw_json, raw_text, fetched_at)
                        VALUES %s
                        ON CONFLICT (raw_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "rankings":
                    values = [
                        (
                            r["ranking_id"], r["university_id"], r["raw_id"], r["ranking_source"], r["ranking_type"],
                            r["ranking_year"], r["rank_start"], r["rank_end"], r["score"], _safe_json(r["metrics_json"]),
                            r["source_url"], r["created_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.rankings
                        (ranking_id, university_id, raw_id, ranking_source, ranking_type, ranking_year,
                         rank_start, rank_end, score, metrics_json, source_url, created_at)
                        VALUES %s
                        ON CONFLICT (ranking_id) DO NOTHING
                        """,
                        values,
                    )
                elif table == "admission_requirements":
                    values = [
                        (
                            r["requirement_id"], r["university_id"], r["program_id"], r["degree_id"], r["raw_id"],
                            r["source_url"], r["gpa_min"], r["ielts_min"], r["toefl_min"], r["gre_min"], r["gmat_min"],
                            r["application_deadline_text"], r["raw_text"], r["parsed_status"], r["extracted_at"],
                        )
                        for r in rows
                    ]
                    execute_values(
                        cur,
                        """
                        INSERT INTO warehouse.admission_requirements
                        (requirement_id, university_id, program_id, degree_id, raw_id, source_url, gpa_min, ielts_min,
                         toefl_min, gre_min, gmat_min, application_deadline_text, raw_text, parsed_status, extracted_at)
                        VALUES %s
                        ON CONFLICT (requirement_id) DO NOTHING
                        """,
                        values,
                    )
                pg_conn.commit()
                print(f"[ok] migrated {table}: {len(rows)} rows")

            _reset_sequences(cur)
            pg_conn.commit()
    finally:
        sqlite_conn.close()


def _reset_sequences(cur: Any) -> None:
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.crawl_runs', 'crawl_run_id'), COALESCE(MAX(crawl_run_id), 1), true) FROM warehouse.crawl_runs")
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.countries', 'country_id'), COALESCE(MAX(country_id), 1), true) FROM warehouse.countries")
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.universities', 'university_id'), COALESCE(MAX(university_id), 1), true) FROM warehouse.universities")
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.university_aliases', 'alias_id'), COALESCE(MAX(alias_id), 1), true) FROM warehouse.university_aliases")
    cur.execute("SELECT setval(pg_get_serial_sequence('staging.raw_source_records', 'raw_id'), COALESCE(MAX(raw_id), 1), true) FROM staging.raw_source_records")
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.rankings', 'ranking_id'), COALESCE(MAX(ranking_id), 1), true) FROM warehouse.rankings")
    cur.execute("SELECT setval(pg_get_serial_sequence('warehouse.admission_requirements', 'requirement_id'), COALESCE(MAX(requirement_id), 1), true) FROM warehouse.admission_requirements")


def main() -> int:
    args = build_parser().parse_args()
    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    try:
        migrate(Path(args.sqlite_path), conn, truncate_first=args.truncate_first)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
