"""Primary database ingestion layer for Clawer.

Role classification:
- Purpose: structured crawler-to-database ingestion
- Scope: warehouse-style dimensions, facts, raw lineage, and crawl-run tracking
- Status: current main persistence path

This module should be used by the active crawler pipeline.
"""
import json
import sqlite3
from typing import Any, Optional
from models import University, AdmissionRequirements


class DBWriter:
    """Main persistence / ingestion service for the current Clawer pipeline.

    Responsibilities:
    - write crawl run metadata
    - store raw source records
    - upsert core dimensions (countries / universities / aliases)
    - insert fact-like records (rankings / admission requirements)

    This class is the primary database writer for the active system.
    """

    def __init__(self, db_path: str = "clawer.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        print(f"[DBWriter] connected to: {db_path}")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cur = self.conn.cursor()
        self._ensure_tables_exist()

    # -----------------------------
    # CRAWL RUNS
    # -----------------------------

    def start_crawl_run(
        self,
        source_name: str,
        ranking_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Create a crawl run record and return its id."""

        self.cur.execute(
            """
            INSERT INTO crawl_runs (
                source_name,
                ranking_type,
                status,
                notes
            ) VALUES (?, ?, 'running', ?)
            """,
            (source_name, ranking_type, notes),
        )
        crawl_run_id = self.cur.lastrowid
        if crawl_run_id is None:
            raise RuntimeError("Failed to create crawl_run record")
        return int(crawl_run_id)

    def finish_crawl_run(self, crawl_run_id: int, status: str = "finished") -> None:
        """Mark a crawl run as finished."""

        self.cur.execute(
            """
            UPDATE crawl_runs
            SET finished_at = CURRENT_TIMESTAMP,
                status = ?
            WHERE crawl_run_id = ?
            """,
            (status, crawl_run_id),
        )

    # -----------------------------
    # RAW SOURCE RECORDS
    # -----------------------------

    def insert_raw_record(
        self,
        source_name: str,
        ranking_type: Optional[str] = None,
        raw_json: Optional[str] = None,
        raw_text: Optional[str] = None,
        source_url: Optional[str] = None,
        crawl_run_id: Optional[int] = None,
        record_type: Optional[str] = None,
    ) -> int:
        """Store original crawler payload for traceability."""

        self.cur.execute(
            """
            INSERT INTO raw_source_records (
                crawl_run_id,
                source_name,
                record_type,
                ranking_type,
                raw_json,
                raw_text,
                source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (crawl_run_id, source_name, record_type, ranking_type, raw_json, raw_text, source_url),
        )

        raw_id = self.cur.lastrowid
        if raw_id is None:
            raise RuntimeError("Failed to create raw_source_record")
        return int(raw_id)

    # -----------------------------
    # COUNTRIES
    # -----------------------------

    def get_or_create_country(self, country_name: str) -> Optional[int]:
        """Return country_id, creating the country if needed."""

        normalized_country = self._normalize_country_name(country_name)
        if not normalized_country:
            return None

        # Try to find an existing country first.
        self.cur.execute(
            """
            SELECT country_id FROM countries
            WHERE country_name = ?
            """,
            (normalized_country,),
        )
        row = self.cur.fetchone()
        if row:
            return row[0]

        # Insert only when the country does not already exist.
        self.cur.execute(
            """
            INSERT OR IGNORE INTO countries (country_name)
            VALUES (?)
            """,
            (normalized_country,),
        )

        self.cur.execute(
            """
            SELECT country_id FROM countries
            WHERE country_name = ?
            """,
            (normalized_country,),
        )

        row = self.cur.fetchone()
        return row[0] if row else None

    # -----------------------------
    # UNIVERSITIES
    # -----------------------------

    def upsert_university(self, uni: University) -> int:
        """Insert or update university record."""

        country_id = self.get_or_create_country(uni.country)

        slug = self._slugify(uni.name)

        self.cur.execute(
            """
            INSERT INTO universities (
                school_slug,
                display_name,
                canonical_name,
                country_id
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(school_slug)
            DO UPDATE SET
                display_name = excluded.display_name,
                canonical_name = excluded.canonical_name,
                country_id = COALESCE(excluded.country_id, universities.country_id)
            """,
            (
                slug,
                uni.name,
                uni.name,
                country_id,
            ),
        )

        self.cur.execute(
            """
            SELECT university_id FROM universities
            WHERE school_slug = ?
            """,
            (slug,),
        )

        row = self.cur.fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve university_id for slug: {slug}")
        return int(row[0])

    def upsert_university_alias(
        self,
        university_id: int,
        source_name: str,
        source_school_name: str,
        match_type: str = "manual",
        confidence_score: float = 1.0,
    ) -> None:
        """Store source-specific university naming for later entity resolution."""

        if not source_school_name:
            return

        self.cur.execute(
            """
            INSERT INTO university_aliases (
                university_id,
                source_name,
                source_school_name,
                match_type,
                confidence_score
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_name, source_school_name)
            DO UPDATE SET
                university_id = excluded.university_id,
                match_type = excluded.match_type,
                confidence_score = excluded.confidence_score
            """,
            (university_id, source_name, source_school_name, match_type, confidence_score),
        )

    # -----------------------------
    # UTILS (small normalization helpers)
    # -----------------------------

    def _safe_int(self, value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    # -----------------------------
    # RANKINGS
    # -----------------------------

    def insert_ranking(
        self,
        university_id: int,
        uni: University,
        ranking_source: str = "QS",
        ranking_type: str = "world",
        ranking_year: Optional[int] = None,
        raw_id: Optional[int] = None,
    ):
        """Insert ranking data."""

        score = None
        metrics_json = None

        if uni.table_metrics:
            score = self._safe_float(uni.table_metrics.get("Overall Score"))
            metrics_json = json.dumps(uni.table_metrics, ensure_ascii=False)

        self.cur.execute(
            """
            INSERT INTO rankings (
                university_id,
                raw_id,
                ranking_source,
                ranking_type,
                ranking_year,
                rank_start,
                rank_end,
                score,
                metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                university_id,
                raw_id,
                ranking_source,
                ranking_type,
                ranking_year,
                self._safe_int(uni.rank),
                self._safe_int(uni.rank),
                score,
                metrics_json,
            ),
        )

    # -----------------------------
    # ADMISSION REQUIREMENTS
    # -----------------------------

    def insert_admission_requirements(
        self,
        university_id: int,
        req: Optional[AdmissionRequirements],
        raw_id: Optional[int] = None,
    ):
        """Insert admission requirements if available."""

        if not req:
            return

        self.cur.execute(
            """
            INSERT INTO admission_requirements (
                university_id,
                raw_id,
                gpa_min,
                ielts_min,
                toefl_min,
                gre_min,
                gmat_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                university_id,
                raw_id,
                self._safe_float(req.gpa),
                self._safe_float(req.ielts),
                self._safe_float(req.toefl),
                self._safe_float(req.gre),
                self._safe_float(req.gmat),
            ),
        )

    # -----------------------------
    # MAIN INGESTION
    # -----------------------------

    def ingest_university(
        self,
        uni: University,
        ranking_source: str = "QS",
        ranking_type: str = "world",
        ranking_year: Optional[int] = None,
        raw_id: Optional[int] = None,
    ):
        """Full pipeline for inserting a university."""

        university_id = self.upsert_university(uni)

        self.upsert_university_alias(
            university_id,
            ranking_source,
            uni.name,
            match_type="crawler",
            confidence_score=1.0,
        )

        self.insert_ranking(
            university_id,
            uni,
            ranking_source,
            ranking_type,
            ranking_year,
            raw_id,
        )

        self.insert_admission_requirements(
            university_id,
            uni.requirements,
            raw_id,
        )

    # -----------------------------
    # UTILS
    # -----------------------------

    def _slugify(self, name: str) -> str:
        return name.lower().replace(" ", "-").replace("(", "").replace(")", "")

    def _normalize_country_name(self, country_name: Optional[str]) -> str:
        """Normalize country text before lookup / insert."""
        if not country_name:
            return ""
        return " ".join(country_name.strip().split())

    def _ensure_tables_exist(self):
        """Check if core tables exist; if not, run schema.sql."""
        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_runs'")
        if not self.cur.fetchone():
            import os
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, "r") as f:
                    self.conn.executescript(f.read())
                self.conn.commit()

    # -----------------------------
    # COMMIT / CLOSE
    # -----------------------------

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()