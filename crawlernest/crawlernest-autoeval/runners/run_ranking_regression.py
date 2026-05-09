#!/usr/bin/env python3
"""Ranking regression runner.

Loads golden expectations from datasets/ranking_regression/golden.json and
queries the live PostgreSQL warehouse to verify:
  - University is present in aggregated rankings
  - Aggregated rank is within the expected ceiling
  - Required sources appear in source_ranks_json
  - Country matches
  - Minimum source count is met

Usage
-----
  python run_ranking_regression.py [--pg-password test] [--pg-database clawer]

Exit codes
----------
  0  all assertions passed (or all skipped due to missing data)
  1  one or more assertions failed
  2  could not connect to PostgreSQL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DATASETS_DIR = Path(__file__).parent.parent / "datasets" / "ranking_regression"
GOLDEN_FILE = DATASETS_DIR / "golden.json"


def load_fixture(fixture_path: str) -> list[dict[str, Any]]:
    p = Path(fixture_path)
    if not p.exists():
        print(f"ERROR fixture file not found: {p}")
        sys.exit(2)
    payload = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        rows = payload.get("aggregated_rankings", [])
        if isinstance(rows, list):
            return rows
    print(f"ERROR unsupported fixture format: {p}")
    sys.exit(2)


def query_university_from_fixture(
    fixture_unis: list[dict[str, Any]], name_pattern: str, year: int
) -> dict[str, Any] | None:
    """Search fixture list using LIKE-style matching on display_name."""
    pattern = name_pattern.lower()
    for uni in fixture_unis:
        if pattern in uni.get("display_name", "").lower():
            source_ranks = uni.get("source_ranks_json", {})
            if isinstance(source_ranks, str):
                source_ranks = json.loads(source_ranks)
            return {
                "display_name": uni.get("display_name"),
                "canonical_slug": uni.get("canonical_slug"),
                "country_name": uni.get("country_name"),
                "display_rank": uni.get("display_rank"),
                "composite_score": uni.get("composite_score"),
                "source_ranks_json": source_ranks,
            }
    return None


def connect(host: str, port: int, database: str, user: str, password: str):
    try:
        import psycopg2  # type: ignore
        return psycopg2.connect(host=host, port=port, database=database,
                                user=user, password=password)
    except ImportError:
        print("ERROR psycopg2 is not installed — run: pip install psycopg2-binary")
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR cannot connect to PostgreSQL: {exc}")
        sys.exit(2)


def load_golden() -> list[dict[str, Any]]:
    if not GOLDEN_FILE.exists():
        print(f"ERROR golden file not found: {GOLDEN_FILE}")
        sys.exit(1)
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))


def query_university(conn, name_pattern: str, year: int) -> dict[str, Any] | None:
    """Return aggregated ranking row + country for a university matched by display_name."""
    sql = """
        SELECT
            cu.display_name,
            cu.canonical_slug,
            c.country_name,
            agg.display_rank,
            agg.composite_score,
            agg.source_ranks_json
        FROM analytics.v_aggregated_rankings_latest agg
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = agg.canonical_university_id
        LEFT JOIN warehouse.countries c
          ON c.country_id = cu.country_id
        WHERE agg.ranking_year = %s
          AND agg.universe_type = 'global'
          AND LOWER(cu.display_name) LIKE LOWER(%s)
        ORDER BY agg.display_rank ASC NULLS LAST
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (year, f"%{name_pattern}%"))
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "display_name": row[0],
        "canonical_slug": row[1],
        "country_name": row[2],
        "display_rank": row[3],
        "composite_score": float(row[4]) if row[4] is not None else None,
        "source_ranks_json": row[5] if isinstance(row[5], dict) else (
            json.loads(row[5]) if row[5] else {}
        ),
    }


