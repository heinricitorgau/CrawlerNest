"""Applying the CrawlerNest SQL schema files to a PostgreSQL database.

Shared because both run_pipeline.py's bootstrap command and the canonical
seeding commands need to guarantee the schema exists before they write. Keeping
them in the entry point would have made the command module import its own
caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from pipeline.bootstrap import resolve_repo_paths
except ModuleNotFoundError:  # pragma: no cover - package import compatibility
    from ...pipeline.bootstrap import resolve_repo_paths

try:
    import psycopg2
    from psycopg2 import errors as psycopg2_errors
except ImportError:  # pragma: no cover - reported by the caller
    psycopg2 = None  # type: ignore
    psycopg2_errors = None  # type: ignore

#: Directory holding the crawlernest-schema package. run_pipeline.py computes
#: this from its own location; this module sits two levels deeper, so it asks
#: the same helper rather than repeating the arithmetic.
_REPO_ROOT, MODULE_ROOT = resolve_repo_paths(str(Path(__file__).resolve().parents[2] / "run_pipeline.py"))


def _split_sql_statements(sql: str) -> list[str]:
    cleaned_lines: list[str] = []
    for line in sql.splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned_lines.append(line)
    sql = "\n".join(cleaned_lines)
    return [part.strip() + ";" for part in sql.split(";") if part.strip()]


def _is_postgres_duplicate_error(exc: Exception) -> bool:
    if psycopg2_errors is None:
        return False
    return isinstance(
        exc,
        (
            psycopg2_errors.DuplicateTable,
            psycopg2_errors.DuplicateObject,
            psycopg2_errors.DuplicateSchema,
            psycopg2_errors.DuplicateColumn,
            psycopg2_errors.DuplicateFunction,
        ),
    )


def assert_no_admission_table_collision(cur) -> None:
    """Refuse to apply the schema while both admission table names exist.

    The rename in admission_postgresql.sql raises 42P07 in that state, which is
    a duplicate-table error, which both schema appliers deliberately swallow --
    so the migration would report success while leaving every row in the old
    table and every reader pointed at the empty new one.

    Usually a stray empty table from the Java integration tests, whose fixtures
    run CREATE TABLE IF NOT EXISTS warehouse.admission_record against this same
    database.
    """
    cur.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name IN ('admission_record', 'admission_records_preview')
        """
    )
    if int(cur.fetchone()[0] or 0) < 2:
        return
    raise RuntimeError(
        "warehouse.admission_record and warehouse.admission_records_preview "
        "both exist, so the rename cannot run. Drop the empty one and retry. "
        "See docs/migrations/ADMISSION_SCHEMA_CONVERGENCE.md"
    )


def ensure_postgres_schema(
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> None:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    schema_paths = [
        MODULE_ROOT / "crawlernest-schema" / "postgresql_schema.sql",
        MODULE_ROOT / "crawlernest-schema" / "entity_resolution_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "multi_source_postgresql.sql",
        # After multi_source: references warehouse.ranking_source.
        MODULE_ROOT / "crawlernest-schema" / "mapping_review_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "subject_ranking_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "ranking_aggregation_postgresql.sql",
        # After mapping_review: references warehouse.entity_source.
        # Before recommendation: its view reads warehouse.admission_record.
        MODULE_ROOT / "crawlernest-schema" / "admission_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "recommendation_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "ml_postgresql.sql",
        # Agent API runtime state; references nothing above.
        MODULE_ROOT / "crawlernest-schema" / "agent_state_postgresql.sql",
    ]
    try:
        with conn.cursor() as cur:
            assert_no_admission_table_collision(cur)
            conn.rollback()
            for path in schema_paths:
                if not path.exists():
                    continue
                for stmt in _split_sql_statements(path.read_text(encoding="utf-8")):
                    try:
                        cur.execute(stmt)
                        conn.commit()
                    except Exception as exc:
                        conn.rollback()
                        if _is_postgres_duplicate_error(exc):
                            continue
                        raise
    finally:
        conn.close()


def ensure_subject_ranking_postgres_schema(
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> None:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    schema_paths = [
        MODULE_ROOT / "crawlernest-schema" / "postgresql_schema.sql",
        MODULE_ROOT / "crawlernest-schema" / "entity_resolution_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "multi_source_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "subject_ranking_postgresql.sql",
    ]
    try:
        with conn.cursor() as cur:
            for path in schema_paths:
                if not path.exists():
                    continue
                for stmt in _split_sql_statements(path.read_text(encoding="utf-8")):
                    try:
                        cur.execute(stmt)
                        conn.commit()
                    except Exception as exc:
                        conn.rollback()
                        if _is_postgres_duplicate_error(exc):
                            continue
                        raise
    finally:
        conn.close()


