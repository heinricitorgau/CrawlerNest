#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    import psycopg2
    from psycopg2 import errors
except ImportError as exc:
    raise SystemExit("psycopg2 is required. Install with `pip install psycopg2-binary`.") from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "crawlernest-schema"
SCHEMA_ORDER = [
    SCHEMA_DIR / "postgresql_schema.sql",
    SCHEMA_DIR / "entity_resolution_postgresql.sql",
    SCHEMA_DIR / "multi_source_postgresql.sql",
    SCHEMA_DIR / "ranking_aggregation_postgresql.sql",
    SCHEMA_DIR / "recommendation_postgresql.sql",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap CrawlerNest PostgreSQL schemas in dependency order")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    parser.add_argument("--reset", action="store_true", help="Drop analytics/staging/warehouse schemas before bootstrap")
    return parser


def _split_sql_statements(sql: str) -> list[str]:
    cleaned_lines: list[str] = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned_lines.append(line)
    sql = "\n".join(cleaned_lines)
    statements: list[str] = []
    parts = sql.split(";")
    for part in parts:
        stmt = part.strip()
        if not stmt:
            continue
        statements.append(stmt + ";")
    return statements


def _is_duplicate_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            errors.DuplicateTable,
            errors.DuplicateObject,
            errors.DuplicateSchema,
            errors.DuplicateColumn,
            errors.DuplicateFunction,
        ),
    )


def _reset_schemas(cur) -> None:
    cur.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
    cur.execute("DROP SCHEMA IF EXISTS staging CASCADE")
    cur.execute("DROP SCHEMA IF EXISTS warehouse CASCADE")


def main() -> int:
    args = build_parser().parse_args()
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            if args.reset:
                _reset_schemas(cur)
                conn.commit()
                print("[ok] reset analytics/staging/warehouse schemas")
            for path in SCHEMA_ORDER:
                sql = path.read_text(encoding="utf-8")
                applied = 0
                skipped = 0
                for stmt in _split_sql_statements(sql):
                    try:
                        cur.execute(stmt)
                        conn.commit()
                        applied += 1
                    except Exception as exc:
                        conn.rollback()
                        if _is_duplicate_error(exc):
                            skipped += 1
                            continue
                        raise
                print(f"[ok] applied {path.name} (executed={applied}, skipped_existing={skipped})")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