def run_assertions(entry: dict[str, Any], row: dict[str, Any] | None) -> list[dict[str, Any]]:
    assertions = entry["assertions"]
    results: list[dict[str, Any]] = []
    name = entry["university_name_pattern"]

    if row is None:
        results.append({
            "assertion": "university_present",
            "passed": False,
            "detail": f"'{name}' not found in aggregated rankings for year {assertions.get('year')}",
        })
        return results

    results.append({"assertion": "university_present", "passed": True, "detail": row["display_name"]})

    if "display_rank_max" in assertions:
        rank = row["display_rank"]
        max_rank = assertions["display_rank_max"]
        passed = rank is not None and rank <= max_rank
        results.append({
            "assertion": "display_rank_max",
            "passed": passed,
            "detail": f"rank={rank} (max allowed={max_rank})",
        })

    if "country" in assertions:
        expected = assertions["country"]
        actual = row.get("country_name") or ""
        passed = actual.lower() == expected.lower()
        results.append({
            "assertion": "country",
            "passed": passed,
            "detail": f"expected='{expected}' actual='{actual}'",
        })

    source_ranks: dict[str, Any] = row.get("source_ranks_json") or {}

    if "source_presence_required" in assertions:
        for src in assertions["source_presence_required"]:
            present = src in source_ranks
            results.append({
                "assertion": f"source_present:{src}",
                "passed": present,
                "detail": f"source_ranks_json keys={list(source_ranks.keys())}",
            })

    if "source_count_min" in assertions:
        actual_count = len(source_ranks)
        min_count = assertions["source_count_min"]
        passed = actual_count >= min_count
        results.append({
            "assertion": "source_count_min",
            "passed": passed,
            "detail": f"sources={actual_count} (min={min_count}): {list(source_ranks.keys())}",
        })

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Ranking regression runner")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    parser.add_argument(
        "--fixture-file",
        metavar="PATH",
        help="Path to a JSON fixture file (list of university records). "
             "Skips PostgreSQL connection entirely — for CI / no-database mode.",
    )
    args = parser.parse_args()

    golden = load_golden()

    use_fixture = bool(args.fixture_file)
    fixture_unis: list[dict[str, Any]] = []
    conn = None

    if use_fixture:
        fixture_unis = load_fixture(args.fixture_file)
    else:
        conn = connect(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)

    total_pass = 0
    total_fail = 0
    entries_missing: list[str] = []
    mismatches: list[dict[str, Any]] = []

    try:
        for entry in golden:
            year = entry["assertions"].get("year", 2026)
            name = entry["university_name_pattern"]

            if use_fixture:
                row = query_university_from_fixture(fixture_unis, name, year)
            else:
                row = query_university(conn, name, year)

            assertion_results = run_assertions(entry, row)
            entry_pass = all(r["passed"] for r in assertion_results)
            entry_fail_count = sum(1 for r in assertion_results if not r["passed"])

            total_pass += sum(1 for r in assertion_results if r["passed"])
            total_fail += entry_fail_count

            if row is None:
                entries_missing.append(name)

            if not entry_pass:
                mismatches.append({
                    "id": entry["id"],
                    "university": name,
                    "failed_assertions": [r for r in assertion_results if not r["passed"]],
                })

            if not args.json:
                status = "PASS" if entry_pass else "FAIL"
                rank_str = f"rank={row['display_rank']}" if row else "NOT FOUND"
                print(f"[{status}] {entry['id']} — {name} ({rank_str})")
                for r in assertion_results:
                    icon = "  ✓" if r["passed"] else "  ✗"
                    print(f"{icon} {r['assertion']}: {r['detail']}")

    finally:
        if conn is not None:
            conn.close()

    summary = {
        "total_assertions": total_pass + total_fail,
        "passed": total_pass,
        "failed": total_fail,
        "missing_universities": entries_missing,
        "mismatches": mismatches,
        "result": "PASS" if total_fail == 0 else "FAIL",
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Results: {total_pass} passed, {total_fail} failed")
        if entries_missing:
            print(f"Missing universities: {entries_missing}")
        if total_fail == 0:
            print("Ranking regression: PASS")
        else:
            print("Ranking regression: FAIL")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
