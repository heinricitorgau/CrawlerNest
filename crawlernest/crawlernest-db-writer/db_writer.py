"""Primary database ingestion layer for Clawer.

Role classification:
- Purpose: structured crawler-to-database ingestion
- Scope: warehouse-style dimensions, facts, raw lineage, and crawl-run tracking
- Status: current main persistence path

This module should be used by the active crawler pipeline.
"""
import json
import sqlite3
import os
from typing import Any, Optional, Union, Dict
from models import University, AdmissionRequirements

# Attempt to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import Json
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


class DBWriter:
    """Main persistence / ingestion service for the Clawer pipeline.

    Supports both SQLite (V1.5) and PostgreSQL (V2/V3 AI-ready).
    """

    def __init__(self, db_type: str = "sqlite", **kwargs):
        """Initialize connection based on db_type.
        
        Args:
            db_type: 'sqlite' or 'postgres'
            **kwargs: Connection parameters (e.g., db_path for sqlite, host/user/password for postgres)
        """
        self.db_type = db_type.lower()
        if self.db_type == "sqlite":
            db_path = kwargs.get("db_path", "clawer.db")
            self.conn = sqlite3.connect(db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")
            print(f"[DBWriter] connected to SQLite: {db_path}")
        elif self.db_type == "postgres":
            if not HAS_POSTGRES:
                raise ImportError("psycopg2 is required for PostgreSQL support. Install with 'pip install psycopg2-binary'")
            self.conn = psycopg2.connect(**kwargs)
            print(f"[DBWriter] connected to PostgreSQL: {kwargs.get('host', 'localhost')}")
        else:
            raise ValueError(f"Unsupported db_type: {db_type}")
        
        self.cur = self.conn.cursor()
        self._country_id_cache: Dict[str, int] = {}
        self._university_id_cache: Dict[str, int] = {}
        self._ensure_tables_exist()

    def _get_placeholder(self) -> str:
        return "?" if self.db_type == "sqlite" else "%s"

    def _get_schema_prefix(self, table_name: str) -> str:
        if self.db_type == "sqlite":
            return table_name
        # Map tables to PostgreSQL schemas
        schema_map = {
            "crawl_runs": "warehouse",
            "countries": "warehouse",
            "universities": "warehouse",
            "university_aliases": "warehouse",
            "programs": "warehouse",
            "degrees": "warehouse",
            "rankings": "warehouse",
            "admission_requirements": "warehouse",
            "raw_source_records": "staging",
            "field_status_logs": "analytics"
        }
        return f"{schema_map.get(table_name, 'public')}.{table_name}"

    # -----------------------------
    # CRAWL RUNS
    # -----------------------------

    def start_crawl_run(
        self,
        source_name: str,
        ranking_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        p = self._get_placeholder()
        table = self._get_schema_prefix("crawl_runs")
        
        query = f"""
            INSERT INTO {table} (
                source_name,
                ranking_type,
                status,
                notes
            ) VALUES ({p}, {p}, 'running', {p})
        """
        
        if self.db_type == "sqlite":
            self.cur.execute(query, (source_name, ranking_type, notes))
            crawl_run_id = self.cur.lastrowid
        else:
            query += " RETURNING crawl_run_id"
            self.cur.execute(query, (source_name, ranking_type, notes))
            crawl_run_id = self.cur.fetchone()[0]

        if crawl_run_id is None:
            raise RuntimeError("Failed to create crawl_run record")
        return int(crawl_run_id)

    def finish_crawl_run(self, crawl_run_id: int, status: str = "finished") -> None:
        p = self._get_placeholder()
        table = self._get_schema_prefix("crawl_runs")
        self.cur.execute(
            f"""
            UPDATE {table}
            SET finished_at = CURRENT_TIMESTAMP,
                status = {p}
            WHERE crawl_run_id = {p}
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
        raw_json: Optional[Union[str, dict]] = None,
        raw_text: Optional[str] = None,
        source_url: Optional[str] = None,
        crawl_run_id: Optional[int] = None,
        record_type: Optional[str] = None,
    ) -> int:
        p = self._get_placeholder()
        table = self._get_schema_prefix("raw_source_records")
        
        # Handle JSONB for PostgreSQL
        if self.db_type == "postgres" and isinstance(raw_json, dict):
            raw_json = Json(raw_json)
        elif self.db_type == "sqlite" and isinstance(raw_json, dict):
            raw_json = json.dumps(raw_json, ensure_ascii=False)

        query = f"""
            INSERT INTO {table} (
                crawl_run_id,
                source_name,
                record_type,
                ranking_type,
                raw_json,
                raw_text,
                source_url
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """
        
        if self.db_type == "sqlite":
            self.cur.execute(query, (crawl_run_id, source_name, record_type, ranking_type, raw_json, raw_text, source_url))
            raw_id = self.cur.lastrowid
        else:
            query += " RETURNING raw_id"
            self.cur.execute(query, (crawl_run_id, source_name, record_type, ranking_type, raw_json, raw_text, source_url))
            raw_id = self.cur.fetchone()[0]

        if raw_id is None:
            raise RuntimeError("Failed to create raw_source_record")
        return int(raw_id)

    def insert_raw_records_batch(self, rows: list[dict[str, Any]]) -> list[int]:
        if not rows:
            return []

        p = self._get_placeholder()
        table = self._get_schema_prefix("raw_source_records")
        query = f"""
            INSERT INTO {table} (
                crawl_run_id,
                source_name,
                record_type,
                ranking_type,
                raw_json,
                raw_text,
                source_url
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """

        params: list[tuple[Any, ...]] = []
        for row in rows:
            raw_json = row.get("raw_json")
            if self.db_type == "postgres" and isinstance(raw_json, dict):
                raw_json = Json(raw_json)
            elif self.db_type == "sqlite" and isinstance(raw_json, dict):
                raw_json = json.dumps(raw_json, ensure_ascii=False)
            params.append(
                (
                    row.get("crawl_run_id"),
                    row.get("source_name"),
                    row.get("record_type"),
                    row.get("ranking_type"),
                    raw_json,
                    row.get("raw_text"),
                    row.get("source_url"),
                )
            )

        if self.db_type == "sqlite":
            self.cur.executemany(query, params)
            self.cur.execute("SELECT last_insert_rowid()")
            last_id_row = self.cur.fetchone()
            if not last_id_row or last_id_row[0] is None:
                raise RuntimeError("Failed to resolve last_insert_rowid for raw_source_records batch")
            last_id = int(last_id_row[0])
            first_id = last_id - len(rows) + 1
            return list(range(first_id, last_id + 1))

        # PostgreSQL fallback keeps correctness (ids may not be contiguous).
        raw_ids: list[int] = []
        for row in rows:
            raw_id = self.insert_raw_record(
                source_name=str(row.get("source_name") or ""),
                ranking_type=row.get("ranking_type"),
                raw_json=row.get("raw_json"),
                raw_text=row.get("raw_text"),
                source_url=row.get("source_url"),
                crawl_run_id=row.get("crawl_run_id"),
                record_type=row.get("record_type"),
            )
            raw_ids.append(raw_id)
        return raw_ids

    def get_existing_states_by_slugs(
        self,
        slugs: list[str],
        ranking_type: str = "world",
        ranking_year: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        unique_slugs = [s for s in dict.fromkeys(slugs) if s]
        if not unique_slugs:
            return {}

        p = self._get_placeholder()
        universities_t = self._get_schema_prefix("universities")
        countries_t = self._get_schema_prefix("countries")
        rankings_t = self._get_schema_prefix("rankings")
        admissions_t = self._get_schema_prefix("admission_requirements")
        in_placeholders = ", ".join([p] * len(unique_slugs))

        query = f"""
            SELECT
                u.school_slug,
                u.display_name,
                COALESCE(c.country_name, ''),
                u.qs_profile_path,
                r.rank_start,
                r.score,
                r.metrics_json,
                ar.gpa_min,
                ar.ielts_min,
                ar.toefl_min,
                ar.gre_min,
                ar.gmat_min
            FROM {universities_t} u
            LEFT JOIN {countries_t} c ON c.country_id = u.country_id
            LEFT JOIN {rankings_t} r ON r.ranking_id = (
                SELECT r2.ranking_id
                FROM {rankings_t} r2
                WHERE r2.university_id = u.university_id
                  AND r2.ranking_type = {p}
                  AND (({p} IS NULL AND r2.ranking_year IS NULL) OR r2.ranking_year = {p})
                ORDER BY r2.ranking_id DESC
                LIMIT 1
            )
            LEFT JOIN {admissions_t} ar ON ar.requirement_id = (
                SELECT a2.requirement_id
                FROM {admissions_t} a2
                WHERE a2.university_id = u.university_id
                ORDER BY a2.requirement_id DESC
                LIMIT 1
            )
            WHERE u.school_slug IN ({in_placeholders})
        """
        params: list[Any] = [ranking_type, ranking_year, ranking_year, *unique_slugs]
        self.cur.execute(query, tuple(params))
        rows = self.cur.fetchall()

        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            metrics = row[6]
            if isinstance(metrics, str):
                try:
                    metrics = json.loads(metrics)
                except Exception:
                    metrics = None
            slug = str(row[0])
            out[slug] = {
                "name": row[1],
                "country": row[2],
                "qs_profile_path": row[3],
                "rank_start": row[4],
                "score": row[5],
                "metrics_json": metrics,
                "gpa": row[7],
                "ielts": row[8],
                "toefl": row[9],
                "gre": row[10],
                "gmat": row[11],
            }
        return out

    # -----------------------------
    # COUNTRIES
    # -----------------------------

    def get_or_create_country(self, country_name: str) -> Optional[int]:
        normalized_country = self._normalize_country_name(country_name)
        if not normalized_country:
            return None
        cached_country_id = self._country_id_cache.get(normalized_country)
        if cached_country_id is not None:
            return cached_country_id

        p = self._get_placeholder()
        table = self._get_schema_prefix("countries")

        self.cur.execute(f"SELECT country_id FROM {table} WHERE country_name = {p}", (normalized_country,))
        row = self.cur.fetchone()
        if row:
            country_id = int(row[0])
            self._country_id_cache[normalized_country] = country_id
            return country_id

        if self.db_type == "sqlite":
            self.cur.execute(f"INSERT OR IGNORE INTO {table} (country_name) VALUES ({p})", (normalized_country,))
        else:
            self.cur.execute(f"INSERT INTO {table} (country_name) VALUES ({p}) ON CONFLICT DO NOTHING", (normalized_country,))

        self.cur.execute(f"SELECT country_id FROM {table} WHERE country_name = {p}", (normalized_country,))
        row = self.cur.fetchone()
        if not row:
            return None
        country_id = int(row[0])
        self._country_id_cache[normalized_country] = country_id
        return country_id

    # -----------------------------
    # UNIVERSITIES
    # -----------------------------

    def upsert_university(self, uni: University, embedding: Optional[list] = None) -> int:
        country_id = self.get_or_create_country(uni.country)
        slug = self._slugify(uni.name)
        cached_university_id = self._university_id_cache.get(slug)
        p = self._get_placeholder()
        table = self._get_schema_prefix("universities")

        if self.db_type == "sqlite":
            self.cur.execute(
                f"""
                INSERT INTO {table} (
                    school_slug, display_name, canonical_name, country_id
                ) VALUES ({p}, {p}, {p}, {p})
                ON CONFLICT(school_slug) DO UPDATE SET
                    display_name = excluded.display_name,
                    canonical_name = excluded.canonical_name,
                    country_id = COALESCE(excluded.country_id, {table}.country_id)
                """,
                (slug, uni.name, uni.name, country_id),
            )
        else:
            # PostgreSQL supports vectors and returning
            self.cur.execute(
                f"""
                INSERT INTO {table} (
                    school_slug, display_name, canonical_name, country_id, embedding
                ) VALUES ({p}, {p}, {p}, {p}, {p})
                ON CONFLICT(school_slug) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    canonical_name = EXCLUDED.canonical_name,
                    country_id = COALESCE(EXCLUDED.country_id, {table}.country_id),
                    embedding = COALESCE(EXCLUDED.embedding, {table}.embedding)
                RETURNING university_id
                """,
                (slug, uni.name, uni.name, country_id, embedding),
            )
            university_id = int(self.cur.fetchone()[0])
            self._university_id_cache[slug] = university_id
            return university_id

        if cached_university_id is not None:
            return cached_university_id

        self.cur.execute(f"SELECT university_id FROM {table} WHERE school_slug = {p}", (slug,))
        row = self.cur.fetchone()
        if row is None:
            raise RuntimeError(f"Failed to resolve university_id for slug={slug}")
        university_id = int(row[0])
        self._university_id_cache[slug] = university_id
        return university_id

    def upsert_university_alias(
        self,
        university_id: int,
        source_name: str,
        source_school_name: str,
        match_type: str = "manual",
        confidence_score: float = 1.0,
    ) -> None:
        if not source_school_name:
            return

        p = self._get_placeholder()
        table = self._get_schema_prefix("university_aliases")
        
        conflict_target = "source_name, source_school_name"
        
        query = f"""
            INSERT INTO {table} (
                university_id, source_name, source_school_name, match_type, confidence_score
            ) VALUES ({p}, {p}, {p}, {p}, {p})
            ON CONFLICT({conflict_target})
            DO UPDATE SET
                university_id = EXCLUDED.university_id,
                match_type = EXCLUDED.match_type,
                confidence_score = EXCLUDED.confidence_score
        """
        # SQLite uses small letters for EXCLUDED sometimes but works with EXCLUDED too.
        self.cur.execute(query, (university_id, source_name, source_school_name, match_type, confidence_score))

    def upsert_university_aliases_batch(self, rows: list[tuple[int, str, str, str, float]]) -> None:
        if not rows:
            return
        p = self._get_placeholder()
        table = self._get_schema_prefix("university_aliases")
        conflict_target = "source_name, source_school_name"
        query = f"""
            INSERT INTO {table} (
                university_id, source_name, source_school_name, match_type, confidence_score
            ) VALUES ({p}, {p}, {p}, {p}, {p})
            ON CONFLICT({conflict_target})
            DO UPDATE SET
                university_id = EXCLUDED.university_id,
                match_type = EXCLUDED.match_type,
                confidence_score = EXCLUDED.confidence_score
        """
        self.cur.executemany(query, rows)

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
        score = None
        metrics_json = uni.table_metrics or {}

        if metrics_json:
            score = self._safe_float(metrics_json.get("Overall Score"))
            if self.db_type == "postgres":
                metrics_json = Json(metrics_json)
            else:
                metrics_json = json.dumps(metrics_json, ensure_ascii=False)
        else:
            metrics_json = None

        p = self._get_placeholder()
        table = self._get_schema_prefix("rankings")

        self.cur.execute(
            f"""
            INSERT INTO {table} (
                university_id, raw_id, ranking_source, ranking_type,
                ranking_year, rank_start, rank_end, score, metrics_json
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (
                university_id, raw_id, ranking_source, ranking_type,
                ranking_year, self._safe_int(uni.rank), self._safe_int(uni.rank),
                score, metrics_json,
            ),
        )

    def insert_rankings_batch(
        self,
        rows: list[tuple[int, Optional[int], str, str, Optional[int], Optional[int], Optional[int], Optional[float], Any]],
    ) -> None:
        if not rows:
            return
        p = self._get_placeholder()
        table = self._get_schema_prefix("rankings")
        query = f"""
            INSERT INTO {table} (
                university_id, raw_id, ranking_source, ranking_type,
                ranking_year, rank_start, rank_end, score, metrics_json
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
        """
        self.cur.executemany(query, rows)

    # -----------------------------
    # ADMISSION REQUIREMENTS
    # -----------------------------

    def insert_admission_requirements(
        self,
        university_id: int,
        req: Optional[AdmissionRequirements],
        raw_id: Optional[int] = None,
    ):
        if not req:
            return

        p = self._get_placeholder()
        table = self._get_schema_prefix("admission_requirements")

        self.cur.execute(
            f"""
            INSERT INTO {table} (
                university_id, raw_id, gpa_min, ielts_min, toefl_min, gre_min, gmat_min
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
            """,
            (
                university_id, raw_id, self._safe_float(req.gpa),
                self._safe_float(req.ielts), self._safe_float(req.toefl),
                self._safe_float(req.gre), self._safe_float(req.gmat),
            ),
        )

    def insert_admission_requirements_batch(
        self,
        rows: list[tuple[int, Optional[int], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]],
    ) -> None:
        if not rows:
            return
        p = self._get_placeholder()
        table = self._get_schema_prefix("admission_requirements")
        query = f"""
            INSERT INTO {table} (
                university_id, raw_id, gpa_min, ielts_min, toefl_min, gre_min, gmat_min
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})
        """
        self.cur.executemany(query, rows)

    # -----------------------------
    # UTILS
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

    def _slugify(self, name: str) -> str:
        return name.lower().replace(" ", "-").replace("(", "").replace(")", "")

    def _normalize_country_name(self, country_name: Optional[str]) -> str:
        if not country_name:
            return ""
        return " ".join(country_name.strip().split())

    def _ensure_tables_exist(self):
        """Minimal check / init for SQLite. PostgreSQL should be initialized via SQL script."""
        if self.db_type == "sqlite":
            self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_runs'")
            if not self.cur.fetchone():
                schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
                if os.path.exists(schema_path):
                    with open(schema_path, "r") as f:
                        self.conn.executescript(f.read())
                    self.conn.commit()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
