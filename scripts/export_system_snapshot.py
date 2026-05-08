#!/usr/bin/env python3
"""Export a full system snapshot to snapshots/system_snapshot_YYYYMMDD_HHMMSS.json.

Queries PostgreSQL directly — does not require Spring Boot to be running.

Usage
-----
  python scripts/export_system_snapshot.py [--pg-password test] [--pg-database clawer]
  python scripts/export_system_snapshot.py --output-dir /custom/path
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent


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


def _scalar(conn, sql: str, params=()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return row[0] if row else None


def _rows(conn, sql: str, params=()) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _one(conn, sql: str, params=()) -> tuple | None:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _serialize(v: Any) -> Any:
    if isinstance(v, datetime.datetime):
        return v.isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if hasattr(v, "__float__"):
        return float(v)
    return v


def serialize_row(row: tuple, cols: list[str]) -> dict[str, Any]:
    return {c: _serialize(row[i]) for i, c in enumerate(cols)}


# ── Section builders ──────────────────────────────────────────────────────────

def build_health(conn) -> dict[str, Any]:
    agg_count = _scalar(conn, "SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest") or 0
    subj_count = _scalar(conn, "SELECT COUNT(*) FROM warehouse.subject_ranking_record") or 0
    latest_year = _scalar(conn, "SELECT MAX(ranking_year) FROM analytics.v_aggregated_rankings_latest")
    latest_subj_year = _scalar(conn, "SELECT MAX(ranking_year) FROM warehouse.subject_ranking_record")

    src_rows = _rows(conn, """
        SELECT rs.source_code, rr.ranking_year, COUNT(*) AS cnt
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
        GROUP BY rs.source_code, rr.ranking_year
        ORDER BY rr.ranking_year DESC, rs.source_code
    """)
    sources = [{"source_code": r[0], "year": int(r[1]), "count": int(r[2])} for r in src_rows]

    return {
        "postgres_connected": True,
        "aggregated_rankings_count": int(agg_count),
        "subject_rankings_count": int(subj_count),
        "latest_ranking_year": int(latest_year) if latest_year else None,
        "latest_subject_year": int(latest_subj_year) if latest_subj_year else None,
        "sources": sources,
    }


def build_freshness(conn) -> dict[str, Any]:
    src_rows = _rows(conn, """
        SELECT rs.source_code,
               MAX(rr.ingested_at) AS latest_ingested_at,
               COUNT(*) AS record_count,
               MAX(rr.ranking_year) AS latest_year
        FROM warehouse.ranking_record rr
        JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
        GROUP BY rs.source_code
        ORDER BY rs.source_code
    """)
    global_rankings = []
    max_ingested = None
    STALE_HOURS = 30 * 24

    for r in src_rows:
        src_code, ingested_at, count, year = r[0], r[1], int(r[2]), r[3]
        age_hours: float | None = None
        stale = True
        if ingested_at:
            ingested_dt = ingested_at if ingested_at.tzinfo else ingested_at.replace(
                tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            age_hours = (now - ingested_dt).total_seconds() / 3600
            stale = age_hours > STALE_HOURS
            if max_ingested is None or ingested_dt > max_ingested:
                max_ingested = ingested_dt

        global_rankings.append({
            "source_code": src_code,
            "latest_ingested_at": ingested_at.isoformat() if ingested_at else None,
            "record_count": count,
            "latest_year": int(year) if year else None,
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "stale": stale,
            "missing": ingested_at is None,
        })

    # Subject freshness
    subj_rows = _rows(conn, """
        SELECT rs.subject_key, rs.display_name,
               MAX(srr.ingested_at) AS latest_ingested_at,
               COUNT(srr.subject_ranking_record_id) AS count,
               MAX(srr.ranking_year) AS latest_year
        FROM warehouse.ranking_subject rs
        LEFT JOIN warehouse.subject_ranking_record srr ON srr.subject_id = rs.subject_id
        WHERE rs.is_active = TRUE
        GROUP BY rs.subject_key, rs.display_name
        ORDER BY rs.display_name
    """)
    subject_rankings = []
    for r in subj_rows:
        subj_key, subj_name, ingested_at, count, year = r[0], r[1], r[2], int(r[3]), r[4]
        age_hours = None
        stale = True
        if ingested_at:
            ingested_dt = ingested_at if ingested_at.tzinfo else ingested_at.replace(
                tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            age_hours = round((now - ingested_dt).total_seconds() / 3600, 1)
            stale = age_hours > STALE_HOURS
        subject_rankings.append({
            "subject_key": subj_key,
            "subject_name": subj_name,
            "latest_ingested_at": ingested_at.isoformat() if ingested_at else None,
            "record_count": count,
            "latest_year": int(year) if year else None,
            "age_hours": age_hours,
            "stale": stale,
            "missing": ingested_at is None,
        })

    # Aggregation freshness
    agg_row = _one(conn, """
        SELECT aggregation_run_id, ranking_year, status, started_at, finished_at,
               output_record_count
        FROM analytics.aggregation_runs
        ORDER BY aggregation_run_id DESC
        LIMIT 1
    """)
    agg_section: dict[str, Any] = {}
    if agg_row:
        finished = agg_row[4] or agg_row[3]
        if finished:
            finished_dt = finished if finished.tzinfo else finished.replace(
                tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(tz=datetime.timezone.utc)
            agg_age = round((now - finished_dt).total_seconds() / 3600, 1)
            behind = bool(max_ingested and finished_dt < max_ingested)
        else:
            agg_age = None
            behind = False
        agg_section = {
            "latest_run_id": int(agg_row[0]),
            "ranking_year": int(agg_row[1]) if agg_row[1] else None,
            "status": agg_row[2],
            "latest_at": finished.isoformat() if finished else None,
            "age_hours": agg_age,
            "stale": agg_age is None or agg_age > STALE_HOURS,
            "behind_ingestion": behind,
            "output_count": int(agg_row[5]) if agg_row[5] else 0,
        }

    any_stale = any(s["stale"] for s in global_rankings)
    agg_stale_or_behind = agg_section.get("stale", True) or agg_section.get("behind_ingestion", False)

    return {
        "global_rankings": global_rankings,
        "subject_rankings": subject_rankings,
        "aggregation": agg_section,
        "overall_stale": any_stale or agg_stale_or_behind,
    }


def build_unresolved_trend(conn) -> dict[str, Any]:
    total = int(_scalar(conn, "SELECT COUNT(*) FROM analytics.missing_entity_log") or 0)
    last_7d = int(_scalar(conn, """
        SELECT COUNT(*) FROM analytics.missing_entity_log
        WHERE created_at >= NOW() - INTERVAL '7 days'
    """) or 0)
    prior_7d = int(_scalar(conn, """
        SELECT COUNT(*) FROM analytics.missing_entity_log
        WHERE created_at >= NOW() - INTERVAL '14 days'
          AND created_at < NOW() - INTERVAL '7 days'
    """) or 0)
    trend_pct = round((last_7d - prior_7d) / prior_7d * 100, 1) if prior_7d > 0 else None

    by_source = _rows(conn, """
        SELECT source_code, COUNT(*) AS cnt
        FROM analytics.missing_entity_log
        GROUP BY source_code
        ORDER BY cnt DESC
    """)

    return {
        "total": total,
        "last_7d": last_7d,
        "prior_7d": prior_7d,
        "trend_pct": trend_pct,
        "by_source": [{"source_code": r[0], "count": int(r[1])} for r in by_source],
    }


def build_regression_summary(conn) -> dict[str, Any]:
    agg_count = int(_scalar(conn, "SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest") or 0)
    stats_row = _one(conn, """
        SELECT MIN(composite_score), MAX(composite_score),
               ROUND(AVG(composite_score)::NUMERIC, 4)
        FROM analytics.v_aggregated_rankings_latest
        WHERE composite_score IS NOT NULL
    """)
    low_cov = int(_scalar(conn, """
        SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest WHERE coverage_ratio < 0.5
    """) or 0)
    score_min = float(stats_row[0]) if stats_row and stats_row[0] else None
    score_max = float(stats_row[1]) if stats_row and stats_row[1] else None
    score_avg = float(stats_row[2]) if stats_row and stats_row[2] else None
    return {
        "aggregated_count": agg_count,
        "score_min": score_min,
        "score_max": score_max,
        "score_avg": score_avg,
        "low_coverage_count": low_cov,
    }


def build_drift_warnings(conn) -> list[dict[str, Any]]:
    """Quick drift check: compare last two ingestion batches per source."""
    log_rows = _rows(conn, """
        SELECT source_code, records_in, unresolved_count, started_at
        FROM analytics.source_ingestion_log
        ORDER BY source_code, started_at DESC
    """)
    by_source: dict[str, list] = {}
    for r in log_rows:
        by_source.setdefault(r[0], []).append(r)

    warnings = []
    for src, batches in by_source.items():
        if len(batches) < 2:
            continue
        new_count = int(batches[0][1] or 0)
        old_count = int(batches[1][1] or 0)
        if old_count > 0:
            drop = (old_count - new_count) / old_count
            if drop > 0.20:
                warnings.append({
                    "source_code": src,
                    "warning_type": "count_drop",
                    "message": f"records_in dropped from {old_count} to {new_count} ({drop*100:.0f}%)",
                    "previous_count": old_count,
                    "current_count": new_count,
                })
            new_unres = int(batches[0][2] or 0)
            old_unres = int(batches[1][2] or 0)
            if old_unres > 0 and new_unres > old_unres * 1.5:
                warnings.append({
                    "source_code": src,
                    "warning_type": "unresolved_spike",
                    "message": f"unresolved_count increased from {old_unres} to {new_unres}",
                    "previous_unresolved": old_unres,
                    "current_unresolved": new_unres,
                })
    return warnings


def build_last_ingestion(conn) -> dict[str, Any] | None:
    row = _one(conn, """
        SELECT source_code, batch_id, started_at, finished_at, records_in,
               matched_count, unresolved_count, inserted_count
        FROM analytics.source_ingestion_log
        ORDER BY started_at DESC
        LIMIT 1
    """)
    if not row:
        return None
    return {
        "source_code": row[0],
        "batch_id": row[1],
        "started_at": row[2].isoformat() if row[2] else None,
        "finished_at": row[3].isoformat() if row[3] else None,
        "records_in": int(row[4]) if row[4] else 0,
        "matched_count": int(row[5]) if row[5] else 0,
        "unresolved_count": int(row[6]) if row[6] else 0,
        "inserted_count": int(row[7]) if row[7] else 0,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Export CrawlerNest system snapshot")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "snapshots"),
                        help="Directory for snapshot output")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = connect(args.pg_host, args.pg_port, args.pg_database,
                   args.pg_user, args.pg_password)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")

    print(f"[snapshot] collecting data at {now.isoformat()}...")
    try:
        health = build_health(conn)
        freshness = build_freshness(conn)
        unresolved_trend = build_unresolved_trend(conn)
        regression_summary = build_regression_summary(conn)
        drift_warnings = build_drift_warnings(conn)
        last_ingestion = build_last_ingestion(conn)
    finally:
        conn.close()

    snapshot: dict[str, Any] = {
        "snapshot_timestamp": now.isoformat(),
        "health": health,
        "freshness": freshness,
        "unresolved": unresolved_trend,
        "drift_warnings": drift_warnings,
        "regression_summary": regression_summary,
        "last_ingestion": last_ingestion,
    }

    # Full snapshot
    full_path = output_dir / f"system_snapshot_{ts}.json"
    full_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[snapshot] written: {full_path}")

    # Compact status for API route consumption
    agg = freshness.get("aggregation", {})
    status: dict[str, Any] = {
        "snapshot_timestamp": now.isoformat(),
        "snapshot_file": full_path.name,
        "aggregated_count": health["aggregated_rankings_count"],
        "source_counts": health["sources"],
        "unresolved_total": unresolved_trend["total"],
        "unresolved_last_7d": unresolved_trend["last_7d"],
        "unresolved_trend_pct": unresolved_trend["trend_pct"],
        "drift_warning_count": len(drift_warnings),
        "drift_warnings": drift_warnings,
        "regression_summary": regression_summary,
        "last_aggregation_run_id": agg.get("latest_run_id"),
        "last_aggregation_at": agg.get("latest_at"),
        "last_aggregation_status": agg.get("status"),
        "last_ingestion": last_ingestion,
        "overall_stale": freshness["overall_stale"],
    }
    latest_path = output_dir / "latest_status.json"
    latest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[snapshot] latest_status updated: {latest_path}")

    print(f"[snapshot] aggregated_count={health['aggregated_rankings_count']} "
          f"unresolved={unresolved_trend['total']} "
          f"drift_warnings={len(drift_warnings)} "
          f"overall_stale={freshness['overall_stale']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
