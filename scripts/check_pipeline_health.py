#!/usr/bin/env python3
"""Readonly CrawlerNest pipeline health diagnostics."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any


EXPECTED_SOURCES = ("QS", "THE", "ARWU")
STALE_AFTER_HOURS = 36
MIN_AGGREGATED_ROWS = 100
MAX_UNRESOLVED_RATIO = 0.05


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def connect() -> Any:
    import psycopg2  # type: ignore[import-not-found]

    return psycopg2.connect(
        host=os.getenv("CRAWLERNEST_PG_HOST", "127.0.0.1"),
        port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
        dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
        user=os.getenv("CRAWLERNEST_PG_USER", "test"),
        password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        connect_timeout=3,
    )


def scalar(cur: Any, sql: str, default: Any = None) -> Any:
    try:
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] if row else default
    except Exception as exc:  # readonly diagnostics should degrade, not crash
        return {"error": str(exc)}


def rows(cur: Any, sql: str) -> list[tuple[Any, ...]]:
    try:
        cur.execute(sql)
        return list(cur.fetchall())
    except Exception:
        return []


def as_int(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def table_error(value: Any) -> str | None:
    return value.get("error") if isinstance(value, dict) else None


def classify(metrics: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if metrics.get("connection_error"):
        return "failed", [metrics["connection_error"]]

    aggregated_count = as_int(metrics.get("aggregated_rankings_count"))
    ranking_count = as_int(metrics.get("ranking_record_count"))
    unresolved_count = as_int(metrics.get("unresolved_count"))
    latest_aggregation = metrics.get("latest_aggregation_finished_at")
    missing_sources = metrics.get("missing_sources", [])
    duplicate_saves = as_int(metrics.get("duplicate_resolution_count"))

    for key in (
        "aggregated_rankings_count",
        "ranking_record_count",
        "unresolved_count",
        "latest_aggregation_finished_at",
        "latest_subject_year",
    ):
        err = table_error(metrics.get(key))
        if err:
            reasons.append(f"{key}: {err}")

    if reasons:
        return "failed", reasons

    if aggregated_count == 0:
        reasons.append("aggregated rankings are empty")
    if ranking_count == 0:
        reasons.append("ranking_record is empty")
    if not latest_aggregation:
        reasons.append("no finished aggregation timestamp")

    if reasons:
        return "failed", reasons

    stale = bool(metrics.get("stale"))
    unresolved_ratio = unresolved_count / ranking_count if ranking_count else 0.0

    if stale:
        reasons.append(f"latest aggregation is older than {STALE_AFTER_HOURS} hours")
    if aggregated_count < MIN_AGGREGATED_ROWS:
        reasons.append(f"aggregated rankings below threshold {MIN_AGGREGATED_ROWS}")
    if unresolved_ratio > MAX_UNRESOLVED_RATIO:
        reasons.append(
            f"unresolved ratio {unresolved_ratio:.2%} exceeds {MAX_UNRESOLVED_RATIO:.2%}"
        )
    if missing_sources:
        reasons.append(f"missing expected sources: {', '.join(missing_sources)}")
    if duplicate_saves > 0:
        reasons.append(f"duplicate resolution saves observed: {duplicate_saves}")

    if stale:
        return "stale", reasons
    if reasons:
        return "degraded", reasons
    return "healthy", ["all readonly health checks are within thresholds"]


def collect_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "checked_at": utc_now().isoformat(),
        "thresholds": {
            "stale_after_hours": STALE_AFTER_HOURS,
            "min_aggregated_rows": MIN_AGGREGATED_ROWS,
            "max_unresolved_ratio": MAX_UNRESOLVED_RATIO,
            "expected_sources": list(EXPECTED_SOURCES),
        },
    }

    try:
        conn = connect()
    except Exception as exc:
        metrics["connection_error"] = str(exc)
        metrics["status"], metrics["reasons"] = classify(metrics)
        return metrics

    with conn:
        with conn.cursor() as cur:
            metrics["aggregated_rankings_count"] = scalar(
                cur, "SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest", 0
            )
            metrics["ranking_record_count"] = scalar(
                cur, "SELECT COUNT(*) FROM warehouse.ranking_record", 0
            )
            metrics["unresolved_count"] = scalar(
                cur, "SELECT COUNT(*) FROM analytics.missing_entity_log", 0
            )
            metrics["duplicate_resolution_count"] = scalar(
                cur,
                """
                SELECT COALESCE(SUM(duplicate_resolution_saves), 0)::int
                FROM analytics.merge_diagnostics
                """,
                0,
            )
            metrics["latest_aggregation_finished_at"] = scalar(
                cur,
                """
                SELECT MAX(finished_at)
                FROM analytics.aggregation_runs
                WHERE status = 'finished'
                """,
            )
            metrics["latest_subject_year"] = scalar(
                cur,
                "SELECT MAX(ranking_year) FROM warehouse.subject_ranking_record",
            )

            coverage_rows = rows(
                cur,
                """
                SELECT rs.source_code, COUNT(rr.ranking_record_id)::int
                FROM warehouse.ranking_source rs
                LEFT JOIN warehouse.ranking_record rr
                  ON rr.ranking_source_id = rs.ranking_source_id
                GROUP BY rs.source_code
                ORDER BY rs.source_code
                """,
            )
            source_coverage = {str(source): int(count or 0) for source, count in coverage_rows}
            metrics["source_coverage"] = source_coverage
            metrics["missing_sources"] = [
                source for source in EXPECTED_SOURCES if source_coverage.get(source, 0) == 0
            ]

    latest = metrics.get("latest_aggregation_finished_at")
    if isinstance(latest, datetime):
        latest_utc = latest.astimezone(timezone.utc)
        age_hours = (utc_now() - latest_utc).total_seconds() / 3600
        metrics["latest_aggregation_age_hours"] = round(age_hours, 2)
        metrics["stale"] = age_hours > STALE_AFTER_HOURS
    else:
        metrics["latest_aggregation_age_hours"] = None
        metrics["stale"] = True

    metrics["status"], metrics["reasons"] = classify(metrics)
    return metrics


def print_summary(metrics: dict[str, Any]) -> None:
    print("CrawlerNest Pipeline Health")
    print(f"Status: {metrics.get('status', 'unknown').upper()}")
    print(f"Checked at: {metrics.get('checked_at')}")
    print("")

    for key in (
        "aggregated_rankings_count",
        "ranking_record_count",
        "unresolved_count",
        "duplicate_resolution_count",
        "latest_aggregation_finished_at",
        "latest_aggregation_age_hours",
        "latest_subject_year",
    ):
        print(f"{key}: {json_default(metrics.get(key))}")

    print(f"source_coverage: {metrics.get('source_coverage', {})}")
    print(f"missing_sources: {metrics.get('missing_sources', [])}")
    print("")
    print("Reasons:")
    for reason in metrics.get("reasons", []):
        print(f"- {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Readonly pipeline health diagnostics")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero unless healthy")
    args = parser.parse_args()

    metrics = collect_metrics()

    if args.json:
        print(json.dumps(metrics, indent=2, default=json_default))
    else:
        print_summary(metrics)
        print("")
        print(json.dumps(metrics, indent=2, default=json_default))

    if args.strict and metrics.get("status") != "healthy":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
