from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class PipelineCommandDependencies:
    ensure_postgres_schema: Callable[..., None]
    load_snapshot: Callable[[Path], list[Any]]
    run_qs_crawl: Callable[..., tuple[list[Any], dict[str, Any]]]
    save_snapshot: Callable[[Path, list[Any]], None]
    save_deferred_detail_list: Callable[[Path, list[Any], list[str]], int]
    normalize_universities: Callable[[list[Any]], list[Any]]
    write_universities: Callable[..., tuple[int, int, int]]
    sync_qs_multi_source_rankings: Callable[..., Any]
    query_rankings: Callable[..., list[Any]]
    enrich_deferred_details: Callable[..., tuple[int, int, int, int, int]]
    load_json_payload: Callable[[Path], list[Any]]
    ingest_rankings_payload: Callable[..., Any]
    run_qs_universe_ingestion: Callable[..., tuple[Any, list[Any], list[Any], bool]]
    iter_all_qs_universes: Callable[[], Any]
    iter_major_qs_universes: Callable[[], Any]
    get_qs_universe_spec: Callable[[str, str], Any]
    recommend_universities_from_db: Callable[..., list[Any]]
    recommend_universities_v2_from_db: Callable[..., Any]
    recommend_universities_v3_from_db: Callable[..., Any]
    compare_universities_from_db: Callable[..., Any]
    parse_preference_weights: Callable[[str | None], dict[str, float]]


