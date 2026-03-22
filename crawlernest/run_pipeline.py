#!/usr/bin/env python3
"""CrawlerNest QS end-to-end pipeline entrypoint (low-resource friendly)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path
from typing import Iterable, Optional, Any


REPO_ROOT = Path(__file__).resolve().parent
if (REPO_ROOT / "crawlernest-core").is_dir():
    MODULE_ROOT = REPO_ROOT
else:
    MODULE_ROOT = REPO_ROOT / "crawlernest"


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

WRITE_BATCH_SIZE = 100


def _normalize_space(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_country(value: str) -> str:
    cleaned = _normalize_space(value)
    if not cleaned:
        return cleaned
    lowered = COUNTRY_NAME_ALIASES.get(cleaned.lower(), cleaned.lower())
    lowered = "".join(ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    lowered = COUNTRY_NAME_ALIASES.get(_normalize_space(lowered), _normalize_space(lowered))
    for code, name in COUNTRY_CODES.items():
        if lowered in (code.lower(), name.lower()):
            return name
    return " ".join(part.capitalize() for part in lowered.split())


def _normalize_rank(rank_text: str) -> str:
    match = re.search(r"\d+", str(rank_text or ""))
    return match.group(0) if match else str(rank_text or "N/A")


def _uni_slug(uni: University) -> str:
    return uni.name.lower().replace(" ", "-").replace("(", "").replace(")", "")


def normalize_universities(universities: Iterable[University]) -> list[University]:
    out: list[University] = []
    for uni in universities:
        uni.rank = _normalize_rank(uni.rank)
        uni.name = _normalize_space(uni.name)
        uni.country = _normalize_country(uni.country)
        uni.path = _normalize_space(uni.path)
        uni.table_metrics = {
            _normalize_space(str(k)): _normalize_space(str(v))
            for k, v in (uni.table_metrics or {}).items()
            if _normalize_space(str(k))
        }
        out.append(uni)
    return out


def ensure_sqlite_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_runs'")
        if cur.fetchone():
            return
        schema_path = MODULE_ROOT / "crawlernest-schema" / "schema.sql"
        with schema_path.open("r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def run_qs_crawl(
    limit: int,
    ranking_id: str,
    use_async: bool,
    workers: int,
    request_delay: float,
    local_parse_workers: int,
    fetch_details: bool,
) -> list[University]:
    config = Config(
        ranking_id=ranking_id,
        ranking_limit=limit,
        use_async=use_async,
        show_progress=True,
        output_format="console",
        max_concurrent_requests=max(1, workers),
        request_delay=max(0.0, request_delay),
        local_parse_workers=max(1, local_parse_workers),
        fetch_details=bool(fetch_details),
    )
    crawler = UniversityCrawler(config)
    return asyncio.run(crawler.crawl_async()) if use_async else crawler.crawl()


def _read_mem_available_mb() -> Optional[float]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = float(line.split()[1])
                    return kb / 1024.0
    except Exception:
        return None
    return None


def adaptive_pause(enabled: bool, workers: int) -> None:
    if not enabled:
        return
    extra = 0.0
    try:
        load1 = os.getloadavg()[0]
        if load1 > max(3.0, workers * 1.0):
            extra += 0.2
        if load1 > 4.5:
            extra += 0.4
    except Exception:
        pass
    mem_mb = _read_mem_available_mb()
    if mem_mb is not None:
        if mem_mb < 512:
            extra += 0.6
        elif mem_mb < 1024:
            extra += 0.2
    if extra > 0:
        time.sleep(extra)


def load_snapshot(path: Path) -> list[University]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [University.from_dict(item) for item in data]


def save_snapshot(path: Path, universities: Iterable[University]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([u.to_dict() for u in universities], f, ensure_ascii=False)


def load_checkpoint(path: Path) -> set[str]:
    done_slugs: set[str] = set()

    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
            done_slugs.update(obj.get("done_slugs", []))
        except Exception:
            # Backward-compat fallback: line-based slug file.
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    slug = line.strip()
                    if slug:
                        done_slugs.add(slug)

    journal = _checkpoint_journal(path)
    if journal.exists():
        with journal.open("r", encoding="utf-8") as f:
            for line in f:
                slug = line.strip()
                if slug:
                    done_slugs.add(slug)

    return done_slugs


def _checkpoint_journal(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".journal")


def append_checkpoint(path: Path, new_slugs: set[str]) -> None:
    if not new_slugs:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    journal = _checkpoint_journal(path)
    with journal.open("a", encoding="utf-8") as f:
        for slug in sorted(new_slugs):
            f.write(slug)
            f.write("\n")


def compact_checkpoint(path: Path, done_slugs: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump({"done_slugs": sorted(done_slugs)}, f, ensure_ascii=False)
    tmp.replace(path)
    journal = _checkpoint_journal(path)
    if journal.exists():
        journal.unlink()


def write_universities(
    universities: Iterable[University],
    db_type: str,
    db_path: Optional[str],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    checkpoint_file: Path,
    resource_guard: bool,
    workers: int,
    write_batch_size: int = WRITE_BATCH_SIZE,
) -> tuple[int, int, int]:
    writer = DBWriter(db_type="sqlite", db_path=db_path) if db_type == "sqlite" else DBWriter(
        db_type="postgres", host=pg_host, port=pg_port, database=pg_database, user=pg_user, password=pg_password
    )

    done_slugs = load_checkpoint(checkpoint_file)
    inserted = 0
    skipped = 0
    failed = 0
    crawl_run_id = writer.start_crawl_run(source_name="QS", ranking_type="world", notes="low-resource pipeline run")
    pending_batch: list[tuple[str, University]] = []

    def _to_float(v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            return float(str(v).strip())
        except Exception:
            return None

    def _to_int(v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(str(v).strip())
        except Exception:
            return None

    def _norm_metrics(v: Any) -> Optional[str]:
        if not v:
            return None
        if isinstance(v, str):
            try:
                obj = json.loads(v)
                return json.dumps(obj, ensure_ascii=False, sort_keys=True)
            except Exception:
                vv = v.strip()
                return vv or None
        try:
            return json.dumps(v, ensure_ascii=False, sort_keys=True)
        except Exception:
            return None

    def _same_float(a: Any, b: Any, eps: float = 1e-9) -> bool:
        aa = _to_float(a)
        bb = _to_float(b)
        if aa is None and bb is None:
            return True
        if aa is None or bb is None:
            return False
        return abs(aa - bb) <= eps

    def _is_unchanged(existing: dict[str, Any], uni: University) -> bool:
        incoming_metrics = uni.table_metrics or {}
        incoming_score = _to_float(incoming_metrics.get("Overall Score"))
        incoming_qs_path = (uni.qs_profile_path or uni.path or None)

        req = uni.requirements
        req_gpa = getattr(req, "gpa", None) if req else None
        req_ielts = getattr(req, "ielts", None) if req else None
        req_toefl = getattr(req, "toefl", None) if req else None
        req_gre = getattr(req, "gre", None) if req else None
        req_gmat = getattr(req, "gmat", None) if req else None

        return (
            str(existing.get("name") or "") == str(uni.name or "")
            and str(existing.get("country") or "") == str(uni.country or "")
            and str(existing.get("qs_profile_path") or "") == str(incoming_qs_path or "")
            and _to_int(existing.get("rank_start")) == _to_int(uni.rank)
            and _same_float(existing.get("score"), incoming_score)
            and _norm_metrics(existing.get("metrics_json")) == _norm_metrics(incoming_metrics)
            and _same_float(existing.get("gpa"), req_gpa)
            and _same_float(existing.get("ielts"), req_ielts)
            and _same_float(existing.get("toefl"), req_toefl)
            and _same_float(existing.get("gre"), req_gre)
            and _same_float(existing.get("gmat"), req_gmat)
        )

    def _write_one(slug: str, uni: University) -> bool:
        nonlocal inserted, failed, done_slugs
        try:
            raw_id = writer.insert_raw_record(
                source_name="QS",
                ranking_type="world",
                raw_json=uni.to_dict(),
                source_url=uni.qs_profile_path or uni.path or None,
                crawl_run_id=crawl_run_id,
                record_type="university_object",
            )
            university_id = writer.upsert_university(uni)
            writer.upsert_university_alias(university_id, "QS", uni.name, "exact", 1.0)
            writer.insert_ranking(university_id, uni, "QS", "world", None, raw_id)
            writer.insert_admission_requirements(university_id, uni.requirements, raw_id)
            inserted += 1
            done_slugs.add(slug)
            return True
        except Exception as e:
            failed += 1
            print(f"[warn] skip write error for {uni.name}: {e}")
            return False

    def _flush_pending_batch() -> set[str]:
        nonlocal inserted, skipped, failed, done_slugs, pending_batch
        if not pending_batch:
            return set()

        appended_slugs: set[str] = set()
        existing_map = writer.get_existing_states_by_slugs(
            [slug for slug, _ in pending_batch],
            ranking_type="world",
            ranking_year=None,
        )
        to_write: list[tuple[str, University]] = []
        for slug, uni in pending_batch:
            existing = existing_map.get(slug)
            if existing is not None and _is_unchanged(existing, uni):
                skipped += 1
                done_slugs.add(slug)
                appended_slugs.add(slug)
                continue
            to_write.append((slug, uni))

        if not to_write:
            pending_batch = []
            return appended_slugs

        # Batch path currently optimized for SQLite; keep PostgreSQL on stable row-by-row path.
        if writer.db_type != "sqlite":
            for slug, uni in to_write:
                before = len(done_slugs)
                _write_one(slug, uni)
                if len(done_slugs) > before and slug in done_slugs:
                    appended_slugs.add(slug)
            pending_batch = []
            return appended_slugs

        raw_rows = [
            {
                "crawl_run_id": crawl_run_id,
                "source_name": "QS",
                "record_type": "university_object",
                "ranking_type": "world",
                "raw_json": uni.to_dict(),
                "raw_text": None,
                "source_url": uni.qs_profile_path or uni.path or None,
            }
            for _, uni in to_write
        ]

        try:
            raw_ids = writer.insert_raw_records_batch(raw_rows)

            alias_rows: list[tuple[int, str, str, str, float]] = []
            ranking_rows: list[tuple[int, Optional[int], str, str, Optional[int], Optional[int], Optional[int], Optional[float], Optional[str]]] = []
            admission_rows: list[tuple[int, Optional[int], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]] = []

            for (slug, uni), raw_id in zip(to_write, raw_ids):
                try:
                    university_id = writer.upsert_university(uni)
                except Exception as e:
                    failed += 1
                    print(f"[warn] skip write error for {uni.name}: {e}")
                    continue

                alias_rows.append((university_id, "QS", uni.name, "exact", 1.0))

                metrics_json = uni.table_metrics or {}
                score = writer._safe_float(metrics_json.get("Overall Score")) if metrics_json else None
                ranking_rows.append(
                    (
                        university_id,
                        raw_id,
                        "QS",
                        "world",
                        None,
                        writer._safe_int(uni.rank),
                        writer._safe_int(uni.rank),
                        score,
                        json.dumps(metrics_json, ensure_ascii=False) if metrics_json else None,
                    )
                )

                req = uni.requirements
                if req:
                    admission_rows.append(
                        (
                            university_id,
                            raw_id,
                            writer._safe_float(req.gpa),
                            writer._safe_float(req.ielts),
                            writer._safe_float(req.toefl),
                            writer._safe_float(req.gre),
                            writer._safe_float(req.gmat),
                        )
                    )

                inserted += 1
                done_slugs.add(slug)
                appended_slugs.add(slug)

            writer.upsert_university_aliases_batch(alias_rows)
            writer.insert_rankings_batch(ranking_rows)
            writer.insert_admission_requirements_batch(admission_rows)
        except Exception as e:
            # Safety net: fallback to stable row-by-row if batch insert fails unexpectedly.
            print(f"[warn] batch write failed, falling back to row-by-row for this chunk: {e}")
            for slug, uni in to_write:
                before = len(done_slugs)
                _write_one(slug, uni)
                if len(done_slugs) > before and slug in done_slugs:
                    appended_slugs.add(slug)
        finally:
            pending_batch = []
        return appended_slugs

    try:
        for i, uni in enumerate(universities, start=1):
            slug = _uni_slug(uni)
            if slug in done_slugs:
                skipped += 1
                continue

            adaptive_pause(resource_guard, workers)
            pending_batch.append((slug, uni))

            if len(pending_batch) >= max(1, write_batch_size):
                newly_done = _flush_pending_batch()
                writer.commit()
                append_checkpoint(checkpoint_file, newly_done)

        newly_done = _flush_pending_batch()
        writer.finish_crawl_run(crawl_run_id, status="finished" if failed == 0 else "partial")
        writer.commit()
        append_checkpoint(checkpoint_file, newly_done)
        compact_checkpoint(checkpoint_file, done_slugs)
    finally:
        writer.close()

    return inserted, skipped, failed


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
            SELECT r.rank_start, u.display_name, COALESCE(c.country_name, ''), r.score, r.ranking_type
            FROM rankings r
            JOIN universities u ON u.university_id = r.university_id
            LEFT JOIN countries c ON c.country_id = u.country_id
            WHERE u.display_name LIKE ?
            ORDER BY CASE WHEN r.rank_start IS NULL THEN 1 ELSE 0 END, r.rank_start ASC, r.ranking_id DESC
            LIMIT ?
            """,
            (f"%{keyword}%", limit),
        )
        return cur.fetchall()
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    default_db = MODULE_ROOT / "crawlernest-kb" / "databases" / "universities.db"
    default_snapshot = MODULE_ROOT / "crawlernest-kb" / "databases" / "last_crawl_snapshot.json"
    default_checkpoint = MODULE_ROOT / "crawlernest-kb" / "databases" / "pipeline_checkpoint.json"

    parser = argparse.ArgumentParser(description="CrawlerNest QS end-to-end pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Crawl QS -> normalize -> write to DB")
    run_parser.add_argument("--ranking-id", default="3990755")
    run_parser.add_argument("--limit", type=int, default=30)
    run_parser.add_argument("--workers", type=int, default=1, help="Max concurrent requests per crawler")
    run_parser.add_argument("--request-delay", type=float, default=10.0, help="Delay (seconds) between requests")
    run_parser.add_argument(
        "--local-parse-workers",
        type=int,
        default=4,
        help="Local CPU workers for parsing HTML into requirements (does not increase web request concurrency)",
    )
    run_parser.add_argument(
        "--rankings-only",
        action="store_true",
        help="Fetch rankings list only; skip per-university detail page fetching/extraction",
    )
    run_parser.add_argument(
        "--write-batch-size",
        type=int,
        default=WRITE_BATCH_SIZE,
        help="Commit/checkpoint interval during DB writes",
    )
    run_parser.add_argument("--use-async", action="store_true")
    run_parser.add_argument("--resource-guard", action="store_true", help="Auto slow down on high load / low memory")
    run_parser.add_argument("--resume", action="store_true", help="Resume from snapshot + checkpoint if available")
    run_parser.add_argument("--snapshot-file", default=str(default_snapshot))
    run_parser.add_argument("--checkpoint-file", default=str(default_checkpoint))
    run_parser.add_argument("--db-type", choices=["sqlite", "postgres"], default="sqlite")
    run_parser.add_argument("--db-path", default=str(default_db))
    run_parser.add_argument("--pg-host", default="localhost")
    run_parser.add_argument("--pg-port", type=int, default=5432)
    run_parser.add_argument("--pg-database", default="clawer")
    run_parser.add_argument("--pg-user", default="postgres")
    run_parser.add_argument("--pg-password", default="")

    query_parser = subparsers.add_parser("query", help="Query stored QS rankings from DB")
    query_parser.add_argument("keyword")
    query_parser.add_argument("--limit", type=int, default=20)
    query_parser.add_argument("--db-type", choices=["sqlite", "postgres"], default="sqlite")
    query_parser.add_argument("--db-path", default=str(default_db))
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "run":
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        if args.db_type == "sqlite":
            ensure_sqlite_schema(Path(args.db_path))

        snapshot_file = Path(args.snapshot_file)
        checkpoint_file = Path(args.checkpoint_file)

        if args.resume and snapshot_file.exists():
            print("[1/4] Loading snapshot (resume mode)...")
            universities = load_snapshot(snapshot_file)
        else:
            print("[1/4] Crawling QS data...")
            universities = run_qs_crawl(
                args.limit,
                args.ranking_id,
                args.use_async,
                args.workers,
                args.request_delay,
                args.local_parse_workers,
                not args.rankings_only,
            )
            if not universities:
                print("No universities crawled. Exiting.")
                return 1
            save_snapshot(snapshot_file, universities)

        print("[2/4] Normalizing fields (Python baseline)...")
        normalized = normalize_universities(universities)

        print(f"[3/4] Writing {len(normalized)} rows to {args.db_type}...")
        inserted, skipped, failed = write_universities(
            universities=normalized,
            db_type=args.db_type,
            db_path=args.db_path,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            checkpoint_file=checkpoint_file,
            resource_guard=args.resource_guard,
            workers=max(1, args.workers),
            write_batch_size=max(1, args.write_batch_size),
        )

        print("[4/4] Done.")
        print(f"Inserted: {inserted}, Skipped(resume): {skipped}, Failed: {failed}")
        print(f"Checkpoint: {checkpoint_file}")
        return 0

    if args.command == "query":
        if args.db_type == "sqlite":
            ensure_sqlite_schema(Path(args.db_path))
        rows = query_rankings(args.db_type, args.db_path, args.keyword, args.limit)
        if not rows:
            print("No matching universities found.")
            return 0
        print("rank | university | country | score | ranking_type")
        for rank_start, display_name, country_name, score, ranking_type in rows:
            print(f"{rank_start} | {display_name} | {country_name} | {'' if score is None else score} | {ranking_type}")
        return 0

    return 1


if __name__ == "__main__":
    start_time = time.time()
    try:
        sys.exit(main())
    finally:
        elapsed = time.time() - start_time
        print(f"\n--- Execution Finished in {elapsed:.2f} seconds ---")
