#!/usr/bin/env python3
"""CrawlerNest QS end-to-end pipeline entrypoint.

Integration scope (minimal glue only):
1) crawlernest-jobs      -> crawl QS ranking + detail pages
2) crawlernest-extractors-> extract structured requirements
3) normalization baseline-> lightweight Python cleanup of fields
4) crawlernest-db-writer -> write into SQLite/PostgreSQL
5) crawlernest-kb        -> default SQLite location + CLI query
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parent
# Support both layouts:
# - script at repo root            -> modules under ./crawlernest
# - script inside ./crawlernest    -> modules under .
if (REPO_ROOT / "crawlernest-core").is_dir():
    MODULE_ROOT = REPO_ROOT
else:
    MODULE_ROOT = REPO_ROOT / "crawlernest"


# Integration point: make modular folders importable without redesign.
def _bootstrap_module_paths() -> None:
    module_dirs = [
        MODULE_ROOT / "crawlernest-core",
        MODULE_ROOT / "crawlernest-extractors",
        MODULE_ROOT / "crawlernest-jobs",
        MODULE_ROOT / "crawlernest-db-writer",
        MODULE_ROOT / "crawlernest-analytics",
    ]
    for mod_dir in module_dirs:
        if mod_dir.is_dir() and str(mod_dir) not in sys.path:
            sys.path.insert(0, str(mod_dir))


_bootstrap_module_paths()

from config import Config  # noqa: E402
from constants import COUNTRY_CODES, COUNTRY_NAME_ALIASES  # noqa: E402
from crawler import UniversityCrawler  # noqa: E402
from db_writer import DBWriter  # noqa: E402
from models import University  # noqa: E402


def _normalize_space(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_country(value: str) -> str:
    cleaned = _normalize_space(value)
    if not cleaned:
        return cleaned

    lowered = cleaned.lower()
    lowered = COUNTRY_NAME_ALIASES.get(lowered, lowered)
    lowered = "".join(
        ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch)
    )
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    lowered = _normalize_space(lowered)
    lowered = COUNTRY_NAME_ALIASES.get(lowered, lowered)

    for code, name in COUNTRY_CODES.items():
        if lowered == code.lower() or lowered == name.lower():
            return name

    return " ".join(part.capitalize() for part in lowered.split())


def _normalize_rank(rank_text: str) -> str:
    match = re.search(r"\d+", str(rank_text or ""))
    return match.group(0) if match else str(rank_text or "N/A")


def normalize_universities(universities: Iterable[University]) -> list[University]:
    """Python baseline normalization before DB write (no new features)."""
    normalized: list[University] = []
    for uni in universities:
        uni.rank = _normalize_rank(uni.rank)
        uni.name = _normalize_space(uni.name)
        uni.country = _normalize_country(uni.country)
        uni.path = _normalize_space(uni.path)

        # Keep metrics stable but cleaned (trim key/value whitespace).
        uni.table_metrics = {
            _normalize_space(str(k)): _normalize_space(str(v))
            for k, v in (uni.table_metrics or {}).items()
            if _normalize_space(str(k))
        }
        normalized.append(uni)

    return normalized


def ensure_sqlite_schema(db_path: Path) -> None:
    """Initialize SQLite schema from crawlernest-schema when DB is empty."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_runs'")
        if cur.fetchone():
            return

        schema_path = MODULE_ROOT / "crawlernest-schema" / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"schema.sql not found: {schema_path}")

        with schema_path.open("r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def run_qs_crawl(limit: int, ranking_id: str, use_async: bool) -> list[University]:
    config = Config(
        ranking_id=ranking_id,
        ranking_limit=limit,
        use_async=use_async,
        show_progress=True,
        output_format="console",
    )
    crawler = UniversityCrawler(config)
    if use_async:
        return asyncio.run(crawler.crawl_async())
    return crawler.crawl()


def write_universities(
    universities: Iterable[University],
    db_type: str,
    db_path: Optional[str],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> int:
    # Integration point: DB writer stays reusable; pipeline only orchestrates call order.
    if db_type == "sqlite":
        if not db_path:
            raise ValueError("db_path is required for sqlite")
        writer = DBWriter(db_type="sqlite", db_path=db_path)
    else:
        writer = DBWriter(
            db_type="postgres",
            host=pg_host,
            port=pg_port,
            database=pg_database,
            user=pg_user,
            password=pg_password,
        )

    inserted = 0
    crawl_run_id = writer.start_crawl_run(
        source_name="QS",
        ranking_type="world",
        notes="run_pipeline.py end-to-end QS run",
    )

    try:
        for uni in universities:
            raw_id = writer.insert_raw_record(
                source_name="QS",
                ranking_type="world",
                raw_json=uni.to_dict(),
                source_url=uni.qs_profile_path or uni.path or None,
                crawl_run_id=crawl_run_id,
                record_type="university_object",
            )
            university_id = writer.upsert_university(uni)
            writer.upsert_university_alias(
                university_id=university_id,
                source_name="QS",
                source_school_name=uni.name,
                match_type="exact",
                confidence_score=1.0,
            )
            writer.insert_ranking(
                university_id=university_id,
                uni=uni,
                ranking_source="QS",
                ranking_type="world",
                ranking_year=None,
                raw_id=raw_id,
            )
            writer.insert_admission_requirements(
                university_id=university_id,
                req=uni.requirements,
                raw_id=raw_id,
            )
            inserted += 1

        writer.finish_crawl_run(crawl_run_id, status="finished")
        writer.commit()
    except Exception:
        writer.finish_crawl_run(crawl_run_id, status="failed")
        writer.commit()
        raise
    finally:
        writer.close()

    return inserted


def query_rankings(db_type: str, db_path: Optional[str], keyword: str, limit: int) -> list[tuple]:
    if db_type != "sqlite":
        raise NotImplementedError("Query mode currently supports sqlite only.")
    if not db_path:
        raise ValueError("db_path is required for sqlite query mode")

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                r.rank_start,
                u.display_name,
                COALESCE(c.country_name, ''),
                r.score,
                r.ranking_type
            FROM rankings r
            JOIN universities u ON u.university_id = r.university_id
            LEFT JOIN countries c ON c.country_id = u.country_id
            WHERE u.display_name LIKE ?
            ORDER BY
                CASE WHEN r.rank_start IS NULL THEN 1 ELSE 0 END,
                r.rank_start ASC,
                r.ranking_id DESC
            LIMIT ?
            """,
            (f"%{keyword}%", limit),
        )
        return cur.fetchall()
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    default_db = MODULE_ROOT / "crawlernest-kb" / "databases" / "universities.db"

    parser = argparse.ArgumentParser(description="CrawlerNest QS end-to-end pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Crawl QS -> normalize -> write to DB")
    run_parser.add_argument("--ranking-id", default="3990755", help="QS ranking id (default: world)")
    run_parser.add_argument("--limit", type=int, default=30, help="Number of rows to ingest")
    run_parser.add_argument("--use-async", action="store_true", help="Use async crawler mode")
    run_parser.add_argument("--db-type", choices=["sqlite", "postgres"], default="sqlite")
    run_parser.add_argument("--db-path", default=str(default_db), help="SQLite DB path")
    run_parser.add_argument("--pg-host", default="localhost")
    run_parser.add_argument("--pg-port", type=int, default=5432)
    run_parser.add_argument("--pg-database", default="clawer")
    run_parser.add_argument("--pg-user", default="postgres")
    run_parser.add_argument("--pg-password", default="")

    query_parser = subparsers.add_parser("query", help="Query stored QS rankings from DB")
    query_parser.add_argument("keyword", help="University name keyword")
    query_parser.add_argument("--limit", type=int, default=20)
    query_parser.add_argument("--db-type", choices=["sqlite", "postgres"], default="sqlite")
    query_parser.add_argument("--db-path", default=str(default_db), help="SQLite DB path")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")

        if args.db_type == "sqlite":
            ensure_sqlite_schema(Path(args.db_path))

        print("[1/4] Crawling QS data...")
        universities = run_qs_crawl(
            limit=args.limit,
            ranking_id=args.ranking_id,
            use_async=args.use_async,
        )
        if not universities:
            print("No universities crawled. Exiting.")
            return 1

        print("[2/4] Normalizing fields (Python baseline)...")
        normalized = normalize_universities(universities)

        print(f"[3/4] Writing {len(normalized)} rows to {args.db_type}...")
        written = write_universities(
            universities=normalized,
            db_type=args.db_type,
            db_path=args.db_path,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )

        print("[4/4] Done.")
        print(f"Inserted rows: {written}")
        print("Query example:")
        print(f"  python run_pipeline.py query MIT --db-path {args.db_path}")
        return 0

    if args.command == "query":
        if args.db_type == "sqlite":
            ensure_sqlite_schema(Path(args.db_path))

        rows = query_rankings(
            db_type=args.db_type,
            db_path=args.db_path,
            keyword=args.keyword,
            limit=args.limit,
        )
        if not rows:
            print("No matching universities found.")
            return 0

        print("rank | university | country | score | ranking_type")
        for rank_start, display_name, country_name, score, ranking_type in rows:
            score_txt = "" if score is None else str(score)
            print(f"{rank_start} | {display_name} | {country_name} | {score_txt} | {ranking_type}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
