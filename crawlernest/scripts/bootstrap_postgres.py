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
    # After multi_source: references warehouse.ranking_source.
    SCHEMA_DIR / "mapping_review_postgresql.sql",
    SCHEMA_DIR / "subject_ranking_postgresql.sql",
    SCHEMA_DIR / "ranking_aggregation_postgresql.sql",
    # After mapping_review: references warehouse.entity_source.
    # Before recommendation: its view reads warehouse.admission_record.
    SCHEMA_DIR / "admission_postgresql.sql",
    SCHEMA_DIR / "recommendation_postgresql.sql",
]


def _subject_registry_summary(cur) -> dict[str, object]:
    cur.execute(
        """
        SELECT subject_key, display_name, is_active
        FROM warehouse.ranking_subject
        ORDER BY subject_key
        """
    )
    rows = cur.fetchall()
    return {
        "ranking_subject_count": len(rows),
        "subjects": [
            {
                "subject_key": subject_key,
                "display_name": display_name,
                "is_active": bool(is_active),
            }
            for subject_key, display_name, is_active in rows
        ],
    }


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


#: Both admission table names existing at once means the rename in
#: admission_postgresql.sql cannot run. PostgreSQL raises 42P07 for it, which
#: is a duplicate-table error, which the loop below deliberately swallows --
#: so the migration would report success while leaving every row behind in the
#: old table and every reader pointed at the empty new one.
#:
#: The usual cause is the Java integration tests: their fixtures run
#: CREATE TABLE IF NOT EXISTS warehouse.admission_record against this same
#: database. If that stray table is empty, drop it and re-run.
ADMISSION_TABLE_NAMES = ("admission_record", "admission_records_preview")


def _assert_no_admission_table_collision(cur) -> None:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = ANY(%s)
        """,
        (list(ADMISSION_TABLE_NAMES),),
    )
    present = {row[0] for row in cur.fetchall()}
    if len(present) < 2:
        return

    cur.execute("SELECT count(*) FROM warehouse.admission_record")
    new_count = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT count(*) FROM warehouse.admission_records_preview")
    old_count = int(cur.fetchone()[0] or 0)

    raise SystemExit(
        f"""Refusing to migrate: warehouse.admission_record ({new_count} rows) and
warehouse.admission_records_preview ({old_count} rows) both exist, so the
rename cannot run.

  The usual cause is a stray table left by the Java integration tests, whose
  fixtures create it in this database.

  If warehouse.admission_record is the empty stray and
  warehouse.admission_records_preview holds the real rows, drop it and re-run
  this command:

      psql -d <db> -c 'DROP TABLE warehouse.admission_record CASCADE'

  CASCADE is needed because analytics.v_recommendation_candidates_latest reads
  it; this command rebuilds that view.

  See docs/migrations/ADMISSION_SCHEMA_CONVERGENCE.md"""
    )


def _assert_ranking_preview_is_empty(cur) -> None:
    """Refuse to drop warehouse.ranking_records_preview while it holds rows.

    multi_source_postgresql.sql drops that table unconditionally. The guard is
    here rather than in the file because a dollar-quoted block cannot survive
    _split_sql_statements, which splits on every ';'.
    """
    cur.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = 'ranking_records_preview'
        """
    )
    if int(cur.fetchone()[0] or 0) == 0:
        return

    cur.execute("SELECT count(*) FROM warehouse.ranking_records_preview")
    leftover = int(cur.fetchone()[0] or 0)
    if leftover == 0:
        return

    raise SystemExit(
        f"""Refusing to drop: warehouse.ranking_records_preview still holds {leftover} row(s).

  Nothing writes that table any more -- the landing chain that did was deleted --
  so rows in it mean something unexpected is still running. Move them into
  warehouse.ranking_record before re-running this command.

  See docs/migrations/RANKING_SCHEMA_CONVERGENCE.md"""
    )


def _reset_schemas(cur) -> None:
    cur.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
    cur.execute("DROP SCHEMA IF EXISTS staging CASCADE")
    cur.execute("DROP SCHEMA IF EXISTS warehouse CASCADE")


def bootstrap_postgres(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    reset: bool = False,
) -> dict[str, object]:
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
    applied_schemas: list[dict[str, object]] = []
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            if reset:
                _reset_schemas(cur)
                conn.commit()
                print("[ok] reset analytics/staging/warehouse schemas")
            _assert_no_admission_table_collision(cur)
            _assert_ranking_preview_is_empty(cur)
            conn.rollback()
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
                applied_schemas.append(
                    {
                        "schema": path.name,
                        "executed": applied,
                        "skipped_existing": skipped,
                    }
                )
            subject_summary = _subject_registry_summary(cur)
    finally:
        conn.close()
    return {
        "database": database,
        "user": user,
        "reset": reset,
        "schemas": applied_schemas,
        **subject_summary,
    }


def main() -> int:
    args = build_parser().parse_args()
    summary = bootstrap_postgres(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        reset=args.reset,
    )
    print(
        "[ok] ranking_subject_count="
        f"{summary['ranking_subject_count']} subjects="
        f"{', '.join(item['subject_key'] for item in summary['subjects'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
