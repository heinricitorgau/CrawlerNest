#!/usr/bin/env python3
"""Source drift detector — read-only.

Detects unexpected changes between consecutive ingestion runs:
  - Record count drop > threshold (default 20%)
  - Unresolved count spike
  - Score distribution shift in ranking_record
  - Country disappearance between the last two ingestion years

Outputs warnings only. Does not modify any data.

Usage
-----
  python run_source_drift.py [--pg-password test] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_SOURCES = ("QS", "THE", "ARWU")


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


def _rows(conn, sql: str, params=None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def detect_count_drops(conn, drop_threshold: float = 0.20) -> list[dict[str, Any]]:
    """Compare last two ingestion batches per source; flag if newer has <(1-threshold) records."""
    rows = _rows(conn, """
        SELECT source_code, records_in, unresolved_count, started_at, batch_id
        FROM analytics.source_ingestion_log
        ORDER BY source_code, started_at DESC
    """)

    by_source: dict[str, list[tuple]] = {}
    for r in rows:
        by_source.setdefault(r[0], []).append(r)

    warnings: list[dict[str, Any]] = []
    for src, entries in by_source.items():
        if len(entries) < 2:
            continue
        newer, older = entries[0], entries[1]
        new_count = int(newer[1] or 0)
        old_count = int(older[1] or 0)
        if old_count == 0:
            continue
        drop_ratio = (old_count - new_count) / old_count
        if drop_ratio > drop_threshold:
            warnings.append({
                "source_code": src,
                "warning_type": "count_drop",
                "message": (
                    f"records_in dropped from {old_count} to {new_count} "
                    f"({drop_ratio*100:.0f}% drop)"
                ),
                "previous_count": old_count,
                "current_count": new_count,
                "drop_pct": round(drop_ratio * 100, 1),
                "batch_id_newer": str(newer[4]) if newer[4] else None,
                "batch_id_older": str(older[4]) if older[4] else None,
            })

        # Check unresolved spike
        new_unresolved = int(newer[2] or 0)
        old_unresolved = int(older[2] or 0)
        if old_unresolved > 0 and new_unresolved > old_unresolved * 1.5:
            warnings.append({
                "source_code": src,
                "warning_type": "unresolved_spike",
                "message": (
                    f"unresolved_count increased from {old_unresolved} to {new_unresolved}"
                ),
                "previous_unresolved": old_unresolved,
                "current_unresolved": new_unresolved,
            })

    return warnings


def detect_rank_range_gaps(conn) -> list[dict[str, Any]]:
    """Check if any source lost more than half of its rank-range coverage vs prior year."""
    rows = _rows(conn, """
        SELECT rs.source_code, rr.ranking_year,
               COUNT(*) AS record_count,
               MIN(rr.rank_position) AS min_rank,
               MAX(rr.rank_position) AS max_rank
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
        WHERE rr.universe_type = 'global'
        GROUP BY rs.source_code, rr.ranking_year
        ORDER BY rs.source_code, rr.ranking_year DESC
    """)

    by_source: dict[str, list[tuple]] = {}
    for r in rows:
        by_source.setdefault(r[0], []).append(r)

    warnings: list[dict[str, Any]] = []
    for src, years in by_source.items():
        if len(years) < 2:
            continue
        new_year_row = years[0]
        old_year_row = years[1]
        new_max = int(new_year_row[4] or 0)
        old_max = int(old_year_row[4] or 0)
        if old_max > 0 and new_max < old_max * 0.5:
            warnings.append({
                "source_code": src,
                "warning_type": "rank_range_shrink",
                "message": (
                    f"max rank dropped from {old_max} ({old_year_row[1]}) "
                    f"to {new_max} ({new_year_row[1]})"
                ),
                "year_newer": int(new_year_row[1]),
                "year_older": int(old_year_row[1]),
                "max_rank_newer": new_max,
                "max_rank_older": old_max,
            })

    return warnings


def detect_score_distribution_shift(conn) -> list[dict[str, Any]]:
    """Compare avg score per source between the last two available years."""
    rows = _rows(conn, """
        SELECT rs.source_code, rr.ranking_year,
               AVG(rr.score) AS avg_score,
               STDDEV(rr.score) AS std_score,
               COUNT(*) AS count
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
        WHERE rr.score IS NOT NULL AND rr.universe_type = 'global'
        GROUP BY rs.source_code, rr.ranking_year
        ORDER BY rs.source_code, rr.ranking_year DESC
    """)

    by_source: dict[str, list[tuple]] = {}
    for r in rows:
        by_source.setdefault(r[0], []).append(r)

    warnings: list[dict[str, Any]] = []
    for src, years in by_source.items():
        if len(years) < 2:
            continue
        new_yr = years[0]
        old_yr = years[1]
        new_avg = float(new_yr[2] or 0)
        old_avg = float(old_yr[2] or 0)
        if old_avg > 0:
            shift_pct = abs(new_avg - old_avg) / old_avg
            if shift_pct > 0.30:
                warnings.append({
                    "source_code": src,
                    "warning_type": "score_distribution_shift",
                    "message": (
                        f"avg score changed from {old_avg:.1f} ({old_yr[1]}) "
                        f"to {new_avg:.1f} ({new_yr[1]}) — "
                        f"{shift_pct*100:.0f}% shift"
                    ),
                    "year_newer": int(new_yr[1]),
                    "year_older": int(old_yr[1]),
                    "avg_score_newer": round(new_avg, 2),
                    "avg_score_older": round(old_avg, 2),
                    "shift_pct": round(shift_pct * 100, 1),
                })

    return warnings


def detect_country_disappearance(conn) -> list[dict[str, Any]]:
    """Find countries present in prior year but absent in the newest year per source."""
    rows = _rows(conn, """
        SELECT rs.source_code, rr.ranking_year, c.country_name, COUNT(*) AS cnt
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = rr.canonical_university_id
        JOIN warehouse.countries c ON c.country_id = cu.country_id
        WHERE rr.universe_type = 'global'
        GROUP BY rs.source_code, rr.ranking_year, c.country_name
        ORDER BY rs.source_code, rr.ranking_year DESC
    """)

    by_source_year: dict[str, dict[int, set[str]]] = {}
    for r in rows:
        src, year, country = r[0], int(r[1]), r[2]
        by_source_year.setdefault(src, {}).setdefault(year, set()).add(country)

    warnings: list[dict[str, Any]] = []
    for src, year_map in by_source_year.items():
        sorted_years = sorted(year_map.keys(), reverse=True)
        if len(sorted_years) < 2:
            continue
        new_year, old_year = sorted_years[0], sorted_years[1]
        new_countries = year_map[new_year]
        old_countries = year_map[old_year]
        disappeared = sorted(old_countries - new_countries)
        if disappeared:
            warnings.append({
                "source_code": src,
                "warning_type": "country_disappearance",
                "message": (
                    f"{len(disappeared)} countr(ies) present in {old_year} "
                    f"but missing in {new_year}"
                ),
                "year_newer": new_year,
                "year_older": old_year,
                "disappeared_countries": disappeared[:10],
            })

    return warnings


def _source_counts_from_fixture(snapshot: dict[str, Any]) -> dict[str, int]:
    counts = snapshot.get("source_counts", {})
    if isinstance(counts, dict):
        return {str(k): int(v or 0) for k, v in counts.items()}
    if isinstance(counts, list):
        result: dict[str, int] = {}
        for item in counts:
            if isinstance(item, dict):
                source = item.get("source_code")
                if source:
                    result[str(source)] = int(item.get("count") or item.get("records_in") or 0)
        return result
    return {}


def detect_fixture_drift(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify no-database failure-state fixtures as drift warnings."""
    warnings: list[dict[str, Any]] = []

    for warning in snapshot.get("drift_warnings", []) or []:
        if isinstance(warning, dict):
            warnings.append(warning)

    existing = {
        (w.get("source_code"), w.get("warning_type"))
        for w in warnings
    }

    def add_once(warning: dict[str, Any]) -> None:
        key = (warning.get("source_code"), warning.get("warning_type"))
        if key not in existing:
            warnings.append(warning)
            existing.add(key)

    source_counts = _source_counts_from_fixture(snapshot)
    for source in snapshot.get("expected_sources", EXPECTED_SOURCES):
        if source_counts.get(source, 0) == 0:
            add_once({
                "source_code": source,
                "warning_type": "missing_source",
                "message": f"{source} has no records in fixture source coverage",
            })

    aggregated_count = int(snapshot.get("aggregated_count") or 0)
    if aggregated_count == 0:
        add_once({
            "source_code": "ALL",
            "warning_type": "empty_aggregation",
            "message": "aggregated_count is zero",
        })

    unresolved_total = int(snapshot.get("unresolved_total") or 0)
    unresolved_trend = snapshot.get("unresolved_trend_pct")
    if unresolved_total > 0 and unresolved_trend is not None and float(unresolved_trend) >= 50:
        add_once({
            "source_code": "ALL",
            "warning_type": "unresolved_spike",
            "message": f"unresolved_total={unresolved_total} trend={unresolved_trend}%",
            "current_unresolved": unresolved_total,
            "trend_pct": unresolved_trend,
        })

    if snapshot.get("overall_stale"):
        add_once({
            "source_code": "ALL",
            "warning_type": "stale_snapshot",
            "message": "snapshot is marked overall_stale=true",
        })

    return warnings


