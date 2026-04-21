#!/usr/bin/env python3
"""CrawlerNest QS end-to-end pipeline entrypoint (low-resource friendly)."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Any

try:
    from pipeline.bootstrap import bootstrap_module_paths, resolve_repo_paths
    from pipeline.cli import build_parser as build_pipeline_parser
    from pipeline.router import dispatch as dispatch_basic_commands
    from pipeline.stages.crawl_stage import execute_run_crawl_stage
    from pipeline.stages.write_stage import execute_run_write_stage
except ModuleNotFoundError:  # pragma: no cover - package import compatibility
    from .pipeline.bootstrap import bootstrap_module_paths, resolve_repo_paths
    from .pipeline.cli import build_parser as build_pipeline_parser
    from .pipeline.router import dispatch as dispatch_basic_commands
    from .pipeline.stages.crawl_stage import execute_run_crawl_stage
    from .pipeline.stages.write_stage import execute_run_write_stage


REPO_ROOT, MODULE_ROOT = resolve_repo_paths(__file__)
bootstrap_module_paths(MODULE_ROOT)

from config import Config  # noqa: E402
from crawler import UniversityCrawler  # noqa: E402
from db_writer import DBWriter  # noqa: E402
from extractor import DataExtractor  # noqa: E402
from fetcher import UniversityFetcher  # noqa: E402
from models import University  # noqa: E402
from qs_universe_crawlers import (  # noqa: E402
    QSGlobalCrawler,
    QSRegionCrawler,
    QSSubjectCrawler,
    QSSpecialCrawler,
    save_universe_snapshot,
)
from qs_universe_registry import (  # noqa: E402
    get_qs_universe_spec,
    iter_all_qs_universes,
    iter_major_qs_universes,
)
from arwu_crawler import crawl_arwu_rankings  # noqa: E402
from the_crawler import crawl_the_rankings  # noqa: E402
from pipeline_command_router import (  # noqa: E402
    PipelineCommandDependencies,
    dispatch_command,
)
from entity_resolution import EntityResolver  # noqa: E402
from entity_resolution.repository import EntityResolutionRepository  # noqa: E402
from multi_source import MultiSourceRankingPipeline  # noqa: E402
from multi_source.adapters import ARWUAdapter, QSAdapter, THEAdapter  # noqa: E402
from multi_source.repository import MultiSourceRepository  # noqa: E402
from comparison import ComparisonRepository, compare_universities  # noqa: E402
from recommendation_engine import (  # noqa: E402
    RecommendationQuery,
    RecommendationRepository,
    default_recommendation_config,
    grouped_recommendations_to_dict,
    recommend_universities_v2,
    recommend_universities_v3,
)
from ranking_aggregation.repository import RankingAggregationRepository  # noqa: E402
try:
    from pipeline.utils.normalization import normalize_universities  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - package import compatibility
    from .pipeline.utils.normalization import normalize_universities  # noqa: E402

try:  # noqa: E402
    import psycopg2
    from psycopg2 import errors as psycopg2_errors
except ImportError:
    psycopg2 = None  # type: ignore
    psycopg2_errors = None  # type: ignore

WRITE_BATCH_SIZE = 100
DEFAULT_RANKING_YEAR = dt.datetime.now().year
_QS_PIPELINE_LOG = logging.getLogger("CrawlerNest.qs")


def _uni_slug(uni: University) -> str:
    return uni.name.lower().replace(" ", "-").replace("(", "").replace(")", "")


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
        MODULE_ROOT / "crawlernest-schema" / "ranking_aggregation_postgresql.sql",
        MODULE_ROOT / "crawlernest-schema" / "recommendation_postgresql.sql",
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


def run_qs_crawl(
    limit: int,
    ranking_year: int,
    ranking_id: str,
    use_async: bool,
    workers: int,
    request_delay: float,
    local_parse_workers: int,
    fetch_details: bool,
    detail_403_streak_threshold: int,
    detail_chunk_size: int,
) -> tuple[list[University], dict[str, Any]]:
    global_spec = get_qs_universe_spec("global", "global")
    preferred_ranking_id = str(ranking_id or "").strip()
    if not preferred_ranking_id:
        preferred_ranking_id = str(global_spec.ranking_id or "").strip()
    config = Config(
        ranking_id=preferred_ranking_id,
        ranking_page_url=global_spec.ranking_page_url,
        source_name="QS",
        ranking_year=ranking_year,
        universe_type="global",
        universe_key="global",
        ranking_limit=limit,
        use_async=use_async,
        show_progress=True,
        output_format="console",
        max_concurrent_requests=max(1, workers),
        request_delay=max(0.0, request_delay),
        local_parse_workers=max(1, local_parse_workers),
        fetch_details=bool(fetch_details),
        detail_forbidden_streak_threshold=max(1, detail_403_streak_threshold),
        detail_chunk_size=max(1, detail_chunk_size),
        resolution_cache_path=str(REPO_ROOT / "crawlernest-kb" / "qs_universe_resolution_cache.json"),
    )
    setattr(config, "_stable_ranking_id", str(global_spec.ranking_id or preferred_ranking_id or "").strip())
    setattr(config, "progress_label", "global/global")
    crawler = UniversityCrawler(config)
    universities = asyncio.run(crawler.crawl_async()) if use_async else crawler.crawl()
    crawl_meta = {
        "detail_fallback_triggered": bool(getattr(config, "_detail_fallback_triggered", False)),
        "detail_deferred_paths": list(getattr(config, "_detail_deferred_paths", []) or []),
        "detail_forbidden_count": int(getattr(config, "_detail_forbidden_count", 0) or 0),
        "failure_classification": str(getattr(config, "_last_failure_classification", "") or ""),
        "failure_message": str(getattr(config, "_last_failure_message", "") or ""),
        "live_fetch_classification": str(getattr(config, "_last_failure_classification", "") or "") or "live_ok",
        "live_fetch_message": str(getattr(config, "_last_failure_message", "") or ""),
        "ranking_id_source": str(getattr(config, "_ranking_id_source", "") or ""),
        "used_resolution_cache": bool(getattr(config, "_used_resolution_cache", False)),
        "resolved_ranking_id": str(getattr(config, "ranking_id", "") or ""),
        "ranking_id_candidates": list(getattr(config, "_ranking_id_candidates", []) or []),
        "resolved_ranking_page_url": str(getattr(config, "_resolved_ranking_page_url", "") or getattr(config, "ranking_page_url", "") or ""),
        "page_resolution_skipped": bool(getattr(config, "_page_resolution_skipped", False)),
        "page_resolution_attempted": bool(getattr(config, "_page_resolution_attempted", False)),
        "resolution_cache_path": str(getattr(config, "resolution_cache_path", "") or ""),
        "used_snapshot_fallback": False,
        "snapshot_fallback_path": "",
        "run_backing": "live",
    }
    universities, crawl_meta = _apply_qs_snapshot_fallback(
        universities,
        crawl_meta,
        artifact_base_dir=REPO_ROOT / "crawlernest-kb" / "qs_universes",
        ranking_year=ranking_year,
        universe_type="global",
        universe_key="global",
    )
    return universities, crawl_meta


def _print_qs_entry_strategy(crawl_meta: dict[str, Any], *, prefix: str = "[entry]") -> None:
    ranking_id_source = str(crawl_meta.get("ranking_id_source", "") or "").strip() or "unknown"
    used_cache = bool(crawl_meta.get("used_resolution_cache", False))
    resolved_ranking_id = str(crawl_meta.get("resolved_ranking_id", "") or "").strip() or "n/a"
    page_resolution_skipped = bool(crawl_meta.get("page_resolution_skipped", False))
    page_resolution_attempted = bool(crawl_meta.get("page_resolution_attempted", False))
    live_fetch_classification = str(crawl_meta.get("live_fetch_classification", "") or "").strip() or "live_ok"
    run_backing = str(crawl_meta.get("run_backing", "") or "").strip() or "live"
    used_snapshot_fallback = bool(crawl_meta.get("used_snapshot_fallback", False))
    print(
        f"{prefix} ranking_id_source={ranking_id_source} "
        f"used_cache={'yes' if used_cache else 'no'} "
        f"ranking_id={resolved_ranking_id} "
        f"page_resolution_skipped={'yes' if page_resolution_skipped else 'no'}"
    )
    print(
        f"{prefix} live_fetch_classification={live_fetch_classification} "
        f"run_backing={run_backing} "
        f"fallback_snapshot_used={'yes' if used_snapshot_fallback else 'no'}"
    )
    resolved_page = str(crawl_meta.get("resolved_ranking_page_url", "") or "").strip()
    if resolved_page:
        print(f"{prefix} resolved_ranking_page_url={resolved_page}")
    cache_path = str(crawl_meta.get("resolution_cache_path", "") or "").strip()
    if cache_path and used_cache:
        print(f"{prefix} resolution_cache_path={cache_path}")
    if page_resolution_attempted:
        print(f"{prefix} page_resolution_attempted=yes")
    live_fetch_message = str(crawl_meta.get("live_fetch_message", "") or "").strip()
    if live_fetch_message:
        print(f"{prefix} live_fetch_message={live_fetch_message}")
    snapshot_path = str(crawl_meta.get("snapshot_fallback_path", "") or "").strip()
    if snapshot_path:
        print(f"{prefix} fallback_snapshot_path={snapshot_path}")


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


def save_standardized_rows(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: list[dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "__dict__"):
            payload.append(dict(row.__dict__))
        else:
            payload.append(dict(row))
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def save_json_artifact(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _qs_universe_artifact_dir(base_dir: Path, ranking_year: int, universe_type: str, universe_key: str) -> Path:
    return base_dir / str(ranking_year) / str(universe_type) / str(universe_key)


def _load_known_good_qs_snapshot(
    base_dir: Path,
    *,
    ranking_year: int,
    universe_type: str,
    universe_key: str,
) -> tuple[list[University], Path] | tuple[None, Path]:
    universe_dir = _qs_universe_artifact_dir(base_dir, ranking_year, universe_type, universe_key)
    raw_snapshot_path = universe_dir / "raw_snapshot.json"
    run_status_path = universe_dir / "run_status.json"
    if not raw_snapshot_path.exists() or not run_status_path.exists():
        return None, raw_snapshot_path
    try:
        run_status = json.loads(run_status_path.read_text(encoding="utf-8"))
    except Exception:
        return None, raw_snapshot_path
    if str(run_status.get("status", "") or "").strip().lower() != "ok":
        return None, raw_snapshot_path
    try:
        universities = load_snapshot(raw_snapshot_path)
    except Exception:
        return None, raw_snapshot_path
    if not universities:
        return None, raw_snapshot_path
    return universities, raw_snapshot_path


def _apply_qs_snapshot_fallback(
    universities: list[University],
    crawl_meta: dict[str, Any],
    *,
    artifact_base_dir: Path,
    ranking_year: int,
    universe_type: str,
    universe_key: str,
) -> tuple[list[University], dict[str, Any]]:
    updated_meta = dict(crawl_meta)
    failure_classification = str(updated_meta.get("failure_classification", "") or "").strip()
    failure_message = str(updated_meta.get("failure_message", "") or "").strip()
    updated_meta.setdefault("live_fetch_classification", failure_classification or "live_ok")
    updated_meta.setdefault("live_fetch_message", failure_message)
    updated_meta.setdefault("used_snapshot_fallback", False)
    updated_meta.setdefault("snapshot_fallback_path", "")
    updated_meta.setdefault("run_backing", "live")
    if universities or failure_classification not in ("upstream_blocked", "upstream_maintenance"):
        return universities, updated_meta

    fallback_universities, snapshot_path = _load_known_good_qs_snapshot(
        artifact_base_dir,
        ranking_year=ranking_year,
        universe_type=universe_type,
        universe_key=universe_key,
    )
    updated_meta["snapshot_fallback_path"] = str(snapshot_path)
    if fallback_universities is None:
        updated_meta["used_snapshot_fallback"] = False
        updated_meta["run_backing"] = "live_blocked_no_fallback"
        _QS_PIPELINE_LOG.info(
            "qs_acquire event=fallback_used status=failed reason=no_snapshot "
            "universe_type=%s universe_key=%s ranking_year=%s snapshot_path=%s",
            universe_type,
            universe_key,
            ranking_year,
            snapshot_path,
        )
        return universities, updated_meta

    updated_meta["used_snapshot_fallback"] = True
    updated_meta["run_backing"] = "fallback_snapshot"
    _QS_PIPELINE_LOG.info(
        "qs_acquire event=fallback_used status=ok universe_type=%s universe_key=%s ranking_year=%s "
        "snapshot_path=%s row_count=%s",
        universe_type,
        universe_key,
        ranking_year,
        snapshot_path,
        len(fallback_universities),
    )
    return fallback_universities, updated_meta


def _qs_terminal_fetch_for_continuous_loop(crawl_meta: dict[str, Any]) -> bool:
    """If True, do not spin the run-qs-* ``while True`` daemon another pass (blocked / unrecoverable this run)."""
    fc = str(crawl_meta.get("failure_classification", "") or "").strip()
    if fc in {
        "upstream_blocked",
        "upstream_maintenance",
        "resolve_blocked",
        "resolve_not_found",
        "fetch_failed",
        "network_error",
        "data_unavailable",
    }:
        return True
    run_backing = str(crawl_meta.get("run_backing", "") or "").strip()
    if run_backing == "live_blocked_no_fallback":
        return True
    return False


def save_deferred_detail_list(path: Path, universities: Iterable[University], deferred_paths: Iterable[str]) -> int:
    deferred_set = {str(p).strip() for p in deferred_paths if str(p).strip()}
    if not deferred_set:
        return 0

    rows: list[dict[str, Any]] = []
    for uni in universities:
        if uni.path not in deferred_set:
            continue
        rows.append(
            {
                "school_slug": _uni_slug(uni),
                "name": uni.name,
                "rank": uni.rank,
                "country": uni.country,
                "path": uni.path,
            }
        )

    unique_rows: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    for row in rows:
        slug = str(row.get("school_slug", ""))
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        unique_rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(unique_rows, f, ensure_ascii=False, indent=2)
    return len(unique_rows)


# ── Enrichment cooldown & retry helpers ─────────────────────────────────────

class _JsOnlyPage(Exception):
    """Raised when a detail page is a JS-rendered shell with no extractable text."""


_FAILURE_COOLDOWN_HOURS: dict[str, float] = {
    "http_403": 12.0,        # scaled: N * 12h, capped at _FAILURE_MAX_COOLDOWN_HOURS
    "http_timeout": 2.0,
    "http_error": 6.0,
    "parse_no_signal": 24.0,
    "js_only_permanent": float("inf"),  # never retry
    "missing_canonical": float("inf"),  # never retry until re-seeded
    "system_error": 1.0,
}
_FAILURE_MAX_COOLDOWN_HOURS: float = 72.0


def _classify_enrichment_failure(exc: Exception) -> tuple[str, bool, float]:
    """Return (failure_type, retryable, base_cooldown_hours) from an enrichment exception."""
    if isinstance(exc, _JsOnlyPage):
        return "js_only_permanent", False, float("inf")
    name = type(exc).__name__
    msg = str(exc)
    if "Timeout" in name or "timeout" in msg.lower():
        return "http_timeout", True, 2.0
    if "HTTPError" in name:
        return ("http_403", True, 12.0) if "403" in msg else ("http_error", True, 6.0)
    if any(k in name for k in ("ConnectionError", "ChunkedEncoding", "RequestException")):
        return "http_error", True, 6.0
    if "No admission signal" in msg:
        return "parse_no_signal", True, 24.0
    if "Empty response" in msg:
        return "http_403", True, 12.0  # most common root cause for empty body
    return "system_error", True, 1.0


def _is_in_cooldown(item: dict[str, Any], now: dt.datetime) -> bool:
    """Return True if next_retry_at is set and still in the future."""
    nr = item.get("next_retry_at")
    if not nr:
        return False
    try:
        nrdt = dt.datetime.fromisoformat(str(nr))
        if nrdt.tzinfo is None:
            nrdt = nrdt.replace(tzinfo=dt.timezone.utc)
        return now < nrdt
    except Exception:
        return False


def _migrate_deferred_item(item: dict[str, Any]) -> dict[str, Any]:
    """Migrate v1 deferred item (uses `attempts`) to v2 schema (uses `failure_count`)."""
    out: dict[str, Any] = {
        "school_slug": str(item.get("school_slug") or "").strip(),
        "path": str(item.get("path") or "").strip(),
        "name": item.get("name"),
        "rank": item.get("rank"),
        "country": item.get("country"),
        # Migrate: prefer failure_count; fall back to old attempts field
        "failure_count": int(item.get("failure_count", item.get("attempts", 0))),
    }
    for field in ("last_failure_type", "last_attempt_at", "next_retry_at"):
        if item.get(field) is not None:
            out[field] = item[field]
    return out


def _write_deferred_file(path: Path, items: list[dict[str, Any]]) -> None:
    """Write deferred items to disk, deduplicating by school_slug."""
    path.parent.mkdir(parents=True, exist_ok=True)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        slug = str(item.get("school_slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(item)
    path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")


def load_deferred_detail_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        migrated = _migrate_deferred_item(item)
        if not migrated["school_slug"] or not migrated["path"]:
            continue
        out.append(migrated)
    return out


def _has_admission_signal(req: Any) -> bool:
    if req is None:
        return False
    for key in ("gpa", "ielts", "toefl", "gre", "gmat"):
        if getattr(req, key, None) is not None:
            return True
    return False


def _resolve_university_ids_by_slugs(writer: DBWriter, slugs: list[str]) -> dict[str, int]:
    uniq = [s for s in dict.fromkeys([str(x).strip() for x in slugs if str(x).strip()])]
    if not uniq:
        return {}
    p = writer._get_placeholder()
    table = writer._get_schema_prefix("universities")
    in_ph = ", ".join([p] * len(uniq))
    writer.cur.execute(
        f"SELECT school_slug, university_id FROM {table} WHERE school_slug IN ({in_ph})",
        tuple(uniq),
    )
    rows = writer.cur.fetchall()
    return {str(slug): int(uid) for slug, uid in rows}


def enrich_deferred_details(
    deferred_file: Path,
    db_type: str,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    limit: int,
    request_delay: float,
    timeout: int,
) -> tuple[int, int, int, int, int]:
    """Enrich deferred university detail pages with cooldown/retry policy.

    Returns:
        (success, skipped_cooldown, failed, skipped_no_uid, remaining_count)
    """
    rows = load_deferred_detail_list(deferred_file)
    if not rows:
        print("[info] No deferred items found — nothing to enrich.")
        return 0, 0, 0, 0, 0

    now_utc = dt.datetime.now(dt.timezone.utc)

    # Partition: items still in cooldown (skip) vs eligible to attempt
    cooldown_items: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for item in rows:
        if _is_in_cooldown(item, now_utc):
            nr = item.get("next_retry_at", "unknown")
            slug = item.get("school_slug", "?")
            print(f"[cooldown] skip {slug!r} — next retry at {nr}")
            cooldown_items.append(item)
        else:
            eligible.append(item)

    skipped_cooldown = len(cooldown_items)
    take = eligible[: max(1, limit)] if limit > 0 else eligible
    rest_eligible = eligible[len(take):]  # eligible but beyond --limit

    if not take:
        print(f"[info] All {len(rows)} deferred item(s) in cooldown — nothing to attempt this run.")
        _write_deferred_file(deferred_file, rows)
        return 0, skipped_cooldown, 0, 0, len(rows)

    if db_type != "postgres":
        raise ValueError("CrawlerNest is now PostgreSQL-only. Use db_type='postgres'.")
    writer = DBWriter(db_type="postgres", host=pg_host, port=pg_port, database=pg_database, user=pg_user, password=pg_password)
    fetcher = UniversityFetcher(
        Config(
            request_delay=max(0.0, request_delay),
            timeout=max(1, int(timeout)),
            use_async=False,
            show_progress=False,
            fetch_details=True,
        )
    )
    extractor = DataExtractor()

    success = 0
    failed = 0
    skipped_no_uid = 0
    remaining_after_attempt: list[dict[str, Any]] = []
    exhausted: list[dict[str, Any]] = []

    crawl_run_id = writer.start_crawl_run(
        source_name="QS",
        ranking_type="world",
        notes="detail enrichment from deferred list",
    )
    slug_to_uid = _resolve_university_ids_by_slugs(writer, [str(x.get("school_slug", "")) for x in take])

    try:
        total = len(take)
        for i, item in enumerate(take, start=1):
            slug = str(item.get("school_slug") or "").strip()
            path_v = str(item.get("path") or "").strip()
            if not slug or not path_v:
                failed += 1
                remaining_after_attempt.append(item)
                continue

            uid = slug_to_uid.get(slug)
            if uid is None:
                skipped_no_uid += 1
                print(f"[skip] {slug!r} — not found in DB (missing_canonical); moved to exhausted")
                exhausted.append({
                    **item,
                    "failure_count": int(item.get("failure_count", 0)) + 1,
                    "last_failure_type": "missing_canonical",
                    "last_attempt_at": now_utc.isoformat(),
                    "next_retry_at": None,
                    "status": "missing_canonical",
                })
                continue

            try:
                html = fetcher.fetch_university_detail(path_v)
                if not html:
                    raise ValueError("Empty response (possible 403/redirect)")

                # Pre-check: JS-rendered shell has very little extractable text
                _plain = re.sub(r"<[^>]+>", "", html[:4000])
                _plain = re.sub(r"\s+", " ", _plain).strip()
                if len(_plain) < 200:
                    raise _JsOnlyPage(f"JS-rendered shell ({len(_plain)} chars) for {slug!r}")

                req = extractor.extract_requirements(html)
                if not _has_admission_signal(req):
                    raise ValueError("No admission signal (gpa/ielts/toefl/gre/gmat) in parsed HTML")

                raw_id = writer.insert_raw_record(
                    source_name="QS",
                    ranking_type="world",
                    raw_json={
                        "school_slug": slug,
                        "path": path_v,
                        "requirements": req.to_dict() if hasattr(req, "to_dict") else None,
                    },
                    source_url=path_v,
                    crawl_run_id=crawl_run_id,
                    record_type="detail_enrichment",
                )
                writer.insert_admission_requirements(uid, req, raw_id)
                success += 1
                print(f"[ok] enriched {slug!r}")

            except Exception as _exc:
                failed += 1
                failure_type, retryable, base_hours = _classify_enrichment_failure(_exc)
                failure_count = int(item.get("failure_count", 0)) + 1

                # Compute cooldown: http_403 scales with failure_count
                if failure_type == "http_403":
                    cooldown_h = min(base_hours * failure_count, _FAILURE_MAX_COOLDOWN_HOURS)
                else:
                    cooldown_h = base_hours

                updated: dict[str, Any] = {
                    **item,
                    "failure_count": failure_count,
                    "last_failure_type": failure_type,
                    "last_attempt_at": now_utc.isoformat(),
                }

                if retryable and cooldown_h < float("inf"):
                    next_retry = now_utc + dt.timedelta(hours=cooldown_h)
                    updated["next_retry_at"] = next_retry.isoformat()
                    retry_str = f"retry after {cooldown_h:.0f}h (next: {next_retry.strftime('%Y-%m-%d %H:%M UTC')})"
                    remaining_after_attempt.append(updated)
                else:
                    updated["next_retry_at"] = None
                    updated["status"] = failure_type
                    retry_str = f"permanent — no retry ({failure_type})"
                    exhausted.append(updated)

                print(
                    f"[warn] {slug!r} ({path_v!r})\n"
                    f"       cause={type(_exc).__name__}: {_exc}\n"
                    f"       class={failure_type} | {retry_str}"
                )

            pct = int(i / max(1, total) * 100)
            filled = pct // 5
            bar = "\u2588" * filled + "\u2591" * (20 - filled)
            print(f"\r  [{bar}] {pct:>3}%  {i}/{total} detail enrich", end="", flush=True)

        if total > 0:
            print()

        writer.finish_crawl_run(crawl_run_id, status="finished" if failed == 0 else "partial")
        writer.commit()
    except Exception:
        writer.finish_crawl_run(crawl_run_id, status="failed")
        writer.commit()
        raise
    finally:
        try:
            fetcher.close()
        except Exception:
            pass
        writer.close()

    # Rebuild deferred file: still-cooling items + retryable failures + eligible not yet attempted
    final_deferred = cooldown_items + remaining_after_attempt + rest_eligible
    _write_deferred_file(deferred_file, final_deferred)

    # Write exhausted items to separate file for manual inspection
    if exhausted:
        exhausted_file = deferred_file.parent / "exhausted_detail_enrichment.json"
        existing_exhausted: list[dict[str, Any]] = []
        if exhausted_file.exists():
            try:
                existing_exhausted = json.loads(exhausted_file.read_text(encoding="utf-8"))
                if not isinstance(existing_exhausted, list):
                    existing_exhausted = []
            except Exception:
                existing_exhausted = []
        merged_ex: list[dict[str, Any]] = []
        seen_ex: set[str] = set()
        for ex_item in exhausted + existing_exhausted:
            ex_slug = str(ex_item.get("school_slug") or "").strip()
            if not ex_slug or ex_slug in seen_ex:
                continue
            seen_ex.add(ex_slug)
            merged_ex.append(ex_item)
        exhausted_file.write_text(json.dumps(merged_ex, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[info] {len(exhausted)} exhausted item(s) written to {exhausted_file}")

    return success, skipped_cooldown, failed, skipped_no_uid, len(final_deferred)




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
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    checkpoint_file: Path,
    resource_guard: bool,
    workers: int,
    resume: bool = False,
    ranking_year: Optional[int] = None,
    write_batch_size: int = WRITE_BATCH_SIZE,
) -> tuple[int, int, int]:
    if db_type != "postgres":
        raise ValueError("CrawlerNest is now PostgreSQL-only. Use db_type='postgres'.")
    writer = DBWriter(db_type="postgres", host=pg_host, port=pg_port, database=pg_database, user=pg_user, password=pg_password)

    done_slugs = load_checkpoint(checkpoint_file) if resume else set()
    inserted = 0
    skipped = 0
    failed = 0
    crawl_run_id = writer.start_crawl_run(source_name="QS", ranking_type="world", notes="low-resource pipeline run")
    writer.commit()  # Ensure the crawl run ID is committed immediately for foreign key satisfaction
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
            writer.insert_ranking(university_id, uni, "QS", "world", ranking_year, raw_id)
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
            ranking_year=ranking_year,
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
            admission_rows: list[
                tuple[
                    int,
                    Optional[int],
                    Optional[float],
                    Optional[float],
                    Optional[float],
                    Optional[float],
                    Optional[float],
                    Optional[str],
                    Optional[str],
                    Optional[str],
                ]
            ] = []

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
                        ranking_year,
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
                            getattr(req, "application_deadline_text", None),
                            getattr(req, "raw_text", None),
                            getattr(req, "parsed_status", None),
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
            # CRITICAL: We MUST rollback here because a failed command in PostgreSQL aborts the transaction.
            writer.rollback()
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


def _connect_postgres(
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> Any:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL mode")
    return psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )


def _build_multi_source_pipeline(conn: Any) -> MultiSourceRankingPipeline:
    er_repo = EntityResolutionRepository(conn)
    profiles = er_repo.load_canonical_profiles()
    if not profiles:
        raise RuntimeError(
            "No canonical university profiles found. Seed entity resolution tables before multi-source ingestion."
        )
    resolver = EntityResolver(profiles)
    return MultiSourceRankingPipeline(
        resolver=resolver,
        multi_source_repo=MultiSourceRepository(conn),
        aggregation_repo=RankingAggregationRepository(conn),
    )


def sync_qs_multi_source_rankings(
    universities: Iterable[University],
    ranking_year: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    batch_id: str | None = None,
    ranking_type: str = "world",
    universe_type: str = "global",
    universe_key: str = "global",
    enable_aggregation: bool = True,
) -> Any:
    effective_run_id = batch_id or (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        pipeline = _build_multi_source_pipeline(conn)
        standardized = QSAdapter(
            ranking_year=ranking_year,
            ranking_type=ranking_type,
            universe_type=universe_type,
            universe_key=universe_key,
        ).adapt(list(universities))
        return pipeline.ingest_records(
            standardized,
            batch_id=effective_run_id,
            run_label_prefix="qs_pipeline_sync",
            ranking_type=ranking_type,
            enable_aggregation=enable_aggregation,
        )
    finally:
        conn.close()


def _build_qs_universe_crawler(
    universe_type: str,
    universe_key: str,
    *,
    limit: int,
    ranking_year: int,
    use_async: bool,
    workers: int,
    request_delay: float,
    local_parse_workers: int,
) -> tuple[Any, Any]:
    spec = get_qs_universe_spec(universe_type, universe_key)
    crawler_kwargs = {
        "spec": spec,
        "limit": limit,
        "ranking_year": ranking_year,
        "use_async": use_async,
        "workers": workers,
        "request_delay": request_delay,
        "local_parse_workers": local_parse_workers,
    }
    if spec.universe_type == "global":
        return spec, QSGlobalCrawler(**crawler_kwargs)
    if spec.universe_type == "region":
        return spec, QSRegionCrawler(**crawler_kwargs)
    if spec.universe_type == "subject":
        return spec, QSSubjectCrawler(**crawler_kwargs)
    return spec, QSSpecialCrawler(**crawler_kwargs)


def run_qs_universe_ingestion(
    *,
    universe_type: str,
    universe_key: str,
    limit: int,
    ranking_year: int,
    use_async: bool,
    workers: int,
    request_delay: float,
    local_parse_workers: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    output_dir: Path,
    resume: bool = False,
) -> tuple[Any, list[University], list[Any], bool, dict[str, Any]]:
    spec, crawler = _build_qs_universe_crawler(
        universe_type,
        universe_key,
        limit=limit,
        ranking_year=ranking_year,
        use_async=use_async,
        workers=workers,
        request_delay=request_delay,
        local_parse_workers=local_parse_workers,
    )
    universe_dir = output_dir / str(ranking_year) / spec.universe_type / spec.universe_key
    raw_snapshot_path = universe_dir / "raw_snapshot.json"
    existing_universities: list[University] = []
    if resume and raw_snapshot_path.exists():
        existing_universities = load_snapshot(raw_snapshot_path)
        print(
            f"[{spec.universe_type}/{spec.universe_key}] [resume] "
            f"loaded {len(existing_universities)} universities from {raw_snapshot_path}"
        )
    universities, crawl_meta = crawler.crawl(existing_universities=existing_universities)
    universities, crawl_meta = _apply_qs_snapshot_fallback(
        universities,
        crawl_meta,
        artifact_base_dir=output_dir,
        ranking_year=ranking_year,
        universe_type=spec.universe_type,
        universe_key=spec.universe_key,
    )
    _print_qs_entry_strategy(crawl_meta, prefix=f"[{spec.universe_type}/{spec.universe_key}] [entry]")
    failure_classification = str(crawl_meta.get("failure_classification", "") or "").strip()
    if failure_classification:
        failure_message = str(crawl_meta.get("failure_message", "") or "").strip() or "no additional detail"
        print(
            f"[{spec.universe_type}/{spec.universe_key}] [entry] "
            f"failure_classification={failure_classification} message={failure_message}"
        )
    save_json_artifact(universe_dir / "crawl_meta.json", crawl_meta)
    try:
        normalized = normalize_universities(universities)
    except Exception as exc:
        save_json_artifact(
            universe_dir / "run_status.json",
            {
                "status": "failed",
                "failure_classification": "normalize_failed",
                "message": str(exc),
                "universe_type": spec.universe_type,
                "universe_key": spec.universe_key,
                "ranking_year": ranking_year,
                "crawl_meta": crawl_meta,
            },
        )
        raise

    standardized = QSAdapter(
        ranking_year=ranking_year,
        ranking_type=spec.ranking_type,
        universe_type=spec.universe_type,
        universe_key=spec.universe_key,
    ).adapt(normalized)

    save_snapshot(universe_dir / "raw_snapshot.json", universities)
    save_universe_snapshot(universe_dir / "normalized_snapshot.json", normalized, spec, ranking_year)
    save_standardized_rows(universe_dir / "standardized_rows.json", standardized)

    run_id = (
        f"qs-{spec.universe_type}-{spec.universe_key}-{ranking_year}-"
        f"{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    try:
        summary = sync_qs_multi_source_rankings(
            normalized,
            ranking_year=ranking_year,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
            batch_id=run_id,
            ranking_type=spec.ranking_type,
            universe_type=spec.universe_type,
            universe_key=spec.universe_key,
            enable_aggregation=spec.enable_aggregation,
        )
    except Exception as exc:
        save_json_artifact(
            universe_dir / "run_status.json",
            {
                "status": "failed",
                "failure_classification": "ingest_failed",
                "message": str(exc),
                "run_id": run_id,
                "universe_type": spec.universe_type,
                "universe_key": spec.universe_key,
                "ranking_year": ranking_year,
                "crawl_meta": crawl_meta,
                "normalized_count": len(normalized),
                "standardized_count": len(standardized),
            },
        )
        raise
    save_json_artifact(
        universe_dir / "run_status.json",
        {
            "status": "ok",
            "failure_classification": str(crawl_meta.get("failure_classification", "") or ""),
            "message": str(crawl_meta.get("failure_message", "") or ""),
            "run_id": run_id,
            "universe_type": spec.universe_type,
            "universe_key": spec.universe_key,
            "ranking_year": ranking_year,
            "crawl_meta": crawl_meta,
            "normalized_count": len(normalized),
            "standardized_count": len(standardized),
            "rows_written": summary.rows_written,
            "rows_updated": summary.rows_updated,
            "matched_count": summary.matched_count,
            "unresolved_count": summary.unresolved_count,
            "aggregated_years": list(summary.years_aggregated),
        },
    )
    return summary, normalized, standardized, crawler.interrupted, crawl_meta


def ingest_rankings_payload(
    source: str,
    payload: list[Any],
    ranking_year: int,
    ranking_type: str,
    source_version: Optional[str],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    batch_id: str | None = None,
) -> Any:
    source_code = str(source or "").strip().upper()
    if source_code == "QS":
        adapter = QSAdapter(ranking_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = [row if isinstance(row, University) else University.from_dict(row) for row in payload]
    elif source_code == "THE":
        adapter = THEAdapter(default_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = payload
    elif source_code == "ARWU":
        adapter = ARWUAdapter(default_year=ranking_year, ranking_type=ranking_type, source_version=source_version)
        adapter_payload = payload
    else:
        raise ValueError(f"Unsupported source: {source}. Expected one of QS, THE, ARWU.")

    effective_run_id = batch_id or (
        f"{source_code.lower()}-{ranking_type}-{ranking_year}-"
        f"{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        pipeline = _build_multi_source_pipeline(conn)
        standardized = adapter.adapt(adapter_payload)
        return pipeline.ingest_records(
            standardized,
            batch_id=effective_run_id,
            run_label_prefix=f"{source_code.lower()}_payload_ingest",
            ranking_type=ranking_type,
        )
    finally:
        conn.close()


def load_json_payload(path: Path) -> list[Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return rows
    raise ValueError(f"Unsupported payload format in {path}. Expected a JSON array or an object with a 'rows' array.")


def run_the_rankings_ingestion(
    *,
    ranking_year: int,
    output_dir: Path,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    skip_seed: bool = False,
) -> dict[str, Any]:
    print(f"[the-rankings] crawling THE world rankings for year={ranking_year}...")
    output_file = crawl_the_rankings(year=ranking_year, output_dir=output_dir)
    payload = load_json_payload(output_file)

    print(f"[the-rankings] ingesting {len(payload)} rows into multi-source pipeline...")
    ingest_summary = ingest_rankings_payload(
        source="THE",
        payload=payload,
        ranking_year=ranking_year,
        ranking_type="world",
        source_version=None,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        batch_id=f"the-{ranking_year}",
    )

    aggregated_rows = int(getattr(ingest_summary, "aggregated_row_count", 0) or 0)
    if not skip_seed:
        print("[the-rankings] seeding canonical entities...")
        seed_canonical_universities(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )

        print("[the-rankings] backfilling ranking records...")
        backfill_summary = backfill_qs_ranking_records_from_legacy(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        aggregated_rows = int(backfill_summary.get("aggregated_rows") or aggregated_rows)

    summary = {
        "rows_crawled": len(payload),
        "matched_count": int(getattr(ingest_summary, "matched_count", 0) or 0),
        "unresolved_count": int(getattr(ingest_summary, "unresolved_count", 0) or 0),
        "aggregated_rows": aggregated_rows,
        "output_file": str(output_file),
    }
    print(
        f"[the-rankings] done. matched={summary['matched_count']} "
        f"unresolved={summary['unresolved_count']} aggregated_rows={summary['aggregated_rows']}"
    )
    return summary


def run_arwu_rankings_ingestion(
    *,
    ranking_year: int,
    output_dir: Path,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    skip_seed: bool = False,
) -> dict[str, Any]:
    print(f"[arwu-rankings] crawling ARWU world rankings for year={ranking_year}...")
    output_file = crawl_arwu_rankings(year=ranking_year, output_dir=output_dir)
    payload = load_json_payload(output_file)

    print(f"[arwu-rankings] ingesting {len(payload)} rows into multi-source pipeline...")
    ingest_summary = ingest_rankings_payload(
        source="ARWU",
        payload=payload,
        ranking_year=ranking_year,
        ranking_type="world",
        source_version=None,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        batch_id=f"arwu-{ranking_year}",
    )

    aggregated_rows = int(getattr(ingest_summary, "aggregated_row_count", 0) or 0)
    if not skip_seed:
        print("[arwu-rankings] seeding canonical entities...")
        seed_canonical_universities(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )

        print("[arwu-rankings] backfilling ranking records...")
        backfill_summary = backfill_qs_ranking_records_from_legacy(
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        aggregated_rows = int(backfill_summary.get("aggregated_rows") or aggregated_rows)

    summary = {
        "rows_crawled": len(payload),
        "matched_count": int(getattr(ingest_summary, "matched_count", 0) or 0),
        "unresolved_count": int(getattr(ingest_summary, "unresolved_count", 0) or 0),
        "aggregated_rows": aggregated_rows,
        "output_file": str(output_file),
    }
    print(
        f"[arwu-rankings] done. matched={summary['matched_count']} "
        f"unresolved={summary['unresolved_count']} aggregated_rows={summary['aggregated_rows']}"
    )
    return summary


def validate_global_multi_source(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
    ranking_year: Optional[int] = None,
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        with conn.cursor() as cur:
            params: list[Any] = []
            year_clause = ""
            year_clause_agg = ""
            if ranking_year is not None:
                year_clause = "AND rr.ranking_year = %s"
                year_clause_agg = "AND ar.ranking_year = %s"
                params.append(int(ranking_year))

            cur.execute(
                f"""
                SELECT rs.source_code, COUNT(*)::INT
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.universe_type = 'global'
                  AND rr.universe_key = 'global'
                  {year_clause}
                GROUP BY rs.source_code
                ORDER BY rs.source_code
                """,
                tuple(params),
            )
            source_rows = cur.fetchall()
            source_counts = {str(source_code): int(count) for source_code, count in source_rows}

            cur.execute(
                f"""
                SELECT COUNT(*)::INT
                FROM (
                    SELECT rr.canonical_university_id
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.ranking_source rs
                      ON rs.ranking_source_id = rr.ranking_source_id
                    WHERE rr.universe_type = 'global'
                      AND rr.universe_key = 'global'
                      {year_clause}
                    GROUP BY rr.canonical_university_id
                    HAVING COUNT(DISTINCT rs.source_code) > 1
                ) t
                """,
                tuple(params),
            )
            multi_source_canonical_count = int(cur.fetchone()[0] or 0)

            cur.execute(
                f"""
                SELECT COUNT(*)::INT
                FROM analytics.aggregated_rankings ar
                WHERE ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                  {year_clause_agg}
                  AND (
                      SELECT COUNT(*)
                      FROM jsonb_object_keys(ar.source_ranks_json)
                  ) > 1
                """,
                tuple([int(ranking_year)]) if ranking_year is not None else (),
            )
            aggregated_multi_source_rows = int(cur.fetchone()[0] or 0)

        return {
            "ranking_year": ranking_year,
            "universe_type": "global",
            "universe_key": "global",
            "sources_present": {
                source: source_counts.get(source, 0) > 0
                for source in ("QS", "THE", "ARWU")
            },
            "source_row_counts": source_counts,
            "multi_source_canonical_count": multi_source_canonical_count,
            "aggregated_multi_source_rows": aggregated_multi_source_rows,
        }
    finally:
        conn.close()


def _normalize_display_name_for_canonical(display_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(display_name or "").strip().lower())
    return " ".join(normalized.split())


def _slugify_canonical_name(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(display_name or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-")


def seed_canonical_from_missing_entities(
    *,
    source_code: str,
    ranking_year: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    seeded = 0
    skipped = 0
    failed = 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT raw_name, country_hint
                FROM analytics.missing_entity_log
                WHERE source_code = %s
                  AND COALESCE(raw_name, '') <> ''
                ORDER BY raw_name ASC, country_hint ASC NULLS LAST
                """,
                (source_code,),
            )
            missing_rows = cur.fetchall()

            for raw_name, country_hint in missing_rows:
                display_name = str(raw_name or "").strip()
                if not display_name:
                    skipped += 1
                    continue

                canonical_slug = _slugify_canonical_name(display_name)
                if not canonical_slug:
                    failed += 1
                    continue

                display_name_normalized = _normalize_display_name_for_canonical(display_name)

                cur.execute(
                    """
                    SELECT canonical_university_id
                    FROM warehouse.canonical_university
                    WHERE canonical_slug = %s
                    """,
                    (canonical_slug,),
                )
                existing = cur.fetchone()
                if existing is not None:
                    skipped += 1
                    continue

                country_id = None
                country_hint_text = str(country_hint or "").strip()
                if country_hint_text:
                    cur.execute(
                        """
                        SELECT country_id
                        FROM warehouse.countries
                        WHERE country_name ILIKE %s
                        LIMIT 1
                        """,
                        (country_hint_text,),
                    )
                    country_row = cur.fetchone()
                    if country_row is not None:
                        country_id = int(country_row[0])
                    else:
                        cur.execute(
                            """
                            INSERT INTO warehouse.countries (country_name)
                            VALUES (%s)
                            ON CONFLICT (country_name) DO NOTHING
                            RETURNING country_id
                            """,
                            (country_hint_text,),
                        )
                        inserted_country = cur.fetchone()
                        if inserted_country is not None:
                            country_id = int(inserted_country[0])
                        else:
                            cur.execute(
                                """
                                SELECT country_id
                                FROM warehouse.countries
                                WHERE country_name ILIKE %s
                                LIMIT 1
                                """,
                                (country_hint_text,),
                            )
                            fallback_country = cur.fetchone()
                            if fallback_country is not None:
                                country_id = int(fallback_country[0])

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                        status
                    )
                    VALUES (%s, %s, %s, %s, 'active')
                    ON CONFLICT (canonical_slug) DO NOTHING
                    RETURNING canonical_university_id
                    """,
                    (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                    ),
                )
                inserted_row = cur.fetchone()
                if inserted_row is not None:
                    seeded += 1
                else:
                    skipped += 1

        conn.commit()
        return {
            "seeded": seeded,
            "skipped": skipped,
            "failed": failed,
            "source_code": source_code,
            "ranking_year": ranking_year,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def seed_canonical_universities(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    seeded = 0
    skipped = 0
    failed = 0
    refreshed_years: list[int] = []
    aggregated_rows = 0

    unresolved_sql = """
        SELECT
            u.university_id,
            u.school_slug,
            u.display_name,
            u.country_id,
            u.city_name,
            u.website_url
        FROM warehouse.universities u
        LEFT JOIN warehouse.canonical_university_link cul
          ON cul.university_id = u.university_id
        WHERE cul.university_id IS NULL
        ORDER BY u.university_id ASC
    """

    total_skipped_sql = """
        SELECT COUNT(*)
        FROM warehouse.universities u
        JOIN warehouse.canonical_university_link cul
          ON cul.university_id = u.university_id
    """

    try:
        with conn.cursor() as cur:
            cur.execute(total_skipped_sql)
            skipped = int(cur.fetchone()[0] or 0)

            cur.execute(unresolved_sql)
            unresolved_rows = cur.fetchall()

            for (
                university_id,
                school_slug,
                display_name,
                country_id,
                city_name,
                website_url,
            ) in unresolved_rows:
                normalized_name = _normalize_display_name_for_canonical(str(display_name or ""))

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        country_id,
                        city_name,
                        website_url,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    ON CONFLICT (canonical_slug) DO NOTHING
                    RETURNING canonical_university_id
                    """,
                    (
                        school_slug,
                        display_name,
                        normalized_name,
                        country_id,
                        city_name,
                        website_url,
                    ),
                )
                row = cur.fetchone()
                if row is not None:
                    canonical_university_id = int(row[0])
                else:
                    cur.execute(
                        """
                        SELECT canonical_university_id
                        FROM warehouse.canonical_university
                        WHERE canonical_slug = %s
                        """,
                        (school_slug,),
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        failed += 1
                        continue
                    canonical_university_id = int(existing[0])

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university_link (
                        canonical_university_id,
                        university_id,
                        link_method,
                        confidence_score,
                        is_primary
                    )
                    VALUES (%s, %s, 'seed_canonical', 1.0000, TRUE)
                    ON CONFLICT (university_id) DO NOTHING
                    RETURNING canonical_university_link_id
                    """,
                    (canonical_university_id, university_id),
                )
                linked = cur.fetchone()
                if linked is not None:
                    seeded += 1
                else:
                    skipped += 1

            cur.execute(
                """
                SELECT DISTINCT ranking_year
                FROM warehouse.ranking_record
                WHERE ranking_type = 'world'
                ORDER BY ranking_year
                """
            )
            years = [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

        if years:
            pipeline = _build_multi_source_pipeline(conn)
            aggregated_rows = pipeline._refresh_aggregations(  # type: ignore[attr-defined]
                years,
                ranking_type="world",
                run_label_prefix="seed_canonical",
            )
            refreshed_years = years

        conn.commit()
        return {
            "seeded": seeded,
            "skipped": skipped,
            "failed": failed,
            "years_aggregated": refreshed_years,
            "aggregated_rows": aggregated_rows,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def backfill_qs_ranking_records_from_legacy(
    *,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    backfilled = 0
    skipped = 0
    failed = 0
    refreshed_years: list[int] = []
    aggregated_rows = 0
    run_id = (
        "backfill-qs-ranking-records-"
        f"{dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}"
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.ranking_source (source_code, source_name, source_version)
                VALUES ('QS', 'QS World University Rankings', NULL)
                ON CONFLICT (source_code)
                DO UPDATE SET source_name = EXCLUDED.source_name
                RETURNING ranking_source_id
                """
            )
            row = cur.fetchone()
            if row is not None:
                ranking_source_id = int(row[0])
            else:
                cur.execute(
                    """
                    SELECT ranking_source_id
                    FROM warehouse.ranking_source
                    WHERE source_code = 'QS'
                    """
                )
                existing_source = cur.fetchone()
                if existing_source is None:
                    raise RuntimeError("Unable to resolve QS ranking_source_id for backfill.")
                ranking_source_id = int(existing_source[0])

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key,
                        r.rank_start AS rank_position,
                        r.score,
                        r.source_url,
                        COALESCE(r.metrics_json, '{}'::jsonb) AS metadata
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                SELECT COUNT(*)
                FROM candidate_rows
                """
                ,
                (ranking_source_id,),
            )
            total_candidates = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                SELECT COUNT(*)
                FROM candidate_rows c
                JOIN warehouse.ranking_record rr
                  ON rr.canonical_university_id = c.canonical_university_id
                 AND rr.ranking_source_id = c.ranking_source_id
                 AND rr.ranking_year = c.ranking_year
                 AND rr.ranking_type = c.ranking_type
                 AND rr.universe_type = c.universe_type
                 AND rr.universe_key = c.universe_key
                """
                ,
                (ranking_source_id,),
            )
            skipped = int(cur.fetchone()[0] or 0)

            cur.execute(
                """
                WITH candidate_rows AS (
                    SELECT DISTINCT ON (
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world')
                    )
                        cul.canonical_university_id,
                        %s::smallint AS ranking_source_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world') AS ranking_type,
                        'global'::text AS universe_type,
                        'global'::text AS universe_key,
                        r.rank_start AS rank_position,
                        r.score,
                        r.source_url,
                        COALESCE(r.metrics_json, '{}'::jsonb) AS metadata
                    FROM warehouse.rankings r
                    JOIN warehouse.canonical_university_link cul
                      ON cul.university_id = r.university_id
                    WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                      AND r.ranking_year IS NOT NULL
                    ORDER BY
                        cul.canonical_university_id,
                        r.ranking_year,
                        COALESCE(NULLIF(r.ranking_type, ''), 'world'),
                        r.rank_start ASC,
                        r.ranking_id DESC
                )
                INSERT INTO warehouse.ranking_record (
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_url,
                    metadata,
                    updated_at,
                    run_id
                )
                SELECT
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_url,
                    metadata,
                    CURRENT_TIMESTAMP,
                    %s
                FROM candidate_rows
                ON CONFLICT (
                    canonical_university_id,
                    ranking_source_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key
                )
                DO UPDATE SET
                    rank_position = EXCLUDED.rank_position,
                    score = EXCLUDED.score,
                    source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP,
                    run_id = EXCLUDED.run_id,
                    ingested_at = CURRENT_TIMESTAMP
                """
                ,
                (ranking_source_id, run_id),
            )

            backfilled = max(0, total_candidates - skipped)

            cur.execute(
                """
                SELECT DISTINCT ranking_year
                FROM warehouse.ranking_record
                WHERE ranking_type = 'world'
                ORDER BY ranking_year
                """
            )
            years = [int(row[0]) for row in cur.fetchall() if row and row[0] is not None]

        if years:
            pipeline = _build_multi_source_pipeline(conn)
            aggregated_rows = pipeline._refresh_aggregations(  # type: ignore[attr-defined]
                years,
                ranking_type="world",
                run_label_prefix="backfill_qs_ranking_records",
            )
            refreshed_years = years

        conn.commit()
        return {
            "run_id": run_id,
            "backfilled": backfilled,
            "skipped": skipped,
            "failed": failed,
            "years_aggregated": refreshed_years,
            "aggregated_rows": aggregated_rows,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_rankings(
    db_type: str,
    keyword: str,
    limit: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> list[tuple]:
    if db_type != "postgres":
        raise ValueError("CrawlerNest query mode is now PostgreSQL-only.")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT r.rank_start, u.display_name, COALESCE(c.country_name, ''), r.score, r.ranking_type
            FROM warehouse.rankings r
            JOIN warehouse.universities u ON u.university_id = r.university_id
            LEFT JOIN warehouse.countries c ON c.country_id = u.country_id
            WHERE u.display_name ILIKE %s
            ORDER BY CASE WHEN r.rank_start IS NULL THEN 1 ELSE 0 END, r.rank_start ASC, r.ranking_id DESC
            LIMIT %s
            """,
            (f"%{keyword}%", limit),
        )
        return cur.fetchall()
    finally:
        conn.close()


def recommend_universities_from_db(
    country: Optional[str],
    ielts_score: Optional[float],
    target_rank: Optional[int],
    preferred_ranking_source: Optional[str],
    limit: int,
    ranking_year: Optional[int],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> list[Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL recommendation mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        repo = RecommendationRepository(conn)
        query = RecommendationQuery(
            country=country,
            ielts_score=ielts_score,
            target_rank=target_rank,
            preferred_ranking_source=preferred_ranking_source,
            limit=limit,
            ranking_year=ranking_year,
        )
        return repo.run_recommendation_query(query, default_recommendation_config(), run_label="run_pipeline_recommend")
    finally:
        conn.close()


def compare_universities_from_db(
    identifiers: list[str | int],
    ranking_year: Optional[int],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL comparison mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        repo = ComparisonRepository(conn)
        rows = repo.resolve_universities(identifiers, ranking_year=ranking_year)
        return compare_universities(rows)
    finally:
        conn.close()


def recommend_universities_v2_from_db(
    country: Optional[str],
    ielts_score: Optional[float],
    target_rank: int,
    risk_profile: Optional[str],
    preferred_ranking_source: Optional[str],
    limit: int,
    ranking_year: Optional[int],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL recommendation mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        repo = RecommendationRepository(conn)
        query = RecommendationQuery(
            country=country,
            ielts_score=ielts_score,
            target_rank=target_rank,
            risk_profile=risk_profile,
            preferred_ranking_source=preferred_ranking_source,
            limit=limit,
            ranking_year=ranking_year,
        )
        candidates = repo.fetch_candidates(ranking_year=ranking_year, country=country)
        grouped = recommend_universities_v2(candidates, query, config=default_recommendation_config())
        return grouped_recommendations_to_dict(grouped)
    finally:
        conn.close()


def _parse_preference_weights(raw: Optional[str]) -> dict[str, float]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid preference weight JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("preference_weights must be a JSON object")
    parsed: dict[str, float] = {}
    for key, value in payload.items():
        try:
            parsed[str(key)] = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid preference weight for {key!r}") from exc
    return parsed


def recommend_universities_v3_from_db(
    country: Optional[str],
    country_policy: Optional[str],
    ielts_score: Optional[float],
    target_rank: int,
    risk_profile: Optional[str],
    preference_weights: dict[str, float],
    preferred_ranking_source: Optional[str],
    limit: int,
    ranking_year: Optional[int],
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL recommendation mode")
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        config = default_recommendation_config()
        repo = RecommendationRepository(conn)
        query = RecommendationQuery(
            country=country,
            country_policy=country_policy,
            ielts_score=ielts_score,
            target_rank=target_rank,
            risk_profile=risk_profile,
            preference_weights=preference_weights,
            preferred_ranking_source=preferred_ranking_source,
            limit=limit,
            ranking_year=ranking_year,
        )
        effective_country = country if (country and (country_policy or config.country_match_policy) == "hard_filter") else None
        candidates = repo.fetch_candidates(ranking_year=ranking_year, country=effective_country)
        grouped = recommend_universities_v3(candidates, query, config=config)
        return grouped_recommendations_to_dict(grouped)
    finally:
        conn.close()


def rebuild_universe_records_diagnostic(
    *,
    ranking_year: int,
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> dict[str, Any]:
    conn = _connect_postgres(pg_host, pg_port, pg_database, pg_user, pg_password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM warehouse.rankings r
                JOIN warehouse.canonical_university_link cul
                  ON cul.university_id = r.university_id
                WHERE COALESCE(NULLIF(r.ranking_type, ''), 'world') = 'world'
                  AND r.ranking_year = %s
                """,
                (ranking_year,),
            )
            legacy_global_count = int(cur.fetchone()[0] or 0)

            universe_statuses: list[dict[str, Any]] = []
            missing_universes: list[str] = []
            for spec in iter_all_qs_universes():
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM warehouse.ranking_record
                    WHERE ranking_year = %s
                      AND universe_type = %s
                      AND universe_key = %s
                    """,
                    (ranking_year, spec.universe_type, spec.universe_key),
                )
                record_count = int(cur.fetchone()[0] or 0)
                label = f"{spec.universe_type}/{spec.universe_key}"
                universe_statuses.append(
                    {
                        "universe_type": spec.universe_type,
                        "universe_key": spec.universe_key,
                        "record_count": record_count,
                    }
                )
                if record_count == 0:
                    print(f"[rebuild] universe {label} has 0 records — marking for re-crawl")
                    missing_universes.append(label)

        return {
            "ranking_year": ranking_year,
            "legacy_global_count": legacy_global_count,
            "missing_universes": missing_universes,
            "universe_statuses": universe_statuses,
        }
    finally:
        conn.close()




def build_parser() -> argparse.ArgumentParser:
    return build_pipeline_parser(
        MODULE_ROOT,
        default_ranking_year=DEFAULT_RANKING_YEAR,
        write_batch_size=WRITE_BATCH_SIZE,
    )


def _handle_run_command(args: argparse.Namespace) -> int:
    crawl_result = execute_run_crawl_stage(
        args,
        ensure_postgres_schema=ensure_postgres_schema,
        load_snapshot=load_snapshot,
        run_qs_crawl=run_qs_crawl,
        save_snapshot=save_snapshot,
        save_deferred_detail_list=save_deferred_detail_list,
        print_qs_entry_strategy=_print_qs_entry_strategy,
    )

    if crawl_result.deferred_count > 0:
        print(
            f"[note] Deferred detail enrichment items: {crawl_result.deferred_count} "
            f"(saved to {Path(args.deferred_details_file)})"
        )

    if crawl_result.crawl_meta.get("detail_fallback_triggered"):
        print(
            "[note] Detail auto-degrade was triggered by repeated 403 responses; "
            "run deferred detail enrichment in smaller batches."
        )
        print(
            f"[note] Observed detail 403 count in this run: "
            f"{crawl_result.crawl_meta.get('detail_forbidden_count', 0)}"
        )

    execute_run_write_stage(
        args,
        universities=crawl_result.universities,
        normalize_universities=normalize_universities,
        write_universities=write_universities,
        sync_qs_multi_source_rankings=sync_qs_multi_source_rankings,
    )

    if getattr(args, "with_the_rankings", False):
        try:
            the_ranking_year = int(getattr(args, "the_ranking_year", 2026))
            print(
                f"[THE] Ingesting THE world rankings (structured JSON / __NEXT_DATA__ path; "
                f"batch_id=the-{the_ranking_year})..."
            )
            the_summary = run_the_rankings_ingestion(
                ranking_year=the_ranking_year,
                output_dir=Path(getattr(args, "the_output_dir", str(MODULE_ROOT / "crawlernest-kb" / "databases"))),
                pg_host=args.pg_host,
                pg_port=args.pg_port,
                pg_database=args.pg_database,
                pg_user=args.pg_user,
                pg_password=args.pg_password,
                skip_seed=bool(getattr(args, "the_skip_seed", False)),
            )
            print(
                f"[THE_CRAWL] pipeline_done rows={the_summary['rows_crawled']} "
                f"matched={the_summary['matched_count']} unresolved={the_summary['unresolved_count']} "
                f"source=THE year={the_ranking_year}"
            )
        except Exception as exc:
            print(f"[warn] THE rankings ingestion skipped: {exc}")

    return 0


def _handle_query_command(args: argparse.Namespace) -> int:
    rows = query_rankings(
        args.db_type,
        args.keyword,
        args.limit,
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )
    if not rows:
        print("No matching universities found.")
        return 0
    print("rank | university | country | score | ranking_type")
    for rank_start, display_name, country_name, score, ranking_type in rows:
        print(f"{rank_start} | {display_name} | {country_name} | {'' if score is None else score} | {ranking_type}")
    return 0


def _handle_enrich_details_command(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        raise SystemExit("--limit must be a positive integer")
    ensure_postgres_schema(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)

    print("[1/2] Enriching deferred detail pages...")
    success, skipped_cooldown, failed, skipped_no_uid, remaining = enrich_deferred_details(
        deferred_file=Path(args.deferred_details_file),
        db_type=args.db_type,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        limit=args.limit,
        request_delay=args.request_delay,
        timeout=args.timeout,
    )
    print("[2/2] Done.")
    print(
        f"Attempted: {success + failed}  |  Enriched: {success}  |  Failed: {failed}  "
        f"|  Cooldown-skipped: {skipped_cooldown}  |  No-DB-match: {skipped_no_uid}"
    )
    print(f"Deferred remaining: {remaining}")
    print(f"Deferred file: {Path(args.deferred_details_file)}")
    return 0


def _build_dispatch_dependencies() -> PipelineCommandDependencies:
    return PipelineCommandDependencies(
        ensure_postgres_schema=ensure_postgres_schema,
        load_snapshot=load_snapshot,
        run_qs_crawl=run_qs_crawl,
        save_snapshot=save_snapshot,
        save_deferred_detail_list=save_deferred_detail_list,
        normalize_universities=normalize_universities,
        write_universities=write_universities,
        sync_qs_multi_source_rankings=sync_qs_multi_source_rankings,
        run_the_rankings_ingestion=run_the_rankings_ingestion,
        query_rankings=query_rankings,
        enrich_deferred_details=enrich_deferred_details,
        load_json_payload=load_json_payload,
        ingest_rankings_payload=ingest_rankings_payload,
        run_qs_universe_ingestion=run_qs_universe_ingestion,
        qs_terminal_fetch_for_continuous_loop=_qs_terminal_fetch_for_continuous_loop,
        iter_all_qs_universes=iter_all_qs_universes,
        iter_major_qs_universes=iter_major_qs_universes,
        get_qs_universe_spec=get_qs_universe_spec,
        recommend_universities_from_db=recommend_universities_from_db,
        recommend_universities_v2_from_db=recommend_universities_v2_from_db,
        recommend_universities_v3_from_db=recommend_universities_v3_from_db,
        compare_universities_from_db=compare_universities_from_db,
        parse_preference_weights=_parse_preference_weights,
    )


def _run_sample_crawl_export(
    command: str,
    output_file: str,
    *,
    normalized_output_file: str | None = None,
    staging_output_file: str | None = None,
) -> tuple[Path, int, Path | None, Path | None]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    try:
        from pipeline.sample_crawl_exports import (  # noqa: E402
            run_admission_sample_export,
            run_ranking_sample_export,
        )
    except ModuleNotFoundError:  # pragma: no cover - package import compatibility
        from .pipeline.sample_crawl_exports import (  # noqa: E402
            run_admission_sample_export,
            run_ranking_sample_export,
        )

    output_path = Path(output_file)
    if command == "crawl-ranking":
        normalized_path = Path(normalized_output_file) if normalized_output_file else None
        staging_path = Path(staging_output_file) if staging_output_file else None
        return run_ranking_sample_export(
            output_path,
            normalized_output_path=normalized_path,
            staging_output_path=staging_path,
        )
    if command == "crawl-admission":
        normalized_path = Path(normalized_output_file) if normalized_output_file else None
        staging_path = Path(staging_output_file) if staging_output_file else None
        return run_admission_sample_export(
            output_path,
            normalized_output_path=normalized_path,
            staging_output_path=staging_path,
        )
    raise ValueError(f"Unsupported sample crawl command: {command}")


def _validate_ranking_staging(staging_file: str) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.validator import (  # noqa: E402
        summary_to_dict,
        validate_ranking_staging_file,
    )

    summary = validate_ranking_staging_file(Path(staging_file))
    return summary_to_dict(summary)


def _validate_admission_staging(staging_file: str) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.validator import (  # noqa: E402
        summary_to_dict,
        validate_admission_staging_file,
    )

    summary = validate_admission_staging_file(Path(staging_file))
    return summary_to_dict(summary)


def _ingest_ranking_staging(
    staging_file: str,
    sqlite_db_file: str,
    *,
    allow_partial: bool,
    write_target: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.ingest import (  # noqa: E402
        ingest_ranking_staging_file,
        ingest_summary_to_dict,
    )

    summary = ingest_ranking_staging_file(
        Path(staging_file),
        Path(sqlite_db_file),
        allow_partial=allow_partial,
        write_target=write_target,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return ingest_summary_to_dict(summary)


def _ingest_admission_staging(
    staging_file: str,
    sqlite_db_file: str,
    *,
    allow_partial: bool,
    write_target: str,
    staging_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.writer import (  # noqa: E402
        ingest_admission_staging_file,
        ingest_summary_to_dict,
    )

    summary = ingest_admission_staging_file(
        Path(staging_file),
        Path(sqlite_db_file),
        allow_partial=allow_partial,
        write_target=write_target,
        staging_table=staging_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return ingest_summary_to_dict(summary)


def _preview_ranking_warehouse_map(
    *,
    input_source: str,
    staging_input_file: str,
    staging_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
        warehouse_rows_to_jsonable,
        write_warehouse_preview,
    )

    if input_source == "jsonl":
        staging_rows = load_staging_rows_from_jsonl(Path(staging_input_file))
        source_location = str(Path(staging_input_file))
    elif input_source == "postgres":
        staging_rows = load_staging_rows_from_postgres(
            table_name=staging_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        source_location = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{staging_table}"
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    mapped_rows = map_staging_rows_to_warehouse_rows(staging_rows)
    output_path = Path(output_file)
    write_warehouse_preview(mapped_rows, output_path)
    preview_payload = warehouse_rows_to_jsonable(mapped_rows[:5])

    return {
        "input_source": input_source,
        "source_location": source_location,
        "row_count": len(mapped_rows),
        "output_file": str(output_path),
        "preview_rows": preview_payload,
    }


def _preview_admission_warehouse_map(
    *,
    input_source: str,
    staging_input_file: str,
    staging_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
        warehouse_rows_to_jsonable,
        write_warehouse_preview,
    )

    if input_source == "jsonl":
        staging_rows = load_staging_rows_from_jsonl(Path(staging_input_file))
        source_location = str(Path(staging_input_file))
    elif input_source == "postgres":
        staging_rows = load_staging_rows_from_postgres(
            table_name=staging_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        source_location = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{staging_table}"
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    mapped_rows = map_staging_rows_to_warehouse_rows(staging_rows)
    output_path = Path(output_file)
    write_warehouse_preview(mapped_rows, output_path)
    preview_payload = warehouse_rows_to_jsonable(mapped_rows[:5])

    return {
        "input_source": input_source,
        "source_location": source_location,
        "row_count": len(mapped_rows),
        "output_file": str(output_path),
        "preview_rows": preview_payload,
    }


def _write_ranking_warehouse_preview(
    *,
    input_source: str,
    preview_input_file: str,
    staging_input_file: str,
    staging_table: str,
    landing_schema: str,
    landing_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_ranking_crawler.warehouse_writer import (  # noqa: E402
        load_warehouse_preview_rows,
        warehouse_landing_summary_to_dict,
        write_warehouse_landing_rows,
    )

    if input_source == "preview-json":
        rows = load_warehouse_preview_rows(Path(preview_input_file))
    elif input_source == "jsonl":
        rows = map_staging_rows_to_warehouse_rows(load_staging_rows_from_jsonl(Path(staging_input_file)))
    elif input_source == "postgres":
        rows = map_staging_rows_to_warehouse_rows(
            load_staging_rows_from_postgres(
                table_name=staging_table,
                pg_host=pg_host,
                pg_port=pg_port,
                pg_database=pg_database,
                pg_user=pg_user,
                pg_password=pg_password,
            )
        )
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    summary = write_warehouse_landing_rows(
        rows,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        schema_name=landing_schema,
        table_name=landing_table,
    )
    return warehouse_landing_summary_to_dict(summary)


def _write_admission_warehouse_preview(
    *,
    input_source: str,
    preview_input_file: str,
    staging_input_file: str,
    staging_table: str,
    landing_schema: str,
    landing_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_admission_crawler.warehouse_writer import (  # noqa: E402
        load_warehouse_preview_rows,
        warehouse_landing_summary_to_dict,
        write_warehouse_landing_rows,
    )

    if input_source == "preview-json":
        rows = load_warehouse_preview_rows(Path(preview_input_file))
    elif input_source == "jsonl":
        rows = map_staging_rows_to_warehouse_rows(load_staging_rows_from_jsonl(Path(staging_input_file)))
    elif input_source == "postgres":
        rows = map_staging_rows_to_warehouse_rows(
            load_staging_rows_from_postgres(
                table_name=staging_table,
                pg_host=pg_host,
                pg_port=pg_port,
                pg_database=pg_database,
                pg_user=pg_user,
                pg_password=pg_password,
            )
        )
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    summary = write_warehouse_landing_rows(
        rows,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        schema_name=landing_schema,
        table_name=landing_table,
    )
    return warehouse_landing_summary_to_dict(summary)


def _resolve_admission_entities(
    *,
    target_schema: str,
    target_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.entity_resolver import (  # noqa: E402
        entity_resolution_summary_to_dict,
        resolve_admission_preview_entities,
    )

    summary = resolve_admission_preview_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
    )
    return entity_resolution_summary_to_dict(summary)


def _get_unresolved_admission_entities(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.unresolved_report import (  # noqa: E402
        get_unresolved_admission_entities,
        unresolved_rows_to_dicts,
        write_unresolved_report,
    )

    rows = get_unresolved_admission_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
    )
    if output_file:
        write_unresolved_report(rows, Path(output_file))

    return {
        "target_table": f"{target_schema}.{target_table}",
        "row_count": len(rows),
        "rows": unresolved_rows_to_dicts(rows),
        "output_file": output_file,
    }


def _refresh_admission_resolution(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    full_summary_limit = 1_000_000

    before_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    resolution_summary = _resolve_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    after_full_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    after_display_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
        output_file=output_file,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    before_unresolved_count = sum(int(row["occurrence_count"]) for row in before_summary["rows"])
    after_unresolved_count = sum(int(row["occurrence_count"]) for row in after_full_summary["rows"])

    return {
        "target_table": before_summary["target_table"],
        "before_unresolved_count": before_unresolved_count,
        "before_distinct_university_count": before_summary["row_count"],
        "after_unresolved_count": after_unresolved_count,
        "after_distinct_university_count": after_full_summary["row_count"],
        "resolved_row_count": resolution_summary["resolved_row_count"],
        "unresolved_row_count": resolution_summary["unresolved_row_count"],
        "canonical_exact_match_count": resolution_summary["canonical_exact_match_count"],
        "alias_exact_match_count": resolution_summary["alias_exact_match_count"],
        "display_rows": after_display_summary["rows"],
        "output_file": after_display_summary["output_file"],
    }


def _rebuild_preview_and_resolve(
    *,
    ranking_preview_input_file: str,
    admission_preview_input_file: str,
    ranking_landing_schema: str,
    ranking_landing_table: str,
    admission_landing_schema: str,
    admission_landing_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    refresh_limit: int,
    refresh_output_file: str,
) -> dict[str, Any]:
    try:
        ranking_summary = _write_ranking_warehouse_preview(
            input_source="preview-json",
            preview_input_file=ranking_preview_input_file,
            staging_input_file="",
            staging_table="",
            landing_schema=ranking_landing_schema,
            landing_table=ranking_landing_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
    except Exception as exc:
        raise RuntimeError(f"Step 1 failed: write-ranking-warehouse-preview: {exc}") from exc

    try:
        admission_summary = _write_admission_warehouse_preview(
            input_source="preview-json",
            preview_input_file=admission_preview_input_file,
            staging_input_file="",
            staging_table="",
            landing_schema=admission_landing_schema,
            landing_table=admission_landing_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
    except Exception as exc:
        raise RuntimeError(f"Step 2 failed: write-admission-warehouse-preview: {exc}") from exc

    try:
        ranking_resolution_summary = _resolve_ranking_entities(
            target_schema=ranking_landing_schema,
            target_table=ranking_landing_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
    except Exception as exc:
        raise RuntimeError(f"Step 3 failed: resolve-ranking-entities: {exc}") from exc

    try:
        admission_resolution_summary = _refresh_admission_resolution(
            target_schema=admission_landing_schema,
            target_table=admission_landing_table,
            limit=refresh_limit,
            output_file=refresh_output_file,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
    except Exception as exc:
        raise RuntimeError(f"Step 4 failed: refresh-admission-resolution: {exc}") from exc

    return {
        "ranking_preview_summary": ranking_summary,
        "admission_preview_summary": admission_summary,
        "ranking_resolution_summary": ranking_resolution_summary,
        "admission_resolution_summary": admission_resolution_summary,
        "success": True,
    }


def _preview_ranking_admission_convergence(
    *,
    ranking_schema: str,
    ranking_table: str,
    admission_schema: str,
    admission_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest.pipeline.convergence_preview import (  # noqa: E402
        build_convergence_preview,
        build_terminal_summary,
        convergence_rows_to_dicts,
        write_convergence_preview,
    )

    rows = build_convergence_preview(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        ranking_schema=ranking_schema,
        ranking_table=ranking_table,
        admission_schema=admission_schema,
        admission_table=admission_table,
        limit=limit,
    )
    if output_file:
        write_convergence_preview(rows, Path(output_file))

    terminal_summary = build_terminal_summary(rows)
    return {
        "ranking_table": f"{ranking_schema}.{ranking_table}",
        "admission_table": f"{admission_schema}.{admission_table}",
        "row_count": terminal_summary["row_count"],
        "both_count": terminal_summary["both_count"],
        "ranking_only_count": terminal_summary["ranking_only_count"],
        "admission_only_count": terminal_summary["admission_only_count"],
        "rows": convergence_rows_to_dicts(rows),
        "preview_rows": convergence_rows_to_dicts(rows[: min(5, len(rows))]),
        "output_file": output_file,
    }


def _preview_canonical_university_detail(
    *,
    canonical_university_id: int | None,
    university_name: str,
    output_file: str,
    ranking_schema: str,
    ranking_table: str,
    admission_schema: str,
    admission_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest.pipeline.canonical_university_detail_preview import (  # noqa: E402
        build_canonical_university_detail_preview,
        detail_preview_to_dict,
        write_detail_preview,
    )

    preview = build_canonical_university_detail_preview(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        canonical_university_id=canonical_university_id,
        university_name=university_name,
        ranking_schema=ranking_schema,
        ranking_table=ranking_table,
        admission_schema=admission_schema,
        admission_table=admission_table,
    )
    if output_file:
        write_detail_preview(preview, Path(output_file))

    payload = detail_preview_to_dict(preview)
    payload["output_file"] = output_file
    return payload


def _aggregate_ranking_preview(
    *,
    input_source: str,
    preview_input_file: str,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.aggregation_writer import (  # noqa: E402
        aggregation_write_summary_to_dict,
        write_aggregated_rows,
    )
    from crawlernest_ranking_crawler.aggregator import (  # noqa: E402
        aggregate_rankings,
        aggregated_rows_to_jsonable,
    )
    from crawlernest_ranking_crawler.postgres_driver import get_psycopg2  # noqa: E402
    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_ranking_crawler.warehouse_writer import load_warehouse_preview_rows  # noqa: E402

    if input_source == "preview-json":
        source_rows = load_warehouse_preview_rows(Path(preview_input_file))
        source_location = str(Path(preview_input_file))
    elif input_source == "postgres":
        staging_rows = load_staging_rows_from_postgres(
            table_name=f"{source_schema}.{source_table}",
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        source_rows = map_staging_rows_to_warehouse_rows(staging_rows)
        source_location = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{source_schema}.{source_table}"
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    aggregated_rows = aggregate_rankings(source_rows)
    output_path = Path(output_file)
    save_json_artifact(output_path, aggregated_rows_to_jsonable(aggregated_rows))

    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        summary = write_aggregated_rows(
            aggregated_rows,
            conn,
            schema_name=target_schema,
            table_name=target_table,
        )
    finally:
        conn.close()

    payload = aggregation_write_summary_to_dict(summary)
    payload["input_source"] = input_source
    payload["source_location"] = source_location
    payload["output_file"] = str(output_path)
    payload["preview_rows"] = aggregated_rows_to_jsonable(aggregated_rows[:5])
    return payload


def _decision_ranking_preview(
    *,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from dataclasses import asdict  # noqa: E402

    from crawlernest_ranking_crawler.decision_writer import (  # noqa: E402
        build_decision_row,
        decision_write_summary_to_dict,
        load_aggregated_rows_from_postgres,
        write_decision_rows,
    )
    from crawlernest_ranking_crawler.explain_layer import build_explain  # noqa: E402
    from crawlernest_ranking_crawler.postgres_driver import get_psycopg2  # noqa: E402

    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        aggregated_rows = load_aggregated_rows_from_postgres(conn)
        decision_rows = [build_decision_row(row, build_explain(row)) for row in aggregated_rows]
        output_path = Path(output_file)
        save_json_artifact(output_path, [asdict(row) for row in decision_rows])
        summary = write_decision_rows(
            decision_rows,
            conn,
            schema_name=target_schema,
            table_name=target_table,
        )
    finally:
        conn.close()

    payload = decision_write_summary_to_dict(summary)
    payload["source_location"] = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{source_schema}.{source_table}"
    payload["output_file"] = str(Path(output_file))
    payload["preview_rows"] = [asdict(row) for row in decision_rows[:5]]
    return payload


def _resolve_ranking_entities(
    *,
    target_schema: str,
    target_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.entity_resolver import (  # noqa: E402
        entity_resolution_summary_to_dict,
        resolve_ranking_preview_entities,
    )

    summary = resolve_ranking_preview_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
    )
    return entity_resolution_summary_to_dict(summary)


def _get_unresolved_ranking_entities(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.unresolved_report import (  # noqa: E402
        get_unresolved_universities,
        unresolved_rows_to_dicts,
        write_unresolved_report,
    )

    rows = get_unresolved_universities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
    )
    if output_file:
        write_unresolved_report(rows, Path(output_file))

    return {
        "target_table": f"{target_schema}.{target_table}",
        "row_count": len(rows),
        "rows": unresolved_rows_to_dicts(rows),
        "output_file": output_file,
    }


def _refresh_ranking_resolution(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    full_summary_limit = 1_000_000

    before_summary = _get_unresolved_ranking_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    resolution_summary = _resolve_ranking_entities(
        target_schema=target_schema,
        target_table=target_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    after_full_summary = _get_unresolved_ranking_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    after_display_summary = _get_unresolved_ranking_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
        output_file=output_file,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    before_unresolved_count = sum(int(row["occurrence_count"]) for row in before_summary["rows"])
    after_unresolved_count = sum(int(row["occurrence_count"]) for row in after_full_summary["rows"])

    return {
        "target_table": before_summary["target_table"],
        "before_unresolved_count": before_unresolved_count,
        "before_distinct_university_count": before_summary["row_count"],
        "after_unresolved_count": after_unresolved_count,
        "after_distinct_university_count": after_full_summary["row_count"],
        "resolved_row_count": resolution_summary["resolved_row_count"],
        "unresolved_row_count": resolution_summary["unresolved_row_count"],
        "display_rows": after_display_summary["rows"],
        "output_file": after_display_summary["output_file"],
    }


def _seed_university_alias(
    *,
    canonical: str,
    alias: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.alias_seed import (  # noqa: E402
        add_university_alias,
        alias_seed_summary_to_dict,
    )

    summary = add_university_alias(
        canonical_name=canonical,
        alias=alias,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return alias_seed_summary_to_dict(summary)




def _dispatch_remaining_commands(args: argparse.Namespace) -> int:
    if args.command == "crawl-ranking":
        output_path, count, normalized_path, staging_path = _run_sample_crawl_export(
            args.command,
            args.output_file,
            normalized_output_file=(
                args.normalized_output_file if getattr(args, "with_normalized_output", False) else None
            ),
            staging_output_file=(
                args.staging_output_file if getattr(args, "write_staging", False) else None
            ),
        )
        print(f"[crawl-ranking] exported={count} output={output_path}")
        if normalized_path is not None:
            print(f"[crawl-ranking] normalized_output={normalized_path}")
        if staging_path is not None:
            print(f"[crawl-ranking] staging_output={staging_path}")
        return 0

    if args.command == "crawl-admission":
        output_path, count, normalized_path, staging_path = _run_sample_crawl_export(
            args.command,
            args.output_file,
            normalized_output_file=(
                args.normalized_output_file if getattr(args, "with_normalized_output", False) else None
            ),
            staging_output_file=(
                args.staging_output_file if getattr(args, "write_staging", False) else None
            ),
        )
        print(f"[crawl-admission] exported={count} output={output_path}")
        if normalized_path is not None:
            print(f"[crawl-admission] normalized_output={normalized_path}")
        if staging_path is not None:
            print(f"[crawl-admission] staging_output={staging_path}")
        return 0

    if args.command == "validate-admission-staging":
        summary = _validate_admission_staging(args.staging_input_file)
        print(
            "[validate-admission-staging] "
            f"total={summary['total_rows']} "
            f"valid={summary['valid_row_count']} "
            f"invalid={summary['invalid_row_count']} "
            f"duplicates={summary['duplicate_row_count']}"
        )
        print(f"[validate-admission-staging] staging_file={summary['staging_file']}")
        if summary["error_samples"]:
            print("[validate-admission-staging] error_samples:")
            print(json.dumps(summary["error_samples"], ensure_ascii=False, indent=2))
        if summary["duplicate_samples"]:
            print("[validate-admission-staging] duplicate_samples:")
            print(json.dumps(summary["duplicate_samples"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "ingest-admission-staging":
        try:
            summary = _ingest_admission_staging(
                args.staging_input_file,
                args.sqlite_db_file,
                allow_partial=bool(getattr(args, "allow_partial_ingest", False)),
                write_target=str(getattr(args, "write_target", "sqlite")),
                staging_table=str(getattr(args, "staging_table", "admission_staging_records")),
                pg_host=str(getattr(args, "pg_host", "localhost")),
                pg_port=int(getattr(args, "pg_port", 5432)),
                pg_database=str(getattr(args, "pg_database", "clawer")),
                pg_user=str(getattr(args, "pg_user", "test")),
                pg_password=str(getattr(args, "pg_password", "")),
            )
        except (ValueError, RuntimeError) as exc:
            print(f"[ingest-admission-staging] aborted: {exc}")
            validation_summary = _validate_admission_staging(args.staging_input_file)
            print(
                "[ingest-admission-staging] "
                f"total={validation_summary['total_rows']} "
                f"valid={validation_summary['valid_row_count']} "
                f"invalid={validation_summary['invalid_row_count']} "
                f"duplicates={validation_summary['duplicate_row_count']}"
            )
            return 1

        print(
            "[ingest-admission-staging] "
            f"write_target={summary['write_target']} "
            f"mode={summary['mode']} "
            f"inserted={summary['inserted_row_count']} "
            f"skipped_existing={summary['skipped_existing_row_count']} "
            f"valid={summary['valid_row_count']} "
            f"invalid={summary['invalid_row_count']} "
            f"duplicates={summary['duplicate_row_count']}"
        )
        print(f"[ingest-admission-staging] target_location={summary['target_location']}")
        print(f"[ingest-admission-staging] table={summary['table_name']}")
        return 0

    if args.command == "preview-admission-warehouse-map":
        summary = _preview_admission_warehouse_map(
            input_source=str(args.input_source),
            staging_input_file=str(args.staging_input_file),
            staging_table=str(args.staging_table),
            output_file=str(args.output_file),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
        print(
            "[preview-admission-warehouse-map] "
            f"input_source={summary['input_source']} "
            f"rows={summary['row_count']} "
            f"output={summary['output_file']}"
        )
        if summary["preview_rows"]:
            print("[preview-admission-warehouse-map] preview_rows:")
            print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "write-admission-warehouse-preview":
        try:
            summary = _write_admission_warehouse_preview(
                input_source=str(args.input_source),
                preview_input_file=str(args.preview_input_file),
                staging_input_file=str(args.staging_input_file),
                staging_table=str(args.staging_table),
                landing_schema=str(args.landing_schema),
                landing_table=str(args.landing_table),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[write-admission-warehouse-preview] aborted: {exc}")
            return 1

        print(
            "[write-admission-warehouse-preview] "
            f"rows={summary['row_count']} "
            f"inserted={summary['inserted_row_count']} "
            f"skipped_existing={summary['skipped_existing_row_count']}"
        )
        print(f"[write-admission-warehouse-preview] target={summary['target_location']}")
        print(f"[write-admission-warehouse-preview] table={summary['table_name']}")
        return 0

    if args.command == "resolve-admission-entities":
        try:
            summary = _resolve_admission_entities(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[resolve-admission-entities] aborted: {exc}")
            return 1

        print(
            "[resolve-admission-entities] "
            f"total={summary['total_rows']} "
            f"resolved={summary['resolved_row_count']} "
            f"unresolved={summary['unresolved_row_count']} "
            f"canonical_exact={summary['canonical_exact_match_count']} "
            f"alias_exact={summary['alias_exact_match_count']}"
        )
        print(f"[resolve-admission-entities] target={summary['target_table']}")
        return 0

    if args.command == "unresolved-admission-entities":
        try:
            summary = _get_unresolved_admission_entities(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                limit=int(args.limit),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[unresolved-admission-entities] aborted: {exc}")
            return 1

        print(
            "[unresolved-admission-entities] "
            f"target={summary['target_table']} "
            f"rows={summary['row_count']}"
        )
        if summary["rows"]:
            print("normalized_university_name | occurrence_count")
            for row in summary["rows"]:
                print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
        else:
            print("No unresolved admission entities found.")
        if summary["output_file"]:
            print(f"[unresolved-admission-entities] output={summary['output_file']}")
        return 0

    if args.command == "refresh-admission-resolution":
        try:
            summary = _refresh_admission_resolution(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                limit=int(args.limit),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[refresh-admission-resolution] aborted: {exc}")
            return 1

        print(
            "[refresh-admission-resolution] "
            f"target={summary['target_table']} "
            f"before_unresolved={summary['before_unresolved_count']} "
            f"after_unresolved={summary['after_unresolved_count']} "
            f"before_distinct={summary['before_distinct_university_count']} "
            f"after_distinct={summary['after_distinct_university_count']} "
            f"resolved={summary['resolved_row_count']} "
            f"unresolved={summary['unresolved_row_count']} "
            f"canonical_exact={summary['canonical_exact_match_count']} "
            f"alias_exact={summary['alias_exact_match_count']}"
        )
        if summary["display_rows"]:
            print("normalized_university_name | occurrence_count")
            for row in summary["display_rows"]:
                print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
        else:
            print("No unresolved admission entities found.")
        if summary["output_file"]:
            print(f"[refresh-admission-resolution] output={summary['output_file']}")
        return 0

    if args.command == "rebuild-preview-and-resolve":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        try:
            summary = _rebuild_preview_and_resolve(
                ranking_preview_input_file=str(args.ranking_preview_input_file),
                admission_preview_input_file=str(args.admission_preview_input_file),
                ranking_landing_schema=str(args.ranking_landing_schema),
                ranking_landing_table=str(args.ranking_landing_table),
                admission_landing_schema=str(args.admission_landing_schema),
                admission_landing_table=str(args.admission_landing_table),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
                refresh_limit=int(args.limit),
                refresh_output_file=str(args.output_file),
            )
        except RuntimeError as exc:
            print(f"[rebuild-preview-and-resolve] aborted: {exc}")
            return 1

        ranking_summary = summary["ranking_preview_summary"]
        admission_summary = summary["admission_preview_summary"]
        ranking_resolution_summary = summary["ranking_resolution_summary"]
        admission_resolution_summary = summary["admission_resolution_summary"]

        print(
            "[rebuild-preview-and-resolve] ranking_preview "
            f"rows={ranking_summary['row_count']} "
            f"inserted={ranking_summary['inserted_row_count']} "
            f"skipped_existing={ranking_summary['skipped_existing_row_count']}"
        )
        print(
            "[rebuild-preview-and-resolve] admission_preview "
            f"rows={admission_summary['row_count']} "
            f"inserted={admission_summary['inserted_row_count']} "
            f"skipped_existing={admission_summary['skipped_existing_row_count']}"
        )
        print(
            "[rebuild-preview-and-resolve] ranking_resolution "
            f"total={ranking_resolution_summary['total_rows']} "
            f"resolved={ranking_resolution_summary['resolved_row_count']} "
            f"unresolved={ranking_resolution_summary['unresolved_row_count']}"
        )
        print(
            "[rebuild-preview-and-resolve] admission_resolution "
            f"resolved={admission_resolution_summary['resolved_row_count']} "
            f"unresolved={admission_resolution_summary['unresolved_row_count']} "
            f"before_distinct={admission_resolution_summary['before_distinct_university_count']} "
            f"after_distinct={admission_resolution_summary['after_distinct_university_count']}"
        )
        print("[rebuild-preview-and-resolve] overall_status=success")
        return 0

    if args.command == "preview-ranking-admission-convergence":
        try:
            summary = _preview_ranking_admission_convergence(
                ranking_schema=str(args.ranking_schema),
                ranking_table=str(args.ranking_table),
                admission_schema=str(args.admission_schema),
                admission_table=str(args.admission_table),
                limit=int(args.limit),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[preview-ranking-admission-convergence] aborted: {exc}")
            return 1

        print(
            "[preview-ranking-admission-convergence] "
            f"rows={summary['row_count']} "
            f"both={summary['both_count']} "
            f"ranking_only={summary['ranking_only_count']} "
            f"admission_only={summary['admission_only_count']}"
        )
        print(f"[preview-ranking-admission-convergence] ranking_table={summary['ranking_table']}")
        print(f"[preview-ranking-admission-convergence] admission_table={summary['admission_table']}")
        if summary["preview_rows"]:
            print("[preview-ranking-admission-convergence] preview_rows:")
            print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
        else:
            print("No converged ranking/admission preview rows found.")
        if summary["output_file"]:
            print(f"[preview-ranking-admission-convergence] output={summary['output_file']}")
        return 0

    if args.command == "preview-canonical-university-detail":
        try:
            summary = _preview_canonical_university_detail(
                canonical_university_id=(
                    None if getattr(args, "canonical_university_id", None) is None
                    else int(args.canonical_university_id)
                ),
                university_name=str(getattr(args, "university_name", "") or ""),
                output_file=str(getattr(args, "output_file", "") or ""),
                ranking_schema=str(getattr(args, "ranking_schema", "warehouse")),
                ranking_table=str(getattr(args, "ranking_table", "ranking_records_preview")),
                admission_schema=str(getattr(args, "admission_schema", "warehouse")),
                admission_table=str(getattr(args, "admission_table", "admission_records_preview")),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except (RuntimeError, ValueError) as exc:
            print(f"[preview-canonical-university-detail] aborted: {exc}")
            return 1

        print(
            "[preview-canonical-university-detail] "
            f"canonical_university_id={summary['canonical_university_id']} "
            f"has_ranking_data={summary['data_availability']['has_ranking_data']} "
            f"has_admission_data={summary['data_availability']['has_admission_data']}"
        )
        print("[preview-canonical-university-detail] preview:")
        print(json.dumps({k: v for k, v in summary.items() if k != "output_file"}, ensure_ascii=False, indent=2))
        if summary["output_file"]:
            print(f"[preview-canonical-university-detail] output={summary['output_file']}")
        return 0

    if args.command == "validate-ranking-staging":
        summary = _validate_ranking_staging(args.staging_input_file)
        print(
            "[validate-ranking-staging] "
            f"total={summary['total_rows']} "
            f"valid={summary['valid_row_count']} "
            f"invalid={summary['invalid_row_count']} "
            f"duplicates={summary['duplicate_row_count']}"
        )
        print(f"[validate-ranking-staging] staging_file={summary['staging_file']}")
        if summary["error_samples"]:
            print("[validate-ranking-staging] error_samples:")
            print(json.dumps(summary["error_samples"], ensure_ascii=False, indent=2))
        if summary["duplicate_samples"]:
            print("[validate-ranking-staging] duplicate_samples:")
            print(json.dumps(summary["duplicate_samples"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "ingest-ranking-staging":
        try:
            summary = _ingest_ranking_staging(
                args.staging_input_file,
                args.sqlite_db_file,
                allow_partial=bool(getattr(args, "allow_partial_ingest", False)),
                write_target=str(getattr(args, "write_target", "sqlite")),
                pg_host=str(getattr(args, "pg_host", "localhost")),
                pg_port=int(getattr(args, "pg_port", 5432)),
                pg_database=str(getattr(args, "pg_database", "clawer")),
                pg_user=str(getattr(args, "pg_user", "test")),
                pg_password=str(getattr(args, "pg_password", "")),
            )
        except (ValueError, RuntimeError) as exc:
            print(f"[ingest-ranking-staging] aborted: {exc}")
            validation_summary = _validate_ranking_staging(args.staging_input_file)
            print(
                "[ingest-ranking-staging] "
                f"total={validation_summary['total_rows']} "
                f"valid={validation_summary['valid_row_count']} "
                f"invalid={validation_summary['invalid_row_count']} "
                f"duplicates={validation_summary['duplicate_row_count']}"
            )
            return 1

        print(
            "[ingest-ranking-staging] "
            f"write_target={summary['write_target']} "
            f"mode={summary['mode']} "
            f"inserted={summary['inserted_row_count']} "
            f"skipped_existing={summary['skipped_existing_row_count']} "
            f"valid={summary['valid_row_count']} "
            f"invalid={summary['invalid_row_count']} "
            f"duplicates={summary['duplicate_row_count']}"
        )
        print(f"[ingest-ranking-staging] target_location={summary['target_location']}")
        print(f"[ingest-ranking-staging] table={summary['table_name']}")
        return 0

    if args.command == "preview-ranking-warehouse-map":
        summary = _preview_ranking_warehouse_map(
            input_source=str(args.input_source),
            staging_input_file=str(args.staging_input_file),
            staging_table=str(args.staging_table),
            output_file=str(args.output_file),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
        print(
            "[preview-ranking-warehouse-map] "
            f"input_source={summary['input_source']} "
            f"rows={summary['row_count']} "
            f"output={summary['output_file']}"
        )
        if summary["preview_rows"]:
            print("[preview-ranking-warehouse-map] preview_rows:")
            print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "write-ranking-warehouse-preview":
        try:
            summary = _write_ranking_warehouse_preview(
                input_source=str(args.input_source),
                preview_input_file=str(args.preview_input_file),
                staging_input_file=str(args.staging_input_file),
                staging_table=str(args.staging_table),
                landing_schema=str(args.landing_schema),
                landing_table=str(args.landing_table),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[write-ranking-warehouse-preview] aborted: {exc}")
            return 1

        print(
            "[write-ranking-warehouse-preview] "
            f"rows={summary['row_count']} "
            f"inserted={summary['inserted_row_count']} "
            f"skipped_existing={summary['skipped_existing_row_count']}"
        )
        print(f"[write-ranking-warehouse-preview] target={summary['target_location']}")
        print(f"[write-ranking-warehouse-preview] table={summary['table_name']}")
        return 0

    if args.command == "aggregate-ranking-preview":
        try:
            summary = _aggregate_ranking_preview(
                input_source=str(args.input_source),
                preview_input_file=str(args.preview_input_file),
                source_schema=str(args.source_schema),
                source_table=str(args.source_table),
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[aggregate-ranking-preview] aborted: {exc}")
            return 1

        print(
            "[aggregate-ranking-preview] "
            f"input_source={summary['input_source']} "
            f"rows={summary['row_count']} "
            f"written={summary['written_row_count']}"
        )
        print(f"[aggregate-ranking-preview] source={summary['source_location']}")
        print(f"[aggregate-ranking-preview] output={summary['output_file']}")
        print(f"[aggregate-ranking-preview] target={summary['target_location']}")
        print(f"[aggregate-ranking-preview] table={summary['table_name']}")
        if summary["preview_rows"]:
            print("[aggregate-ranking-preview] preview_rows:")
            print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
        return 0

    if args.command == "decision-ranking-preview":
        try:
            summary = _decision_ranking_preview(
                source_schema=str(args.source_schema),
                source_table=str(args.source_table),
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[decision-ranking-preview] aborted: {exc}")
            return 1

        print(
            f"[decision-ranking-preview] rows={summary['row_count']} "
            f"inserted={summary['inserted_row_count']}"
        )
        return 0

    if args.command == "resolve-ranking-entities":
        try:
            summary = _resolve_ranking_entities(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[resolve-ranking-entities] aborted: {exc}")
            return 1

        print(
            "[resolve-ranking-entities] "
            f"total={summary['total_rows']} "
            f"resolved={summary['resolved_row_count']} "
            f"unresolved={summary['unresolved_row_count']}"
        )
        print(f"[resolve-ranking-entities] target={summary['target_table']}")
        return 0

    if args.command == "unresolved-ranking-entities":
        try:
            summary = _get_unresolved_ranking_entities(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                limit=int(args.limit),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[unresolved-ranking-entities] aborted: {exc}")
            return 1

        print(
            "[unresolved-ranking-entities] "
            f"target={summary['target_table']} "
            f"rows={summary['row_count']}"
        )
        if summary["rows"]:
            print("normalized_university_name | occurrence_count")
            for row in summary["rows"]:
                print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
        else:
            print("No unresolved ranking entities found.")
        if summary["output_file"]:
            print(f"[unresolved-ranking-entities] output={summary['output_file']}")
        return 0

    if args.command == "refresh-ranking-resolution":
        try:
            summary = _refresh_ranking_resolution(
                target_schema=str(args.target_schema),
                target_table=str(args.target_table),
                limit=int(args.limit),
                output_file=str(args.output_file),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except RuntimeError as exc:
            print(f"[refresh-ranking-resolution] aborted: {exc}")
            return 1

        print(
            "[refresh-ranking-resolution] "
            f"target={summary['target_table']} "
            f"before_unresolved={summary['before_unresolved_count']} "
            f"after_unresolved={summary['after_unresolved_count']} "
            f"before_distinct={summary['before_distinct_university_count']} "
            f"after_distinct={summary['after_distinct_university_count']} "
            f"resolved={summary['resolved_row_count']} "
            f"unresolved={summary['unresolved_row_count']}"
        )
        if summary["display_rows"]:
            print("normalized_university_name | occurrence_count")
            for row in summary["display_rows"]:
                print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
        else:
            print("No unresolved ranking entities found.")
        if summary["output_file"]:
            print(f"[refresh-ranking-resolution] output={summary['output_file']}")
        return 0

    if args.command == "seed-university-alias":
        try:
            summary = _seed_university_alias(
                canonical=str(args.canonical),
                alias=str(args.alias),
                pg_host=str(args.pg_host),
                pg_port=int(args.pg_port),
                pg_database=str(args.pg_database),
                pg_user=str(args.pg_user),
                pg_password=str(args.pg_password),
            )
        except (RuntimeError, ValueError) as exc:
            print(f"[seed-university-alias] aborted: {exc}")
            return 1

        print(
            "[seed-university-alias] "
            f"canonical_id={summary['canonical_university_id']} "
            f"created_canonical={'yes' if summary['created_canonical'] else 'no'} "
            f"created_alias={'yes' if summary['created_alias'] else 'no'}"
        )
        print(
            f"[seed-university-alias] canonical={summary['canonical_name']} "
            f"normalized_canonical={summary['normalized_canonical_name']}"
        )
        print(
            f"[seed-university-alias] alias={summary['alias']} "
            f"normalized_alias={summary['normalized_alias']}"
        )
        return 0

    if args.command == "seed-canonical":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = seed_canonical_universities(
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(
            f"[seed-canonical] seeded={summary['seeded']} "
            f"skipped={summary['skipped']} failed={summary['failed']}"
        )
        print(
            f"[seed-canonical] years_aggregated={summary['years_aggregated']} "
            f"aggregated_rows={summary['aggregated_rows']}"
        )
        return 0

    if args.command == "seed-canonical-from-missing":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = seed_canonical_from_missing_entities(
            source_code=str(args.source or "THE").strip().upper(),
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(
            f"[seed-canonical-from-missing] seeded={summary['seeded']} "
            f"skipped={summary['skipped']} failed={summary['failed']}"
        )
        if summary["source_code"] == "THE":
            print("[seed-canonical-from-missing] re-ingesting THE rankings...")
            the_summary = run_the_rankings_ingestion(
                ranking_year=args.ranking_year,
                output_dir=MODULE_ROOT / "crawlernest-kb" / "databases",
                pg_host=args.pg_host,
                pg_port=args.pg_port,
                pg_database=args.pg_database,
                pg_user=args.pg_user,
                pg_password=args.pg_password,
                skip_seed=True,
            )
            print(
                f"[seed-canonical-from-missing] matched={the_summary['matched_count']} "
                f"unresolved={the_summary['unresolved_count']} "
                f"aggregated_rows={the_summary['aggregated_rows']}"
            )
        return 0

    if args.command == "backfill-ranking-records":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = backfill_qs_ranking_records_from_legacy(
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(
            f"[backfill-ranking-records] run_id={summary['run_id']} "
            f"backfilled={summary['backfilled']} skipped={summary['skipped']} failed={summary['failed']}"
        )
        print(
            f"[backfill-ranking-records] years_aggregated={summary['years_aggregated']} "
            f"aggregated_rows={summary['aggregated_rows']}"
        )
        return 0

    if args.command == "rebuild-universe-records":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = rebuild_universe_records_diagnostic(
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(
            f"[rebuild] legacy global candidate rows for {summary['ranking_year']}: "
            f"{summary['legacy_global_count']}"
        )
        if summary["missing_universes"]:
            print("[rebuild] universes requiring re-crawl:")
            for label in summary["missing_universes"]:
                print(f"- {label}")
        else:
            print("[rebuild] all configured QS universes have ranking_record rows.")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-the-rankings":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = run_the_rankings_ingestion(
            ranking_year=args.ranking_year,
            output_dir=Path(args.output_dir),
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            skip_seed=bool(args.skip_seed),
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-arwu-rankings":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = run_arwu_rankings_ingestion(
            ranking_year=args.ranking_year,
            output_dir=Path(args.output_dir),
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            skip_seed=bool(args.skip_seed),
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate-global-multi-source":
        ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        summary = validate_global_multi_source(
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            ranking_year=args.ranking_year,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    return dispatch_command(args, _build_dispatch_dependencies())


def main() -> int:
    args = build_parser().parse_args()
    return dispatch_basic_commands(
        args,
        run_handler=_handle_run_command,
        query_handler=_handle_query_command,
        enrich_handler=_handle_enrich_details_command,
        fallback_handler=_dispatch_remaining_commands,
    )


if __name__ == "__main__":
    start_time = time.time()
    try:
        sys.exit(main())
    finally:
        elapsed = time.time() - start_time
        print(f"\n--- Execution Finished in {elapsed:.2f} seconds ---")
