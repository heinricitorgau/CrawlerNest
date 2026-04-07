from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class CrawlStageResult:
    universities: list[Any]
    crawl_meta: dict[str, Any]
    deferred_count: int


def execute_run_crawl_stage(
    args: Any,
    *,
    ensure_postgres_schema: Callable[..., None],
    load_snapshot: Callable[[Path], list[Any]],
    run_qs_crawl: Callable[..., tuple[list[Any], dict[str, Any]]],
    save_snapshot: Callable[[Path, list[Any]], None],
    save_deferred_detail_list: Callable[[Path, list[Any], list[str]], int],
    print_qs_entry_strategy: Callable[[dict[str, Any]], None],
) -> CrawlStageResult:
    if args.limit <= 0:
        raise SystemExit("--limit must be a positive integer")

    ensure_postgres_schema(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)
    snapshot_file = Path(args.snapshot_file)

    if args.resume and snapshot_file.exists():
        print("[1/4] Loading snapshot (resume mode)...")
        universities = load_snapshot(snapshot_file)
        return CrawlStageResult(universities=universities, crawl_meta={}, deferred_count=0)

    print("[1/4] Crawling QS data...")
    universities, crawl_meta = run_qs_crawl(
        args.limit,
        args.ranking_year,
        args.ranking_id,
        args.use_async,
        args.workers,
        args.request_delay,
        args.local_parse_workers,
        not args.rankings_only,
        args.detail_403_streak_threshold,
        args.detail_chunk_size,
    )
    print_qs_entry_strategy(crawl_meta)
    if not universities:
        failure_classification = str(crawl_meta.get("failure_classification", "") or "").strip()
        failure_message = str(crawl_meta.get("failure_message", "") or "").strip()
        if failure_classification:
            print(
                f"[error] QS acquisition failed with classification={failure_classification}: "
                f"{failure_message or 'no additional detail'}"
            )
            resolved_page = str(crawl_meta.get("resolved_ranking_page_url", "") or "").strip()
            resolved_id = str(crawl_meta.get("resolved_ranking_id", "") or "").strip()
            if resolved_page:
                print(f"[error] ranking_page_url={resolved_page}")
            if resolved_id:
                print(f"[error] resolved_ranking_id={resolved_id}")
        print("No universities crawled. Exiting.")
        raise SystemExit(1)

    save_snapshot(snapshot_file, universities)
    deferred_count = save_deferred_detail_list(
        Path(args.deferred_details_file),
        universities,
        crawl_meta.get("detail_deferred_paths", []),
    )
    return CrawlStageResult(
        universities=universities,
        crawl_meta=crawl_meta,
        deferred_count=deferred_count,
    )
