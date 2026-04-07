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

    print("[4/4] Done.")
    print(f"Inserted: {inserted}, Skipped(resume): {skipped}, Failed: {failed}")
    print(f"Checkpoint: {checkpoint_file}")

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

    return WriteStageResult(
        normalized=normalized,
        inserted=inserted,
        skipped=skipped,
        failed=failed,
        multi_source_summary=summary,
    )
