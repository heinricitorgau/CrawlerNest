#!/usr/bin/env python3
"""Subject ranking evaluation runner.

Validates structural quality of subject_ranking_record data against
datasets/subject_rankings/golden.json. Checks:
  - Minimum university count per subject
  - All rank_position values are positive integers
  - Score values are within [0, 100]
  - No duplicate (canonical_university_id) per subject+year
  - subject_key is stored in normalized kebab-case

Usage
-----
  python run_subject_eval.py [--pg-password test] [--pg-database clawer]

Exit codes: 0=pass, 1=fail, 2=connection error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DATASETS_DIR = Path(__file__).parent.parent / "datasets" / "subject_rankings"
GOLDEN_FILE = DATASETS_DIR / "golden.json"


def connect(host: str, port: int, database: str, user: str, password: str):
    try:
        import psycopg2  # type: ignore
        return psycopg2.connect(host=host, port=port, database=database,
                                user=user, password=password)
    except ImportError:
        print("ERROR psycopg2 not installed — run: pip install psycopg2-binary")
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR cannot connect to PostgreSQL: {exc}")
        sys.exit(2)


def load_golden() -> list[dict[str, Any]]:
    if not GOLDEN_FILE.exists():
        print(f"ERROR golden file not found: {GOLDEN_FILE}")
        sys.exit(1)
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))


def query_subject_rows(conn, subject_key: str, year: int) -> list[dict[str, Any]]:
    sql = """
        SELECT
            srr.canonical_university_id,
            rs.subject_key,
            srr.ranking_year,
            srr.rank_position,
            srr.score
        FROM warehouse.subject_ranking_record srr
        JOIN warehouse.ranking_subject rs ON rs.subject_id = srr.subject_id
        WHERE rs.subject_key = %s AND srr.ranking_year = %s
        ORDER BY srr.rank_position ASC NULLS LAST
    """
    with conn.cursor() as cur:
        cur.execute(sql, (subject_key, year))
        rows = cur.fetchall()
    return [
        {
            "canonical_university_id": r[0],
            "subject_key": r[1],
            "ranking_year": r[2],
            "rank_position": r[3],
            "score": float(r[4]) if r[4] is not None else None,
        }
        for r in rows
    ]


def check_subject(entry: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assertions = entry["assertions"]
    results: list[dict[str, Any]] = []
    subject_key = entry["subject_key"]
    year = entry["year"]

    if not rows:
        if assertions.get("min_universities", 0) > 0:
            results.append({
                "assertion": "min_universities",
                "passed": False,
                "detail": f"No rows found for {subject_key}/{year}. Run the subject pipeline first.",
            })
        else:
            results.append({
                "assertion": "min_universities",
                "passed": True,
                "detail": "0 rows (min=0, skipped)",
            })
        return results

    count = len(rows)

    if "min_universities" in assertions:
        passed = count >= assertions["min_universities"]
        results.append({
            "assertion": "min_universities",
            "passed": passed,
            "detail": f"count={count} (min={assertions['min_universities']})",
        })

    if assertions.get("rank_position_all_positive"):
        bad = [r["rank_position"] for r in rows
               if r["rank_position"] is not None and r["rank_position"] <= 0]
        passed = len(bad) == 0
        results.append({
            "assertion": "rank_position_all_positive",
            "passed": passed,
            "detail": f"non-positive rank_positions={bad[:5]}" if bad else f"all {count} positive",
        })

    if "score_range" in assertions:
        lo, hi = assertions["score_range"]
        bad_scores = [r["score"] for r in rows
                      if r["score"] is not None and not (lo <= r["score"] <= hi)]
        passed = len(bad_scores) == 0
        results.append({
            "assertion": "score_range",
            "passed": passed,
            "detail": (f"out-of-range scores={bad_scores[:5]}" if bad_scores
                       else f"all {count} scores in [{lo}, {hi}]"),
        })

    if assertions.get("no_duplicate_universities"):
        ids = [r["canonical_university_id"] for r in rows]
        unique_ids = set(ids)
        duplicates = len(ids) - len(unique_ids)
        passed = duplicates == 0
        results.append({
            "assertion": "no_duplicate_universities",
            "passed": passed,
            "detail": (f"{duplicates} duplicate canonical_university_id(s)" if duplicates > 0
                       else f"all {count} universities unique"),
        })

    if assertions.get("subject_key_stored_normalized"):
        import re
        bad_keys = [r["subject_key"] for r in rows
                    if not re.match(r"^[a-z][a-z0-9-]*$", r["subject_key"])]
        passed = len(bad_keys) == 0
        unique_bad = list(set(bad_keys))
        results.append({
            "assertion": "subject_key_stored_normalized",
            "passed": passed,
            "detail": (f"non-normalized keys={unique_bad[:5]}" if unique_bad
                       else f"all subject_keys in kebab-case"),
        })

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Subject ranking evaluation runner")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()

    golden = load_golden()
    conn = connect(args.pg_host, args.pg_port, args.pg_database, args.pg_user, args.pg_password)

    total_pass = 0
    total_fail = 0
    mismatches: list[dict[str, Any]] = []

    try:
        for entry in golden:
            rows = query_subject_rows(conn, entry["subject_key"], entry["year"])
            assertion_results = check_subject(entry, rows)

            entry_pass = all(r["passed"] for r in assertion_results)
            total_pass += sum(1 for r in assertion_results if r["passed"])
            total_fail += sum(1 for r in assertion_results if not r["passed"])

            if not entry_pass:
                mismatches.append({
                    "id": entry["id"],
                    "subject_key": entry["subject_key"],
                    "year": entry["year"],
                    "failed_assertions": [r for r in assertion_results if not r["passed"]],
                })

            if not args.json:
                status = "PASS" if entry_pass else "FAIL"
                print(f"[{status}] {entry['id']} — {entry['subject_key']} ({entry['year']}) — {len(rows)} rows")
                for r in assertion_results:
                    icon = "  ✓" if r["passed"] else "  ✗"
                    print(f"{icon} {r['assertion']}: {r['detail']}")
    finally:
        conn.close()

    summary = {
        "total_assertions": total_pass + total_fail,
        "passed": total_pass,
        "failed": total_fail,
        "mismatches": mismatches,
        "result": "PASS" if total_fail == 0 else "FAIL",
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"Results: {total_pass} passed, {total_fail} failed")
        print(f"Subject eval: {summary['result']}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
