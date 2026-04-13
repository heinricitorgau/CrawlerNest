from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path


def build_parser(
    module_root: Path,
    *,
    default_ranking_year: int | None = None,
    write_batch_size: int = 100,
) -> argparse.ArgumentParser:
    default_ranking_year = default_ranking_year or dt.datetime.now().year
    workspace_root = module_root.parent
    default_snapshot = module_root / "crawlernest-kb" / "databases" / "last_crawl_snapshot.json"
    default_checkpoint = module_root / "crawlernest-kb" / "databases" / "pipeline_checkpoint.json"
    default_deferred = module_root / "crawlernest-kb" / "databases" / "pending_detail_enrichment.json"
    default_ranking_records = workspace_root / "crawlernest-samples" / "ranking_records.json"
    default_ranking_records_normalized = workspace_root / "crawlernest-samples" / "ranking_records_normalized.json"
    default_ranking_records_staging = workspace_root / "crawlernest-samples" / "ranking_records_staging.jsonl"
    default_ranking_ingest_db = workspace_root / "crawlernest-samples" / "ranking_staging_ingest.sqlite3"
    default_ranking_warehouse_preview = workspace_root / "crawlernest-samples" / "ranking_warehouse_preview.json"
    default_aggregated_ranking_preview = workspace_root / "crawlernest-samples" / "aggregated_rankings_preview.json"
    default_decision_ranking_preview = workspace_root / "crawlernest-samples" / "ranking_decision_preview.json"
    default_unresolved_report = workspace_root / "crawlernest-samples" / "ranking_unresolved_entities.json"
    default_admission_records = workspace_root / "crawlernest-samples" / "admission_records.json"

    parser = argparse.ArgumentParser(description="CrawlerNest ranking ingestion and recommendation pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Crawl QS -> normalize -> write to DB")
    run_parser.add_argument("--ranking-id", default="3990755")
    run_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
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
        default=write_batch_size,
        help="Commit/checkpoint interval during DB writes",
    )
    run_parser.add_argument("--use-async", action="store_true")
    run_parser.add_argument("--resource-guard", action="store_true", help="Auto slow down on high load / low memory")
    run_parser.add_argument("--resume", action="store_true", help="Resume from snapshot + checkpoint if available")
    run_parser.add_argument("--snapshot-file", default=str(default_snapshot))
    run_parser.add_argument("--checkpoint-file", default=str(default_checkpoint))
    run_parser.add_argument(
        "--deferred-details-file",
        default=str(default_deferred),
        help="JSON output path for deferred detail-enrichment items when anti-403 degrade is triggered",
    )
    run_parser.add_argument(
        "--detail-403-streak-threshold",
        type=int,
        default=8,
        help="Auto-degrade to rankings-only when this many consecutive detail 403 responses are observed",
    )
    run_parser.add_argument(
        "--detail-chunk-size",
        type=int,
        default=20,
        help="Async detail fetch chunk size for degrade checks (smaller chunks react to 403 sooner)",
    )
    run_parser.add_argument("--db-type", choices=["postgres"], default="postgres")
    run_parser.add_argument("--pg-host", default="localhost")
    run_parser.add_argument("--pg-port", type=int, default=5432)
    run_parser.add_argument("--pg-database", default="clawer")
    run_parser.add_argument("--pg-user", default="test")
    run_parser.add_argument("--pg-password", default="")
    run_parser.add_argument(
        "--with-the-rankings",
        action="store_true",
        help="After QS multi-source sync, ingest THE world rankings (warehouse.ranking_record, batch_id the-<year>)",
    )
    run_parser.add_argument(
        "--the-ranking-year",
        type=int,
        default=2026,
        help="THE edition when --with-the-rankings is set (default: 2026)",
    )
    run_parser.add_argument(
        "--the-output-dir",
        default=str(module_root / "crawlernest-kb" / "databases"),
        help="THE crawl JSON output directory when --with-the-rankings is set",
    )
    run_parser.add_argument(
        "--the-skip-seed",
        action="store_true",
        help="With --with-the-rankings, skip canonical seed/backfill after THE ingest",
    )

    query_parser = subparsers.add_parser("query", help="Query stored QS rankings from DB")
    query_parser.add_argument("keyword")
    query_parser.add_argument("--limit", type=int, default=20)
    query_parser.add_argument("--db-type", choices=["postgres"], default="postgres")
    query_parser.add_argument("--pg-host", default="localhost")
    query_parser.add_argument("--pg-port", type=int, default=5432)
    query_parser.add_argument("--pg-database", default="clawer")
    query_parser.add_argument("--pg-user", default="test")
    query_parser.add_argument("--pg-password", default="")

    enrich_parser = subparsers.add_parser(
        "enrich-details",
        help="Enrich admissions by crawling deferred university detail pages in small batches",
    )
    enrich_parser.add_argument("--limit", type=int, default=30, help="How many deferred schools to process this run")
    enrich_parser.add_argument("--request-delay", type=float, default=10.0, help="Delay (seconds) between detail requests")
    enrich_parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds for detail requests")
    enrich_parser.add_argument("--deferred-details-file", default=str(default_deferred))
    enrich_parser.add_argument("--db-type", choices=["postgres"], default="postgres")
    enrich_parser.add_argument("--pg-host", default="localhost")
    enrich_parser.add_argument("--pg-port", type=int, default=5432)
    enrich_parser.add_argument("--pg-database", default="clawer")
    enrich_parser.add_argument("--pg-user", default="test")
    enrich_parser.add_argument("--pg-password", default="")

    crawl_ranking_parser = subparsers.add_parser(
        "crawl-ranking",
        help="Run the ranking crawler engine and export mock records to JSON",
    )
    crawl_ranking_parser.add_argument(
        "--output-file",
        default=str(default_ranking_records),
        help="JSON output path for serialized ranking records",
    )
    crawl_ranking_parser.add_argument(
        "--with-normalized-output",
        action="store_true",
        help="Also export a normalized ranking artifact",
    )
    crawl_ranking_parser.add_argument(
        "--normalized-output-file",
        default=str(default_ranking_records_normalized),
        help="JSON output path for normalized ranking rows",
    )
    crawl_ranking_parser.add_argument(
        "--write-staging",
        action="store_true",
        help="Write normalized ranking rows to a staging JSONL artifact",
    )
    crawl_ranking_parser.add_argument(
        "--staging-output-file",
        default=str(default_ranking_records_staging),
        help="JSONL output path for normalized ranking staging rows",
    )

    crawl_admission_parser = subparsers.add_parser(
        "crawl-admission",
        help="Run the admission crawler engine and export mock records to JSON",
    )
    crawl_admission_parser.add_argument(
        "--output-file",
        default=str(default_admission_records),
        help="JSON output path for serialized admission records",
    )

    validate_ranking_staging_parser = subparsers.add_parser(
        "validate-ranking-staging",
        help="Validate ranking staging JSONL before any formal DB write step",
    )
    validate_ranking_staging_parser.add_argument(
        "--staging-input-file",
        default=str(default_ranking_records_staging),
        help="JSONL staging file to validate",
    )

    ingest_ranking_staging_parser = subparsers.add_parser(
        "ingest-ranking-staging",
        help="Ingest validated ranking staging JSONL into a safe SQLite store",
    )
    ingest_ranking_staging_parser.add_argument(
        "--staging-input-file",
        default=str(default_ranking_records_staging),
        help="JSONL staging file to ingest",
    )
    ingest_ranking_staging_parser.add_argument(
        "--sqlite-db-file",
        default=str(default_ranking_ingest_db),
        help="SQLite file used for safe ranking staging ingestion",
    )
    ingest_ranking_staging_parser.add_argument(
        "--write-target",
        choices=["sqlite", "postgres"],
        default="sqlite",
        help="Write target adapter used by ranking staging ingestion",
    )
    ingest_ranking_staging_parser.add_argument("--pg-host", default="localhost")
    ingest_ranking_staging_parser.add_argument("--pg-port", type=int, default=5432)
    ingest_ranking_staging_parser.add_argument("--pg-database", default="clawer")
    ingest_ranking_staging_parser.add_argument("--pg-user", default="test")
    ingest_ranking_staging_parser.add_argument("--pg-password", default="")
    ingest_ranking_staging_parser.add_argument(
        "--allow-partial-ingest",
        action="store_true",
        help="Ingest only validated rows even if invalid or duplicate rows are present",
    )

    preview_ranking_warehouse_parser = subparsers.add_parser(
        "preview-ranking-warehouse-map",
        help="Preview how ranking staging rows would map into warehouse-ready ranking rows",
    )
    preview_ranking_warehouse_parser.add_argument(
        "--input-source",
        choices=["jsonl", "postgres"],
        default="jsonl",
        help="Where to load staging rows from for warehouse mapping preview",
    )
    preview_ranking_warehouse_parser.add_argument(
        "--staging-input-file",
        default=str(default_ranking_records_staging),
        help="JSONL staging file used when --input-source=jsonl",
    )
    preview_ranking_warehouse_parser.add_argument(
        "--staging-table",
        default="ranking_staging_records",
        help="PostgreSQL staging table used when --input-source=postgres",
    )
    preview_ranking_warehouse_parser.add_argument(
        "--output-file",
        default=str(default_ranking_warehouse_preview),
        help="Artifact path for warehouse-ready preview rows",
    )
    preview_ranking_warehouse_parser.add_argument("--pg-host", default="localhost")
    preview_ranking_warehouse_parser.add_argument("--pg-port", type=int, default=5432)
    preview_ranking_warehouse_parser.add_argument("--pg-database", default="clawer")
    preview_ranking_warehouse_parser.add_argument("--pg-user", default="test")
    preview_ranking_warehouse_parser.add_argument("--pg-password", default="")

    write_ranking_warehouse_parser = subparsers.add_parser(
        "write-ranking-warehouse-preview",
        help="Write warehouse-ready ranking preview rows into a safe warehouse landing table",
    )
    write_ranking_warehouse_parser.add_argument(
        "--input-source",
        choices=["preview-json", "jsonl", "postgres"],
        default="preview-json",
        help="Where to load warehouse-ready rows from before landing write",
    )
    write_ranking_warehouse_parser.add_argument(
        "--preview-input-file",
        default=str(default_ranking_warehouse_preview),
        help="Warehouse preview artifact used when --input-source=preview-json",
    )
    write_ranking_warehouse_parser.add_argument(
        "--staging-input-file",
        default=str(default_ranking_records_staging),
        help="JSONL staging file used when --input-source=jsonl",
    )
    write_ranking_warehouse_parser.add_argument(
        "--staging-table",
        default="ranking_staging_records",
        help="PostgreSQL staging table used when --input-source=postgres",
    )
    write_ranking_warehouse_parser.add_argument(
        "--landing-schema",
        default="warehouse",
        help="Target schema for warehouse landing writes",
    )
    write_ranking_warehouse_parser.add_argument(
        "--landing-table",
        default="ranking_records_preview",
        help="Target table for warehouse landing writes",
    )
    write_ranking_warehouse_parser.add_argument("--pg-host", default="localhost")
    write_ranking_warehouse_parser.add_argument("--pg-port", type=int, default=5432)
    write_ranking_warehouse_parser.add_argument("--pg-database", default="clawer")
    write_ranking_warehouse_parser.add_argument("--pg-user", default="test")
    write_ranking_warehouse_parser.add_argument("--pg-password", default="")

    aggregate_ranking_preview_parser = subparsers.add_parser(
        "aggregate-ranking-preview",
        help="Aggregate warehouse-ready ranking preview rows into a safe aggregated preview table",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--input-source",
        choices=["preview-json", "postgres"],
        default="postgres",
        help="Where to load ranking rows from before preview aggregation",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--preview-input-file",
        default=str(default_ranking_warehouse_preview),
        help="Warehouse preview artifact used when --input-source=preview-json",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--source-schema",
        default="warehouse",
        help="Schema containing the warehouse preview source table when --input-source=postgres",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--source-table",
        default="ranking_records_preview",
        help="Warehouse preview source table when --input-source=postgres",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--target-schema",
        default="warehouse",
        help="Target schema for aggregated preview writes",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--target-table",
        default="aggregated_rankings_preview",
        help="Target table for aggregated preview writes",
    )
    aggregate_ranking_preview_parser.add_argument(
        "--output-file",
        default=str(default_aggregated_ranking_preview),
        help="Optional JSON artifact path for aggregated preview rows",
    )
    aggregate_ranking_preview_parser.add_argument("--pg-host", default="localhost")
    aggregate_ranking_preview_parser.add_argument("--pg-port", type=int, default=5432)
    aggregate_ranking_preview_parser.add_argument("--pg-database", default="clawer")
    aggregate_ranking_preview_parser.add_argument("--pg-user", default="test")
    aggregate_ranking_preview_parser.add_argument("--pg-password", default="")

    decision_ranking_preview_parser = subparsers.add_parser(
        "decision-ranking-preview",
        help="Build decision-layer preview rows from aggregated rankings preview",
    )
    decision_ranking_preview_parser.add_argument(
        "--source-schema",
        default="warehouse",
        help="Schema containing the aggregated rankings preview source table",
    )
    decision_ranking_preview_parser.add_argument(
        "--source-table",
        default="aggregated_rankings_preview",
        help="Source table used to load aggregated ranking rows",
    )
    decision_ranking_preview_parser.add_argument(
        "--target-schema",
        default="warehouse",
        help="Target schema for decision preview writes",
    )
    decision_ranking_preview_parser.add_argument(
        "--target-table",
        default="ranking_decision_preview",
        help="Target table for decision preview writes",
    )
    decision_ranking_preview_parser.add_argument(
        "--output-file",
        default=str(default_decision_ranking_preview),
        help="Optional JSON artifact path for decision preview rows",
    )
    decision_ranking_preview_parser.add_argument("--pg-host", default="localhost")
    decision_ranking_preview_parser.add_argument("--pg-port", type=int, default=5432)
    decision_ranking_preview_parser.add_argument("--pg-database", default="clawer")
    decision_ranking_preview_parser.add_argument("--pg-user", default="test")
    decision_ranking_preview_parser.add_argument("--pg-password", default="")

    resolve_ranking_entities_parser = subparsers.add_parser(
        "resolve-ranking-entities",
        help="Resolve warehouse preview rows to canonical_university_id using deterministic exact matches",
    )
    resolve_ranking_entities_parser.add_argument(
        "--target-schema",
        default="warehouse",
        help="Schema containing the ranking preview table",
    )
    resolve_ranking_entities_parser.add_argument(
        "--target-table",
        default="ranking_records_preview",
        help="Preview table to update with canonical entity resolution",
    )
    resolve_ranking_entities_parser.add_argument("--pg-host", default="localhost")
    resolve_ranking_entities_parser.add_argument("--pg-port", type=int, default=5432)
    resolve_ranking_entities_parser.add_argument("--pg-database", default="clawer")
    resolve_ranking_entities_parser.add_argument("--pg-user", default="test")
    resolve_ranking_entities_parser.add_argument("--pg-password", default="")

    unresolved_ranking_entities_parser = subparsers.add_parser(
        "unresolved-ranking-entities",
        help="Read-only report of unresolved ranking entities grouped by normalized university name",
    )
    unresolved_ranking_entities_parser.add_argument("--target-schema", default="warehouse")
    unresolved_ranking_entities_parser.add_argument("--target-table", default="ranking_records_preview")
    unresolved_ranking_entities_parser.add_argument("--limit", type=int, default=20)
    unresolved_ranking_entities_parser.add_argument(
        "--output-file",
        default="",
        help=f"Optional JSON output file for unresolved entity report (example default: {default_unresolved_report})",
    )
    unresolved_ranking_entities_parser.add_argument("--pg-host", default="localhost")
    unresolved_ranking_entities_parser.add_argument("--pg-port", type=int, default=5432)
    unresolved_ranking_entities_parser.add_argument("--pg-database", default="clawer")
    unresolved_ranking_entities_parser.add_argument("--pg-user", default="test")
    unresolved_ranking_entities_parser.add_argument("--pg-password", default="")

    refresh_ranking_resolution_parser = subparsers.add_parser(
        "refresh-ranking-resolution",
        help="Refresh deterministic ranking entity resolution, then regenerate the unresolved entity report",
    )
    refresh_ranking_resolution_parser.add_argument("--target-schema", default="warehouse")
    refresh_ranking_resolution_parser.add_argument("--target-table", default="ranking_records_preview")
    refresh_ranking_resolution_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="How many unresolved universities to print after the refresh",
    )
    refresh_ranking_resolution_parser.add_argument(
        "--output-file",
        default="",
        help=f"Optional JSON output file for the refreshed unresolved report (example default: {default_unresolved_report})",
    )
    refresh_ranking_resolution_parser.add_argument("--pg-host", default="localhost")
    refresh_ranking_resolution_parser.add_argument("--pg-port", type=int, default=5432)
    refresh_ranking_resolution_parser.add_argument("--pg-database", default="clawer")
    refresh_ranking_resolution_parser.add_argument("--pg-user", default="test")
    refresh_ranking_resolution_parser.add_argument("--pg-password", default="")

    seed_university_alias_parser = subparsers.add_parser(
        "seed-university-alias",
        help="Create or reuse a canonical university and seed a deterministic alias mapping",
    )
    seed_university_alias_parser.add_argument("--canonical", required=True)
    seed_university_alias_parser.add_argument("--alias", required=True)
    seed_university_alias_parser.add_argument("--pg-host", default="localhost")
    seed_university_alias_parser.add_argument("--pg-port", type=int, default=5432)
    seed_university_alias_parser.add_argument("--pg-database", default="clawer")
    seed_university_alias_parser.add_argument("--pg-user", default="test")
    seed_university_alias_parser.add_argument("--pg-password", default="")

    ingest_parser = subparsers.add_parser(
        "ingest-rankings",
        help="Ingest standardized ranking payloads for QS/THE/ARWU into multi-source tables and refresh aggregation",
    )
    ingest_parser.add_argument("--source", required=True, choices=["QS", "THE", "ARWU"])
    ingest_parser.add_argument("--input-file", required=True, help="JSON array or {\"rows\": [...]} payload")
    ingest_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    ingest_parser.add_argument("--ranking-type", default="world")
    ingest_parser.add_argument("--source-version", default=None)
    ingest_parser.add_argument("--batch-id", default=None)
    ingest_parser.add_argument("--pg-host", default="localhost")
    ingest_parser.add_argument("--pg-port", type=int, default=5432)
    ingest_parser.add_argument("--pg-database", default="clawer")
    ingest_parser.add_argument("--pg-user", default="test")
    ingest_parser.add_argument("--pg-password", default="")

    seed_canonical_parser = subparsers.add_parser(
        "seed-canonical",
        help="Promote unresolved warehouse.universities rows into canonical_university and canonical_university_link",
    )
    seed_canonical_parser.add_argument("--pg-host", default="localhost")
    seed_canonical_parser.add_argument("--pg-port", type=int, default=5432)
    seed_canonical_parser.add_argument("--pg-database", default="clawer")
    seed_canonical_parser.add_argument("--pg-user", default="test")
    seed_canonical_parser.add_argument("--pg-password", default="")

    seed_canonical_missing_parser = subparsers.add_parser(
        "seed-canonical-from-missing",
        help="Seed canonical_university rows from unresolved analytics.missing_entity_log entries and re-ingest THE",
    )
    seed_canonical_missing_parser.add_argument("--source", default="THE")
    seed_canonical_missing_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    seed_canonical_missing_parser.add_argument("--pg-host", default="localhost")
    seed_canonical_missing_parser.add_argument("--pg-port", type=int, default=5432)
    seed_canonical_missing_parser.add_argument("--pg-database", default="clawer")
    seed_canonical_missing_parser.add_argument("--pg-user", default="test")
    seed_canonical_missing_parser.add_argument("--pg-password", default="")

    backfill_ranking_parser = subparsers.add_parser(
        "backfill-ranking-records",
        help="Backfill multi-source warehouse.ranking_record rows from legacy warehouse.rankings using canonical_university_link",
    )
    backfill_ranking_parser.add_argument("--pg-host", default="localhost")
    backfill_ranking_parser.add_argument("--pg-port", type=int, default=5432)
    backfill_ranking_parser.add_argument("--pg-database", default="clawer")
    backfill_ranking_parser.add_argument("--pg-user", default="test")
    backfill_ranking_parser.add_argument("--pg-password", default="")

    rebuild_universe_parser = subparsers.add_parser(
        "rebuild-universe-records",
        help="Diagnose which QS universes are missing ranking_record rows for a given year",
    )
    rebuild_universe_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    rebuild_universe_parser.add_argument("--pg-host", default="localhost")
    rebuild_universe_parser.add_argument("--pg-port", type=int, default=5432)
    rebuild_universe_parser.add_argument("--pg-database", default="clawer")
    rebuild_universe_parser.add_argument("--pg-user", default="test")
    rebuild_universe_parser.add_argument("--pg-password", default="")

    the_rankings_parser = subparsers.add_parser(
        "run-the-rankings",
        help="Crawl THE world rankings, ingest into multi-source tables, and optionally seed/backfill visibility",
    )
    the_rankings_parser.add_argument("--ranking-year", type=int, default=2026)
    the_rankings_parser.add_argument(
        "--output-dir",
        default=str(module_root / "crawlernest-kb" / "databases"),
    )
    the_rankings_parser.add_argument("--skip-seed", action="store_true")
    the_rankings_parser.add_argument("--pg-host", default="localhost")
    the_rankings_parser.add_argument("--pg-port", type=int, default=5432)
    the_rankings_parser.add_argument("--pg-database", default="clawer")
    the_rankings_parser.add_argument("--pg-user", default="test")
    the_rankings_parser.add_argument("--pg-password", default="")

    arwu_rankings_parser = subparsers.add_parser(
        "run-arwu-rankings",
        help="Crawl ARWU world rankings, ingest into multi-source tables, and optionally seed/backfill visibility",
    )
    arwu_rankings_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    arwu_rankings_parser.add_argument(
        "--output-dir",
        default=str(module_root / "crawlernest-kb" / "databases"),
    )
    arwu_rankings_parser.add_argument("--skip-seed", action="store_true")
    arwu_rankings_parser.add_argument("--pg-host", default="localhost")
    arwu_rankings_parser.add_argument("--pg-port", type=int, default=5432)
    arwu_rankings_parser.add_argument("--pg-database", default="clawer")
    arwu_rankings_parser.add_argument("--pg-user", default="test")
    arwu_rankings_parser.add_argument("--pg-password", default="")

    validate_global_sources_parser = subparsers.add_parser(
        "validate-global-multi-source",
        help="Validate presence of QS/THE/ARWU global rows and multi-source aggregation coverage",
    )
    validate_global_sources_parser.add_argument("--ranking-year", type=int, default=None)
    validate_global_sources_parser.add_argument("--pg-host", default="localhost")
    validate_global_sources_parser.add_argument("--pg-port", type=int, default=5432)
    validate_global_sources_parser.add_argument("--pg-database", default="clawer")
    validate_global_sources_parser.add_argument("--pg-user", default="test")
    validate_global_sources_parser.add_argument("--pg-password", default="")

    qs_global_parser = subparsers.add_parser(
        "run-qs-global",
        help="Run QS global rankings ingestion into the multi-universe store",
    )
    qs_global_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_global_parser.add_argument("--limit", type=int, default=0)
    qs_global_parser.add_argument("--workers", type=int, default=1)
    qs_global_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_global_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_global_parser.add_argument("--use-async", action="store_true")
    qs_global_parser.add_argument("--resume", action="store_true", help="Resume from the last saved raw snapshot for this universe")
    qs_global_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_global_parser.add_argument("--pg-host", default="localhost")
    qs_global_parser.add_argument("--pg-port", type=int, default=5432)
    qs_global_parser.add_argument("--pg-database", default="clawer")
    qs_global_parser.add_argument("--pg-user", default="test")
    qs_global_parser.add_argument("--pg-password", default="")

    qs_region_parser = subparsers.add_parser(
        "run-qs-region",
        help="Run one QS regional ranking universe ingestion",
    )
    qs_region_parser.add_argument(
        "--region",
        required=True,
        choices=["europe", "asia", "latin-america", "arab-region", "oceania", "africa", "north-america"],
    )
    qs_region_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_region_parser.add_argument("--limit", type=int, default=0)
    qs_region_parser.add_argument("--workers", type=int, default=1)
    qs_region_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_region_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_region_parser.add_argument("--use-async", action="store_true")
    qs_region_parser.add_argument("--resume", action="store_true", help="Resume from the last saved raw snapshot for this universe")
    qs_region_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_region_parser.add_argument("--pg-host", default="localhost")
    qs_region_parser.add_argument("--pg-port", type=int, default=5432)
    qs_region_parser.add_argument("--pg-database", default="clawer")
    qs_region_parser.add_argument("--pg-user", default="test")
    qs_region_parser.add_argument("--pg-password", default="")

    qs_subject_parser = subparsers.add_parser(
        "run-qs-subject",
        help="Run one QS subject ranking universe ingestion",
    )
    qs_subject_parser.add_argument(
        "--subject",
        required=True,
        choices=["engineering-technology", "computer-science", "business-management"],
    )
    qs_subject_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_subject_parser.add_argument("--limit", type=int, default=0)
    qs_subject_parser.add_argument("--workers", type=int, default=1)
    qs_subject_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_subject_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_subject_parser.add_argument("--use-async", action="store_true")
    qs_subject_parser.add_argument("--resume", action="store_true", help="Resume from the last saved raw snapshot for this universe")
    qs_subject_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_subject_parser.add_argument("--pg-host", default="localhost")
    qs_subject_parser.add_argument("--pg-port", type=int, default=5432)
    qs_subject_parser.add_argument("--pg-database", default="clawer")
    qs_subject_parser.add_argument("--pg-user", default="test")
    qs_subject_parser.add_argument("--pg-password", default="")

    qs_special_parser = subparsers.add_parser(
        "run-qs-special",
        help="Run one QS special ranking universe ingestion",
    )
    qs_special_parser.add_argument(
        "--special",
        required=True,
        choices=["sustainability", "mba", "business-masters"],
    )
    qs_special_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_special_parser.add_argument("--limit", type=int, default=0)
    qs_special_parser.add_argument("--workers", type=int, default=1)
    qs_special_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_special_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_special_parser.add_argument("--use-async", action="store_true")
    qs_special_parser.add_argument("--resume", action="store_true", help="Resume from the last saved raw snapshot for this universe")
    qs_special_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_special_parser.add_argument("--pg-host", default="localhost")
    qs_special_parser.add_argument("--pg-port", type=int, default=5432)
    qs_special_parser.add_argument("--pg-database", default="clawer")
    qs_special_parser.add_argument("--pg-user", default="test")
    qs_special_parser.add_argument("--pg-password", default="")

    qs_all_parser = subparsers.add_parser(
        "run-all-qs-universes",
        help="Run every configured QS ranking universe independently with failure isolation",
    )
    qs_all_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_all_parser.add_argument("--limit", type=int, default=0)
    qs_all_parser.add_argument("--workers", type=int, default=1)
    qs_all_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_all_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_all_parser.add_argument("--use-async", action="store_true")
    qs_all_parser.add_argument("--resume", action="store_true", help="Resume each universe from its last saved raw snapshot")
    qs_all_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_all_parser.add_argument("--pg-host", default="localhost")
    qs_all_parser.add_argument("--pg-port", type=int, default=5432)
    qs_all_parser.add_argument("--pg-database", default="clawer")
    qs_all_parser.add_argument("--pg-user", default="test")
    qs_all_parser.add_argument("--pg-password", default="")

    qs_major_parser = subparsers.add_parser(
        "run-qs-major",
        help="Run only the major QS ranking universes (Global + 5 Regions) independently",
    )
    qs_major_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_major_parser.add_argument("--limit", type=int, default=0)
    qs_major_parser.add_argument("--workers", type=int, default=1)
    qs_major_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_major_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_major_parser.add_argument("--use-async", action="store_true")
    qs_major_parser.add_argument("--resume", action="store_true", help="Resume each universe from its last saved raw snapshot")
    qs_major_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_major_parser.add_argument("--pg-host", default="localhost")
    qs_major_parser.add_argument("--pg-port", type=int, default=5432)
    qs_major_parser.add_argument("--pg-database", default="clawer")
    qs_major_parser.add_argument("--pg-user", default="test")
    qs_major_parser.add_argument("--pg-password", default="")

    qs_universes_parser = subparsers.add_parser(
        "run-qs-universes",
        help="Unified QS multi-universe runner; defaults to all universes, optionally narrow by type/key",
    )
    qs_universes_parser.add_argument(
        "--universe-type",
        default="all",
        choices=["all", "global", "region", "subject", "special"],
    )
    qs_universes_parser.add_argument("--universe-key", default=None)
    qs_universes_parser.add_argument("--ranking-year", type=int, default=default_ranking_year)
    qs_universes_parser.add_argument("--limit", type=int, default=0)
    qs_universes_parser.add_argument("--workers", type=int, default=1)
    qs_universes_parser.add_argument("--request-delay", type=float, default=10.0)
    qs_universes_parser.add_argument("--local-parse-workers", type=int, default=4)
    qs_universes_parser.add_argument("--use-async", action="store_true")
    qs_universes_parser.add_argument("--resume", action="store_true", help="Resume each selected universe from its last saved raw snapshot")
    qs_universes_parser.add_argument("--output-dir", default=str(module_root / "crawlernest-kb" / "qs_universes"))
    qs_universes_parser.add_argument("--pg-host", default="localhost")
    qs_universes_parser.add_argument("--pg-port", type=int, default=5432)
    qs_universes_parser.add_argument("--pg-database", default="clawer")
    qs_universes_parser.add_argument("--pg-user", default="test")
    qs_universes_parser.add_argument("--pg-password", default="")

    recommend_parser = subparsers.add_parser(
        "recommend",
        help="Run the rule-based university recommendation engine against PostgreSQL candidate data",
    )
    recommend_parser.add_argument("--country", default=None)
    recommend_parser.add_argument("--ielts-score", type=float, default=None)
    recommend_parser.add_argument("--target-rank", type=int, default=None)
    recommend_parser.add_argument("--preferred-ranking-source", default=None)
    recommend_parser.add_argument("--limit", type=int, default=10)
    recommend_parser.add_argument("--ranking-year", type=int, default=None)
    recommend_parser.add_argument("--pg-host", default="localhost")
    recommend_parser.add_argument("--pg-port", type=int, default=5432)
    recommend_parser.add_argument("--pg-database", default="clawer")
    recommend_parser.add_argument("--pg-user", default="test")
    recommend_parser.add_argument("--pg-password", default="")

    recommend_v2_parser = subparsers.add_parser(
        "recommend-v2",
        help="Run grouped reach/target/safety recommendations against PostgreSQL candidate data",
    )
    recommend_v2_parser.add_argument("--country", default=None)
    recommend_v2_parser.add_argument("--ielts", type=float, default=None)
    recommend_v2_parser.add_argument("--target-rank", type=int, required=True)
    recommend_v2_parser.add_argument("--risk-profile", default="balanced", choices=["conservative", "balanced", "aggressive"])
    recommend_v2_parser.add_argument("--preferred-ranking-source", default=None)
    recommend_v2_parser.add_argument("--limit", type=int, default=5)
    recommend_v2_parser.add_argument("--ranking-year", type=int, default=None)
    recommend_v2_parser.add_argument("--pg-host", default="localhost")
    recommend_v2_parser.add_argument("--pg-port", type=int, default=5432)
    recommend_v2_parser.add_argument("--pg-database", default="clawer")
    recommend_v2_parser.add_argument("--pg-user", default="test")
    recommend_v2_parser.add_argument("--pg-password", default="")

    recommend_v3_parser = subparsers.add_parser(
        "recommend-v3",
        help="Run hybrid grouped recommendations with configurable preference weights against PostgreSQL candidate data",
    )
    recommend_v3_parser.add_argument("--country", default=None)
    recommend_v3_parser.add_argument("--country-policy", default=None, choices=["hard_filter", "soft_preference"])
    recommend_v3_parser.add_argument("--ielts", type=float, default=None)
    recommend_v3_parser.add_argument("--target-rank", type=int, required=True)
    recommend_v3_parser.add_argument("--risk-profile", default="balanced", choices=["conservative", "balanced", "aggressive"])
    recommend_v3_parser.add_argument(
        "--preference-weights",
        default=None,
        help='Optional JSON object, for example {"ranking":0.5,"ielts":0.2,"confidence":0.2,"country_match":0.1}',
    )
    recommend_v3_parser.add_argument("--preferred-ranking-source", default=None)
    recommend_v3_parser.add_argument("--limit", type=int, default=5)
    recommend_v3_parser.add_argument("--ranking-year", type=int, default=None)
    recommend_v3_parser.add_argument("--pg-host", default="localhost")
    recommend_v3_parser.add_argument("--pg-port", type=int, default=5432)
    recommend_v3_parser.add_argument("--pg-database", default="clawer")
    recommend_v3_parser.add_argument("--pg-user", default="test")
    recommend_v3_parser.add_argument("--pg-password", default="")

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two or more universities using aggregated ranking, source ranks, IELTS, and completeness",
    )
    compare_parser.add_argument("--a", required=True, help="First university name or canonical university id")
    compare_parser.add_argument(
        "--b",
        required=True,
        action="append",
        help="Second university and any additional universities to compare",
    )
    compare_parser.add_argument("--ranking-year", type=int, default=None)
    compare_parser.add_argument("--pg-host", default="localhost")
    compare_parser.add_argument("--pg-port", type=int, default=5432)
    compare_parser.add_argument("--pg-database", default="clawer")
    compare_parser.add_argument("--pg-user", default="test")
    compare_parser.add_argument("--pg-password", default="")
    return parser
