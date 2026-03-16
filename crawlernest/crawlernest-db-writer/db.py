"""Legacy lightweight SQLite helper.

This module is kept for simple experiments and backward compatibility.

Role classification:
- Purpose: temporary / experimental local table writing
- Scope: single-table helper for `universities_tmp`
- Status: legacy helper, not the main warehouse ingestion path

For the current structured crawler-to-database pipeline, use `db_writer.py`.
"""
import sqlite3


# --------------------------------------------------
# Legacy temporary database helpers
# --------------------------------------------------
def get_connection():
    return sqlite3.connect("universities.db")


# Creates a minimal temporary table used in early experiments.
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS universities_tmp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rank_value TEXT,
        name TEXT,
        country TEXT,
        path TEXT,
        overall_score TEXT,
        academic_reputation TEXT,
        employer_reputation TEXT
    )
    """)

    conn.commit()
    conn.close()


# Writes a simplified university row into the legacy temporary table.
def insert_university(uni):
    conn = get_connection()
    cursor = conn.cursor()

    metrics = uni.table_metrics or {}

    cursor.execute("""
    INSERT INTO universities_tmp (
        rank_value,
        name,
        country,
        path,
        overall_score,
        academic_reputation,
        employer_reputation
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(uni.rank),
        str(uni.name),
        str(uni.country),
        str(uni.path),
        metrics.get("Overall Score"),
        metrics.get("Academic Reputation"),
        metrics.get("Employer Reputation"),
    ))

    conn.commit()
    conn.close()