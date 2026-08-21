#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import psycopg2


MODULE_ROOT = Path(__file__).resolve().parents[1]
for _path in (MODULE_ROOT, MODULE_ROOT / "crawlernest-core"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from db.analytics_bridge import (  # noqa: E402
    aggregate_legacy_analytics,
    seed_legacy_entities,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke test the legacy tables -> analytics path, end to end"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--source-code", default="QS")
    parser.add_argument("--universe-type", default="global")
    parser.add_argument("--universe-key", default="global")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8080/api/v1/rankings?page=1&pageSize=20&year=2026&scope=global",
        help="Product rankings API URL to verify after DB checks.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    try:
        # The whole path, twice. warehouse.ranking_record has one writer now --
        # the multi-source pipeline, reading the legacy tables -- so the bridge
        # alone no longer fills it, and a smoke test that only called the bridge
        # would assert against a table nothing had written.
        #
        # Seed first: the resolver loads canonical profiles when it is built.
        # Aggregate last: it reads the rows the ingest just wrote.
        first = _run_once(conn, args)
        second = _run_once(conn, args)

        ranking_record_count = _count_ranking_records(
            conn,
            year=args.year,
            source_code=args.source_code,
            universe_type=args.universe_type,
            universe_key=args.universe_key,
        )
        latest_view_count = _count_latest_view(
            conn,
            year=args.year,
            universe_type=args.universe_type,
            universe_key=args.universe_key,
        )
    finally:
        conn.close()

    # Idempotency across the whole path, not just the bridge: re-running must
    # update the same rows rather than adding to them or dropping any.
    if second != first:
        raise RuntimeError(
            f"Rerunning the path changed its counts: first={first}, second={second}"
        )
    if ranking_record_count <= 0:
        raise RuntimeError("warehouse.ranking_record has 0 rows after the ingest")
    if latest_view_count <= 0:
        raise RuntimeError("analytics.v_aggregated_rankings_latest has 0 rows after aggregation")

    api_count = _fetch_api_item_count(args.api_url)
    if api_count <= 0:
        raise RuntimeError(f"{args.api_url} returned 0 ranking items")

    print(f"[smoke] rerun is idempotent: {first}")
    print(f"[smoke] warehouse.ranking_record count: {ranking_record_count}")
    print(f"[smoke] analytics.v_aggregated_rankings_latest count: {latest_view_count}")
    print(f"[smoke] /api/v1/rankings item count: {api_count}")
    return 0


def _run_once(conn, args) -> tuple[int, int, int]:
    """Seed, ingest, aggregate. Returns the counts each phase reports."""
    from multi_source.legacy_source import load_legacy_ranking_records
    from pipeline.utils.postgres import build_multi_source_pipeline

    seed = seed_legacy_entities(
        conn, ranking_year=args.year, source_code=args.source_code
    )

    standardized = load_legacy_ranking_records(
        conn,
        source_code=args.source_code,
        ranking_year=args.year,
        universe_type=args.universe_type,
        universe_key=args.universe_key,
    )
    ingested = 0
    if standardized:
        pipeline = build_multi_source_pipeline(conn)
        summary = pipeline.ingest_records(
            standardized,
            # Unique per pass, deliberately. A constant run id makes
            # prune_superseded_records a no-op, so a smoke test using one would
            # leave the delete it is meant to cover unexercised. Two passes over
            # the same payload rewrite every row, so nothing is pruned and the
            # counts still have to match.
            batch_id=(
                f"smoke-{args.source_code.lower()}-{args.year}-"
                f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
            ),
            run_label_prefix="smoke_analytics_bridge",
            enable_aggregation=False,
        )
        ingested = int(getattr(summary, "matched_count", 0) or 0)

    aggregated = aggregate_legacy_analytics(
        conn,
        ranking_year=args.year,
        source_code=args.source_code,
        universe_type=args.universe_type,
        universe_key=args.universe_key,
    )
    return (
        seed.canonical_university_count,
        ingested,
        aggregated.aggregated_rankings_count,
    )


def _count_ranking_records(
    conn,
    *,
    year: int,
    source_code: str,
    universe_type: str,
    universe_key: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs
              ON rs.ranking_source_id = rr.ranking_source_id
            WHERE rr.ranking_year = %s
              AND rs.source_code = %s
              AND rr.universe_type = %s
              AND rr.universe_key = %s
            """,
            (year, source_code.upper(), universe_type.lower(), universe_key.lower()),
        )
        return int(cur.fetchone()[0] or 0)


def _count_latest_view(conn, *, year: int, universe_type: str, universe_key: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM analytics.v_aggregated_rankings_latest
            WHERE ranking_year = %s
              AND universe_type = %s
              AND universe_key = %s
            """,
            (year, universe_type.lower(), universe_key.lower()),
        )
        return int(cur.fetchone()[0] or 0)


def _fetch_api_item_count(api_url: str) -> int:
    with urlopen(api_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data") or {}
    items = data.get("items") or []
    return len(items)


if __name__ == "__main__":
    raise SystemExit(main())

