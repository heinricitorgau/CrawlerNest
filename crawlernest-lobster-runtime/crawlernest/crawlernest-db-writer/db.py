"""Legacy helper redirected to PostgreSQL-only mode.

For production ingestion, prefer `db_writer.DBWriter`.
This helper remains only to avoid import breakage in old scripts.
"""

from __future__ import annotations

try:
    import psycopg2
except ImportError as exc:
    raise RuntimeError("psycopg2 is required for PostgreSQL mode") from exc


def get_connection(
    host: str = "localhost",
    port: int = 5432,
    database: str = "clawer",
    user: str = "test",
    password: str = "",
):
    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )


def init_db():
    raise RuntimeError("Legacy local DB bootstrap has been removed. Use bootstrap_postgres.py instead.")


def insert_university(uni):
    raise RuntimeError("Legacy direct insert helper has been removed. Use DBWriter instead.")
