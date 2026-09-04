#!/usr/bin/env python3
"""Did every QS universe the registry asks for actually land for a given year?

Read-only. This is the half of post-ingest verification that SQL cannot do:
verify_ranking_year.sql can only report the universes the database *has*, and a
universe that failed to crawl leaves no row behind to report. The list of
universes that were meant to run lives in ``qs_universe_registry.py``, so the
comparison has to happen in Python.

    ./.venv/bin/python crawlernest/scripts/verify_ranking_year.py \
        --ranking-year 2026 --pg-password test

Exit codes
----------
0   every registered universe that can produce rows has them
1   at least one is missing, or the database holds a universe the registry
    does not know about
2   could not connect / psycopg2 missing

``enable_aggregation=False`` universes are expected to be absent -- QS Business
Master's is a family of five rankings with no id of its own -- so they are
listed under "disabled" rather than counted as failures.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_JOBS = Path(__file__).resolve().parents[1] / "crawlernest-jobs"
if _JOBS.is_dir() and str(_JOBS) not in sys.path:
    sys.path.insert(0, str(_JOBS))

from qs_universe_registry import iter_all_qs_universes  # noqa: E402


def connect(host: str, port: int, database: str, user: str, password: str):
    try:
        import psycopg2  # type: ignore
        return psycopg2.connect(host=host, port=port, database=database,
                                user=user, password=password)
    except ImportError:
        print("ERROR psycopg2 not installed - run: pip install psycopg2-binary")
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR cannot connect to PostgreSQL: {exc}")
        sys.exit(2)


def universes_in_warehouse(conn, source_code: str, ranking_year: int) -> dict[str, dict[str, Any]]:
    """One entry per universe present, keyed by ranking_type."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rr.ranking_type,
                   count(*),
                   count(DISTINCT rr.run_id),
                   max(rr.updated_at)
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs USING (ranking_source_id)
            WHERE rs.source_code = %s AND rr.ranking_year = %s
            GROUP BY 1
        """, (source_code, ranking_year))
        return {r[0]: {"rows": int(r[1]), "run_ids": int(r[2]),
                       "last_update": str(r[3])} for r in cur.fetchall()}


def unresolved_by_universe(conn, source_code: str, ranking_year: int) -> dict[str, int]:
    """Rows the crawler produced that entity resolution could not place.

    A universe that crawled but resolved nothing has no ranking_record rows and
    would otherwise look identical to one that never ran at all.

    Counted for the newest ingest of each universe only. The table is
    append-only and has no batch id, so ingesting a year twice logs its misses
    twice. ingest_records writes the ranking records before it logs the misses,
    so the newest ingest's misses are those logged at or after that universe's
    newest row -- no time window needed, and an ingest that resolved everything
    correctly reads as zero rather than inheriting the previous run's misses.
    """
    with conn.cursor() as cur:
        cur.execute("""
            WITH loaded AS (
                SELECT rr.ranking_type, max(rr.updated_at) AS ingested_at
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs USING (ranking_source_id)
                WHERE rs.source_code = %s AND rr.ranking_year = %s
                GROUP BY 1
            )
            SELECT m.ranking_type, count(*)
            FROM analytics.missing_entity_log m
            JOIN loaded l ON l.ranking_type = m.ranking_type
            WHERE m.source_code = %s AND m.ranking_year = %s
              AND m.created_at >= l.ingested_at
            GROUP BY 1
        """, (source_code, ranking_year, source_code, ranking_year))
        return {r[0]: int(r[1]) for r in cur.fetchall()}


def build_report(conn, source_code: str, ranking_year: int) -> dict[str, Any]:
    present = universes_in_warehouse(conn, source_code, ranking_year)
    unresolved = unresolved_by_universe(conn, source_code, ranking_year)

    expected: list[dict[str, Any]] = []
    disabled: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for spec in iter_all_qs_universes():
        entry = {
            "ranking_type": spec.ranking_type,
            "universe_type": spec.universe_type,
            "universe_key": spec.universe_key,
            "label": spec.label,
            "ranking_scope": spec.ranking_scope,
            "pinned_ranking_id": spec.ranking_id,
        }
        if not spec.enable_aggregation:
            disabled.append(entry)
            continue
        found = present.get(spec.ranking_type)
        entry["rows"] = found["rows"] if found else 0
        entry["run_ids"] = found["run_ids"] if found else 0
        entry["last_update"] = found["last_update"] if found else None
        entry["unresolved"] = unresolved.get(spec.ranking_type, 0)
        expected.append(entry)
        if not found:
            missing.append(entry)

    known = {spec.ranking_type for spec in iter_all_qs_universes()}
    unregistered = [
        {"ranking_type": rt, **stats}
        for rt, stats in sorted(present.items()) if rt not in known
    ]
    # A universe whose rows all come from one run is the normal shape; two run
    # ids mean an older ingest was only partly overwritten.
    multi_run = [
        {"ranking_type": e["ranking_type"], "run_ids": e["run_ids"]}
        for e in expected if e["run_ids"] > 1
    ]

    return {
        "source_code": source_code,
        "ranking_year": ranking_year,
        "registered": len(expected) + len(disabled),
        "expected_to_load": len(expected),
        "loaded": len(expected) - len(missing),
        "universes": expected,
        "missing": missing,
        "disabled": disabled,
        "unregistered_in_database": unregistered,
        "universes_with_multiple_runs": multi_run,
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"QS universe coverage - {report['source_code']} {report['ranking_year']}")
    print(f"  registered in qs_universe_registry : {report['registered']}")
    print(f"  expected to produce rows           : {report['expected_to_load']}")
    print(f"  present in warehouse               : {report['loaded']}")
    print()

    width = max((len(u["ranking_type"]) for u in report["universes"]), default=10)
    for u in sorted(report["universes"], key=lambda x: x["ranking_type"]):
        mark = "ok  " if u["rows"] else "MISS"
        print(f"  {mark} {u['ranking_type']:<{width}}  rows={u['rows']:>5}"
              f"  unresolved={u['unresolved']:>5}  last={u['last_update'] or '-'}")

    if report["disabled"]:
        print("\n  disabled in the registry (absence is expected):")
        for u in report["disabled"]:
            print(f"    - {u['ranking_type']}: {u['label']}")

    if report["missing"]:
        print("\n  MISSING - registered, aggregation enabled, no rows:")
        for u in report["missing"]:
            hint = ""
            if u["unresolved"]:
                hint = (f" (crawled: {u['unresolved']} rows reached entity"
                        " resolution and none matched)")
            elif u["pinned_ranking_id"]:
                hint = f" (pinned ranking_id {u['pinned_ranking_id']}; nothing to re-resolve it from)"
            print(f"    - {u['ranking_type']}: {u['label']}{hint}")

    if report["unregistered_in_database"]:
        print("\n  UNREGISTERED - rows present for a universe the registry does not list:")
        for u in report["unregistered_in_database"]:
            print(f"    - {u['ranking_type']}: rows={u['rows']}")

    if report["universes_with_multiple_runs"]:
        print("\n  MIXED RUNS - rows from more than one ingest of the same year:")
        for u in report["universes_with_multiple_runs"]:
            print(f"    - {u['ranking_type']}: {u['run_ids']} run ids")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the QS universe registry against what a year actually loaded")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--source-code", default="QS")
    parser.add_argument("--ranking-year", type=int, default=2026)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    conn = connect(args.pg_host, args.pg_port, args.pg_database,
                   args.pg_user, args.pg_password)
    try:
        report = build_report(conn, args.source_code, args.ranking_year)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)

    if report["missing"] or report["unregistered_in_database"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
