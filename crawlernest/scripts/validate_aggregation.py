#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from typing import Any

import psycopg2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate multi-universe aggregated rankings."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--universe-type",
        choices=["global", "region", "subject"],
        required=True,
    )
    parser.add_argument("--universe-key")
    parser.add_argument("--pg-host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--pg-database", default=os.getenv("PGDATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.getenv("PGUSER", "test"))
    parser.add_argument("--pg-password", default=os.getenv("PGPASSWORD"))
    return parser


def resolve_universe_key(universe_type: str, universe_key: str | None) -> str:
    if universe_type == "global":
        return universe_key or "global"
    if not universe_key:
        raise SystemExit("--universe-key is required for region and subject validation")
    return universe_key


def connect(args: argparse.Namespace) -> Any:
    return psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )


def fetch_rows(
    conn: Any,
    *,
    year: int,
    universe_type: str,
    universe_key: str,
) -> list[tuple[int | None, int, str, str | None]]:
    sql = """
        SELECT
            ar.display_rank,
            ar.canonical_university_id,
            cu.display_name AS university_name,
            c.country_name
        FROM analytics.v_aggregated_rankings_latest ar
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = ar.canonical_university_id
        LEFT JOIN warehouse.countries c
          ON c.country_id = cu.country_id
        WHERE ar.ranking_year = %s
          AND ar.universe_type = %s
          AND ar.universe_key = %s
        ORDER BY
            ar.display_rank NULLS LAST,
            cu.display_name ASC,
            ar.canonical_university_id ASC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (year, universe_type, universe_key))
        return cur.fetchall()


def compute_missing_ranks(ranks: list[int], expected_count: int) -> list[int]:
    if expected_count <= 0:
        return []
    rank_set = set(ranks)
    return [rank for rank in range(1, expected_count + 1) if rank not in rank_set]


def print_report(
    *,
    year: int,
    universe_type: str,
    universe_key: str,
    rows: list[tuple[int | None, int, str, str | None]],
) -> int:
    row_count = len(rows)
    distinct_university_count = len({row[1] for row in rows})
    duplicates = row_count - distinct_university_count
    null_rank_count = sum(1 for rank, _, _, _ in rows if rank is None)

    non_null_ranks = [int(rank) for rank, _, _, _ in rows if rank is not None]
    missing_ranks = compute_missing_ranks(non_null_ranks, distinct_university_count)
    rank_continuity = "OK" if not missing_ranks else "WARNING"

    country_counts = Counter((country or "Unknown") for _, _, _, country in rows)
    top_countries = country_counts.most_common(10)

    if duplicates > 0 or null_rank_count > 0:
        status = "FAIL"
    elif row_count == 0 or missing_ranks:
        status = "WARNING"
    else:
        status = "OK"

    print("----------------------------------------")
    print(f"Universe: {universe_type} / {universe_key} / {year}")
    print("----------------------------------------")
    print(f"rows: {row_count}")
    print(f"distinct_universities: {distinct_university_count}")
    print(f"duplicates: {duplicates}")
    print(f"null_rank: {null_rank_count}")
    print("")
    print(f"rank_continuity: {rank_continuity}")
    print(f"missing_ranks: {missing_ranks}")
    print("")
    print("top_countries:")
    if top_countries:
        for country, count in top_countries:
            print(f"- {country}: {count}")
    else:
        print("- None")
    print("")
    print("top_20:")
    if rows:
        for rank, _, university_name, country in rows[:20]:
            rank_label = "NULL" if rank is None else str(rank)
            country_label = country or "Unknown"
            print(f"{rank_label}  {university_name} ({country_label})")
    else:
        print("No rows found.")
    print("")
    print("----------------------------------------")
    print(f"STATUS: {status}")
    print("----------------------------------------")

    return 1 if status == "FAIL" else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    universe_key = resolve_universe_key(args.universe_type, args.universe_key)

    conn = connect(args)
    try:
        rows = fetch_rows(
            conn,
            year=args.year,
            universe_type=args.universe_type,
            universe_key=universe_key,
        )
    finally:
        conn.close()

    return print_report(
        year=args.year,
        universe_type=args.universe_type,
        universe_key=universe_key,
        rows=rows,
    )


if __name__ == "__main__":
    sys.exit(main())