def load_fixture_snapshot(path: str) -> dict[str, Any]:
    fixture_path = Path(path)
    if not fixture_path.exists():
        print(f"ERROR fixture file not found: {fixture_path}")
        sys.exit(2)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print(f"ERROR source drift fixture must be a snapshot object: {fixture_path}")
        sys.exit(2)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Source drift detector")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--drop-threshold", type=float, default=0.20,
                        help="Flag count drops above this ratio (default 0.20 = 20%%)")
    parser.add_argument(
        "--fixture-file",
        metavar="PATH",
        help="Snapshot-style JSON fixture. Skips PostgreSQL connection entirely.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.fixture_file:
        snapshot = load_fixture_snapshot(args.fixture_file)
        fixture_warnings = detect_fixture_drift(snapshot)
        count_drops = [
            w for w in fixture_warnings
            if w.get("warning_type") in {"count_drop", "missing_source", "empty_aggregation"}
        ]
        rank_gaps: list[dict[str, Any]] = []
        score_shifts: list[dict[str, Any]] = []
        country_loss: list[dict[str, Any]] = []
        fixture_only = [
            w for w in fixture_warnings
            if w.get("warning_type") not in {"count_drop", "missing_source", "empty_aggregation"}
        ]
    else:
        conn = connect(args.pg_host, args.pg_port, args.pg_database,
                       args.pg_user, args.pg_password)
        try:
            count_drops = detect_count_drops(conn, args.drop_threshold)
            rank_gaps = detect_rank_range_gaps(conn)
            score_shifts = detect_score_distribution_shift(conn)
            country_loss = detect_country_disappearance(conn)
            fixture_only = []
        finally:
            conn.close()

    all_warnings = count_drops + rank_gaps + score_shifts + country_loss + fixture_only

    report = {
        "total_warnings": len(all_warnings),
        "count_drops": count_drops,
        "rank_range_gaps": rank_gaps,
        "score_distribution_shifts": score_shifts,
        "country_disappearances": country_loss,
        "fixture_warnings": fixture_only,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=== Source Drift Detection ===")
    if not all_warnings:
        print("No drift warnings detected.")
        return 0

    for w in all_warnings:
        print(f"[WARNING] {w['source_code']} — {w['warning_type']}: {w['message']}")

    print()
    print(f"Total warnings: {len(all_warnings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
