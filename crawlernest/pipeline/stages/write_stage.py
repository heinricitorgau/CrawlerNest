from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class WriteStageResult:
    normalized: list[Any]
    inserted: int
    skipped: int
    failed: int
    multi_source_summary: Any | None


def execute_run_write_stage(
    args: Any,
    *,
    universities: list[Any],
    normalize_universities: Callable[[list[Any]], list[Any]],
    write_universities: Callable[..., tuple[int, int, int]],
    sync_qs_multi_source_rankings: Callable[..., Any],
    sync_legacy_rankings_to_analytics: Callable[..., Any] | None = None,
    count_analytics_latest_view: Callable[..., int] | None = None,
) -> WriteStageResult:
    checkpoint_file = Path(args.checkpoint_file)

    print("[2/4] Normalizing fields (Python baseline)...")
    normalized = normalize_universities(universities)

    print(f"[3/4] Writing {len(normalized)} rows to {args.db_type}...")
    inserted, skipped, failed = write_universities(
        universities=normalized,
        db_type=args.db_type,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
        checkpoint_file=checkpoint_file,
        resource_guard=args.resource_guard,
        workers=max(1, args.workers),
        ranking_year=args.ranking_year,
        write_batch_size=max(1, args.write_batch_size),
    )

    print(f"Inserted: {inserted}, Skipped(resume): {skipped}, Failed: {failed}")
    print(f"Checkpoint: {checkpoint_file}")

    if sync_legacy_rankings_to_analytics is not None:
        print("[4/4] Syncing legacy rankings into analytics-native tables...")
        analytics_summary = sync_legacy_rankings_to_analytics(
            ranking_year=args.ranking_year,
            source_code="QS",
            universe_type="global",
            universe_key="global",
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(f"[analytics] seeded ranking_source: {analytics_summary.ranking_source_count}")
        print(f"[analytics] seeded canonical_university: {analytics_summary.canonical_university_count}")
        print(f"[analytics] seeded canonical_university_link: {analytics_summary.canonical_university_link_count}")
        print(f"[analytics] synced ranking_record: {analytics_summary.ranking_record_count}")
        print(f"[analytics] created aggregation_run: {analytics_summary.aggregation_run_id}")
        print(f"[analytics] aggregated_rankings count: {analytics_summary.aggregated_rankings_count}")
        print(f"[analytics] latest view count: {analytics_summary.latest_view_count}")
        if analytics_summary.latest_view_count <= 0:
            raise RuntimeError(
                "Analytics sync completed but analytics.v_aggregated_rankings_latest has 0 rows "
                f"for year={args.ranking_year}, source=QS, universe=global/global. "
                "The product rankings API will return empty results."
            )

    summary = None
    try:
        summary = sync_qs_multi_source_rankings(
            normalized,
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            batch_id=f"qs-run-{args.ranking_year}",
        )
        print(
            "[multi-source] "
            f"rows={summary.standardized_count} matched={summary.matched_count} "
            f"unresolved={summary.unresolved_count} duplicates={summary.duplicate_input_count} "
            f"aggregated_years={summary.years_aggregated}"
        )
    except Exception as exc:
        print(f"[warn] QS multi-source sync skipped: {exc}")

    if count_analytics_latest_view is not None:
        latest_view_count = count_analytics_latest_view(
            ranking_year=args.ranking_year,
            universe_type="global",
            universe_key="global",
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(f"[analytics] final latest view count: {latest_view_count}")
        if latest_view_count <= 0:
            raise RuntimeError(
                "Pipeline ended with analytics.v_aggregated_rankings_latest count=0 "
                f"for year={args.ranking_year}, universe=global/global. "
                "Do not treat this run as complete because /api/v1/rankings will be empty."
            )

    print("[4/4] Done.")

    return WriteStageResult(
        normalized=normalized,
        inserted=inserted,
        skipped=skipped,
        failed=failed,
        multi_source_summary=summary,
    )
