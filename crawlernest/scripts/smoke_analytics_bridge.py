#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

import psycopg2


MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from db.analytics_bridge import sync_legacy_rankings_to_analytics  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test legacy rankings -> analytics bridge")
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
        first = sync_legacy_rankings_to_analytics(
            conn,
            ranking_year=args.year,
            source_code=args.source_code,
            universe_type=args.universe_type,
            universe_key=args.universe_key,
        )
        second = sync_legacy_rankings_to_analytics(
            conn,
            ranking_year=args.year,
            source_code=args.source_code,
            universe_type=args.universe_type,
            universe_key=args.universe_key,
        )
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

    if second.ranking_record_count != first.ranking_record_count:
        raise RuntimeError(
            "Bridge rerun changed synced row count unexpectedly: "
            f"first={first.ranking_record_count}, second={second.ranking_record_count}"
        )
    if ranking_record_count <= 0:
        raise RuntimeError("warehouse.ranking_record has 0 rows after bridge sync")
    if latest_view_count <= 0:
        raise RuntimeError("analytics.v_aggregated_rankings_latest has 0 rows after bridge sync")

    api_count = _fetch_api_item_count(args.api_url)
    if api_count <= 0:
        raise RuntimeError(f"{args.api_url} returned 0 ranking items")

    print("[smoke] sync rerun: ok")
    print(f"[smoke] warehouse.ranking_record count: {ranking_record_count}")
    print(f"[smoke] analytics.v_aggregated_rankings_latest count: {latest_view_count}")
    print(f"[smoke] /api/v1/rankings item count: {api_count}")
    return 0


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

