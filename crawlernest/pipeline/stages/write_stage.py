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
    sync_qs_from_legacy: Callable[..., Any],
    seed_legacy_entities: Callable[..., Any] | None = None,
    aggregate_legacy_analytics: Callable[..., Any] | None = None,
    count_analytics_latest_view: Callable[..., int] | None = None,
) -> WriteStageResult:
    """
    Crawl output lands in the legacy tables, then flows through one writer.

    The order below is the point of this stage. warehouse.ranking_record used
    to be written twice per run -- once by the analytics bridge joining
    canonical_slug = school_slug, once by the multi-source pipeline resolving
    the crawled payload -- each with its own run_id convention, the second
    pruning what the first wrote. Now:

        write_universities        legacy tables: the crawl's landing zone
        seed_legacy_entities      canonical_university, which the resolver reads
        sync_qs_from_legacy       reads legacy, resolves, writes ranking_record
        aggregate_legacy_analytics reads ranking_record, writes aggregated_rankings

    Seeding has to precede the ingest because the resolver loads canonical
    profiles at construction; aggregation has to follow it because it reads the
    rows the ingest just wrote.
    """
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

    if seed_legacy_entities is not None:
        print("[4/4] Seeding canonical entities from the legacy tables...")
        seed_summary = seed_legacy_entities(
            ranking_year=args.ranking_year,
            source_code="QS",
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(f"[analytics] seeded ranking_source: {seed_summary.ranking_source_count}")
        print(f"[analytics] seeded canonical_university: {seed_summary.canonical_university_count}")
        print(f"[analytics] seeded canonical_university_link: {seed_summary.canonical_university_link_count}")

    # Deliberately unguarded. This used to be wrapped in a bare
    # `except Exception` that printed "[warn] QS multi-source sync skipped" and
    # carried on. That was survivable only while the bridge wrote
    # ranking_record too, so the rankings API stayed populated and the loss
    # showed up nowhere. It is the only writer now: if it raises, the run has
    # produced no QS ranking records at all, and saying so is the only useful
    # behaviour.
    summary = sync_qs_from_legacy(
        ranking_year=args.ranking_year,
        source_code="QS",
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_database=args.pg_database,
        pg_user=args.pg_user,
        pg_password=args.pg_password,
    )
    print(
        "[multi-source] "
        f"rows={summary.standardized_count} matched={summary.matched_count} "
        f"unresolved={summary.unresolved_count} duplicates={summary.duplicate_input_count}"
    )

    if aggregate_legacy_analytics is not None:
        print("[4/4] Aggregating analytics from warehouse.ranking_record...")
        analytics_summary = aggregate_legacy_analytics(
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
        print(f"[analytics] ranking_record rows aggregated: {analytics_summary.ranking_record_count}")
        print(f"[analytics] created aggregation_run: {analytics_summary.aggregation_run_id}")
        print(f"[analytics] aggregated_rankings count: {analytics_summary.aggregated_rankings_count}")
        print(f"[analytics] latest view count: {analytics_summary.latest_view_count}")
        if analytics_summary.latest_view_count <= 0:
            raise RuntimeError(
                "Analytics sync completed but analytics.v_aggregated_rankings_latest has 0 rows "
                f"for year={args.ranking_year}, source=QS, universe=global/global. "
                "The product rankings API will return empty results."
            )

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