def dispatch_command(args: Any, deps: PipelineCommandDependencies) -> int:
    if args.command == "run":
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )

        snapshot_file = Path(args.snapshot_file)
        checkpoint_file = Path(args.checkpoint_file)

        if args.resume and snapshot_file.exists():
            print("[1/4] Loading snapshot (resume mode)...")
            universities = deps.load_snapshot(snapshot_file)
        else:
            print("[1/4] Crawling QS data...")
            universities, crawl_meta = deps.run_qs_crawl(
                args.limit,
                args.ranking_id,
                args.use_async,
                args.workers,
                args.request_delay,
                args.local_parse_workers,
                not args.rankings_only,
                args.detail_403_streak_threshold,
                args.detail_chunk_size,
            )
            if not universities:
                print("No universities crawled. Exiting.")
                return 1
            deps.save_snapshot(snapshot_file, universities)
            deferred_count = deps.save_deferred_detail_list(
                Path(args.deferred_details_file),
                universities,
                crawl_meta.get("detail_deferred_paths", []),
            )
            if deferred_count > 0:
                print(
                    f"[note] Deferred detail enrichment items: {deferred_count} "
                    f"(saved to {Path(args.deferred_details_file)})"
                )
            if crawl_meta.get("detail_fallback_triggered"):
                print(
                    "[note] Detail auto-degrade was triggered by repeated 403 responses; "
                    "run deferred detail enrichment in smaller batches."
                )
                print(
                    f"[note] Observed detail 403 count in this run: "
                    f"{crawl_meta.get('detail_forbidden_count', 0)}"
                )

        print("[2/4] Normalizing fields (Python baseline)...")
        normalized = deps.normalize_universities(universities)

        print(f"[3/4] Writing {len(normalized)} rows to {args.db_type}...")
        inserted, skipped, failed = deps.write_universities(
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
            resume=bool(args.resume),
            ranking_year=args.ranking_year,
            write_batch_size=max(1, args.write_batch_size),
        )

        print("[4/4] Done.")
        print(f"Inserted: {inserted}, Skipped(resume): {skipped}, Failed: {failed}")
        print(f"Checkpoint: {checkpoint_file}")
        try:
            summary = deps.sync_qs_multi_source_rankings(
                normalized,
                ranking_year=args.ranking_year,
                pg_host=args.pg_host,
                pg_port=args.pg_port,
                pg_database=args.pg_database,
                pg_user=args.pg_user,
                pg_password=args.pg_password,
                batch_id=None,
            )
            print(
                "[multi-source] "
                f"rows={summary.standardized_count} matched={summary.matched_count} "
                f"unresolved={summary.unresolved_count} duplicates={summary.duplicate_input_count} "
                f"aggregated_years={summary.years_aggregated}"
            )
        except Exception as exc:
            print(f"[warn] QS multi-source sync skipped: {exc}")
        return 0

    if args.command == "query":
        rows = deps.query_rankings(
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
            print(
                f"{rank_start} | {display_name} | {country_name} | "
                f"{'' if score is None else score} | {ranking_type}"
            )
        return 0

    if args.command == "enrich-details":
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )

        print("[1/2] Enriching deferred detail pages...")
        success, skipped_cooldown, failed, skipped_no_uid, remaining = deps.enrich_deferred_details(
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

    if args.command == "ingest-rankings":
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        payload_path = Path(args.input_file)
        payload = deps.load_json_payload(payload_path)
        summary = deps.ingest_rankings_payload(
            source=args.source,
            payload=payload,
            ranking_year=args.ranking_year,
            ranking_type=args.ranking_type,
            source_version=args.source_version,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
            batch_id=args.batch_id,
        )
        print(
            f"source={args.source} rows={summary.standardized_count} matched={summary.matched_count} "
            f"unresolved={summary.unresolved_count} duplicates={summary.duplicate_input_count}"
        )
        print(
            f"by_source={summary.by_source_count} aggregated_years={summary.years_aggregated} "
            f"aggregated_rows={summary.aggregated_row_count}"
        )
        return 0

    if args.command in {"run-qs-global", "run-qs-region", "run-qs-subject", "run-qs-special"}:
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        universe_type = "global"
        universe_key = "global"
        if args.command == "run-qs-region":
            universe_type = "region"
            universe_key = args.region
        elif args.command == "run-qs-subject":
            universe_type = "subject"
            universe_key = args.subject
        elif args.command == "run-qs-special":
            universe_type = "special"
            universe_key = args.special

        while True:
            summary, normalized, standardized, interrupted = deps.run_qs_universe_ingestion(
                universe_type=universe_type,
                universe_key=universe_key,
                limit=args.limit,
                ranking_year=args.ranking_year,
                use_async=args.use_async,
                workers=args.workers,
                request_delay=args.request_delay,
                local_parse_workers=args.local_parse_workers,
                pg_host=args.pg_host,
                pg_port=args.pg_port,
                pg_database=args.pg_database,
                pg_user=args.pg_user,
                pg_password=args.pg_password,
                output_dir=Path(args.output_dir),
                resume=bool(getattr(args, "resume", False)),
            )
            print(
                f"[qs-universe] {universe_type}/{universe_key} "
                f"normalized={len(normalized)} standardized={len(standardized)} "
                f"matched={summary.matched_count} unresolved={summary.unresolved_count} "
                f"rows_written={summary.rows_written} run_id={summary.run_id} "
                f"aggregated_years={summary.years_aggregated}"
            )
            if interrupted:
                print(f"\n[pipeline] Graceful shutdown completed for {universe_type}/{universe_key}. Exiting.")
                break
            print(
                f"\n--- [continuous] Completed pass for {universe_type}/{universe_key}. "
                "Starting next pass in 5s... ---"
            )
            time.sleep(5)
        return 0

    if args.command in {"run-all-qs-universes", "run-qs-universes", "run-qs-major"}:
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        results: list[dict[str, Any]] = []
        failures = 0
        if args.command == "run-qs-universes":
            if args.universe_type == "all":
                selected_specs = list(deps.iter_all_qs_universes())
            else:
                if args.universe_key:
                    selected_specs = [deps.get_qs_universe_spec(args.universe_type, args.universe_key)]
                elif args.universe_type == "global":
                    selected_specs = [deps.get_qs_universe_spec("global", "global")]
                else:
                    raise SystemExit("--universe-key is required when --universe-type is not 'all' or 'global'")
        elif args.command == "run-qs-major":
            selected_specs = list(deps.iter_major_qs_universes())
        else:
            selected_specs = list(deps.iter_all_qs_universes())

        while True:
            total_specs = len(selected_specs)
            for spec in selected_specs:
                current_index = len(results) + 1
                label = f"{spec.universe_type}/{spec.universe_key}"
                print(f"\n=== [{current_index}/{total_specs}] Starting QS universe: {label} ===")
                try:
                    summary, normalized, standardized, interrupted = deps.run_qs_universe_ingestion(
                        universe_type=spec.universe_type,
                        universe_key=spec.universe_key,
                        limit=args.limit,
                        ranking_year=args.ranking_year,
                        use_async=args.use_async,
                        workers=args.workers,
                        request_delay=args.request_delay,
                        local_parse_workers=args.local_parse_workers,
                        pg_host=args.pg_host,
                        pg_port=args.pg_port,
                        pg_database=args.pg_database,
                        pg_user=args.pg_user,
                        pg_password=args.pg_password,
                        output_dir=Path(args.output_dir),
                        resume=bool(getattr(args, "resume", False)),
                    )
                    results.append(
                        {
                            "universe_type": spec.universe_type,
                            "universe_key": spec.universe_key,
                            "normalized_count": len(normalized),
                            "standardized_count": len(standardized),
                            "matched_count": summary.matched_count,
                            "unresolved_count": summary.unresolved_count,
                            "aggregated_years": summary.years_aggregated,
                        }
                    )
                    print(
                        f"=== [{current_index}/{total_specs}] Completed QS universe: {label} | "
                        f"normalized={len(normalized)} standardized={len(standardized)} "
                        f"matched={summary.matched_count} unresolved={summary.unresolved_count} "
                        f"rows_written={summary.rows_written} run_id={summary.run_id} ==="
                    )
                    if interrupted:
                        print(f"\n[pipeline] Graceful shutdown completed for {label}. Stopping crawler loop.")
                        print(json.dumps({"failures": failures, "results": results}, ensure_ascii=False, indent=2))
                        return 0
                except Exception as exc:
                    failures += 1
                    results.append(
                        {
                            "universe_type": spec.universe_type,
                            "universe_key": spec.universe_key,
                            "error": str(exc),
                        }
                    )
                    print(
                        f"[warn] QS universe failed but pipeline continues: "
                        f"{spec.universe_type}/{spec.universe_key} -> {exc}"
                    )

            print("\n--- [continuous] Completed full pass of all universes. Starting next pass in 30s... ---")
            results = []
            time.sleep(30)
        return 0

    if args.command == "recommend":
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        rows = deps.recommend_universities_from_db(
            country=args.country,
            ielts_score=args.ielts_score,
            target_rank=args.target_rank,
            preferred_ranking_source=args.preferred_ranking_source,
            limit=args.limit,
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        if not rows:
            print("No recommendations matched the provided constraints.")
            return 0

        print("canonical_id | university | country | aggregated_rank | ielts_min | score")
        for row in rows:
            print(
                f"{row.canonical_university_id} | {row.university_name} | {row.country or ''} | "
                f"{'' if row.aggregated_rank is None else row.aggregated_rank} | "
                f"{'' if row.ielts_min is None else row.ielts_min} | {row.matching_score:.2f}"
            )
            print(f"  explanation: {row.explanation}")
        return 0

    if args.command == "recommend-v2":
        if args.target_rank <= 0:
            raise SystemExit("--target-rank must be a positive integer")
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        grouped = deps.recommend_universities_v2_from_db(
            country=args.country,
            ielts_score=args.ielts,
            target_rank=args.target_rank,
            risk_profile=args.risk_profile,
            preferred_ranking_source=args.preferred_ranking_source,
            limit=args.limit,
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(json.dumps(grouped, ensure_ascii=False, indent=2, sort_keys=False))
        return 0

    if args.command == "recommend-v3":
        if args.target_rank <= 0:
            raise SystemExit("--target-rank must be a positive integer")
        if args.limit <= 0:
            raise SystemExit("--limit must be a positive integer")
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        try:
            preference_weights = deps.parse_preference_weights(args.preference_weights)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        grouped = deps.recommend_universities_v3_from_db(
            country=args.country,
            country_policy=args.country_policy,
            ielts_score=args.ielts,
            target_rank=args.target_rank,
            risk_profile=args.risk_profile,
            preference_weights=preference_weights,
            preferred_ranking_source=args.preferred_ranking_source,
            limit=args.limit,
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(json.dumps(grouped, ensure_ascii=False, indent=2, sort_keys=False))
        return 0

    if args.command == "compare":
        identifiers = [args.a, *(args.b or [])]
        deps.ensure_postgres_schema(
            args.pg_host,
            args.pg_port,
            args.pg_database,
            args.pg_user,
            args.pg_password,
        )
        result = deps.compare_universities_from_db(
            identifiers=identifiers,
            ranking_year=args.ranking_year,
            pg_host=args.pg_host,
            pg_port=args.pg_port,
            pg_database=args.pg_database,
            pg_user=args.pg_user,
            pg_password=args.pg_password,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
        return 0

    return 1
