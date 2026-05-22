#!/usr/bin/env python3
"""Readonly source freshness inspection for maintenance mode."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_SNAPSHOT = REPO_ROOT / "snapshots" / "latest_status.json"
DEFAULT_SUMMARY = REPO_ROOT / "reports" / "maintenance_readiness_summary.md"
EXPECTED_SOURCES = ("QS", "THE", "ARWU")
STALE_HOURS = 36.0
CRITICAL_HOURS = 168.0


def parse_dt(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def age_hours(value: Any, now: dt.datetime) -> float | None:
    parsed = parse_dt(value)
    if not parsed:
        return None
    return round((now - parsed).total_seconds() / 3600, 2)


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def source_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    raw = snapshot.get("source_counts")
    if raw is None:
        raw = snapshot.get("health", {}).get("sources", [])
    if isinstance(raw, dict):
        return {str(k): as_int(v) for k, v in raw.items()}
    result: dict[str, int] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            source = item.get("source_code") or item.get("source")
            if source:
                result[str(source)] = as_int(
                    item.get("count", item.get("record_count", item.get("records_in", 0)))
                )
    return result


def load_snapshot(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {}, [f"snapshot not found: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"malformed snapshot: {path} ({exc})"]
    if not isinstance(payload, dict):
        return {}, [f"malformed snapshot: {path} (root is not an object)"]
    return payload, warnings


def classify_source(source: str, count: int, agg_age: float | None) -> tuple[str, str]:
    if count <= 0:
        return "unavailable", "missing expected source"
    if agg_age is None:
        return "degraded", "aggregation age unknown"
    if agg_age >= CRITICAL_HOURS:
        return "stale", f"aggregation age {agg_age:.2f}h"
    if agg_age >= STALE_HOURS:
        return "degraded", f"aggregation age {agg_age:.2f}h"
    return "healthy", f"count={count}"


def inspect(snapshot: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    now = dt.datetime.now(tz=dt.timezone.utc)
    counts = source_counts(snapshot)
    aggregation_at = (
        snapshot.get("last_aggregation_at")
        or snapshot.get("freshness", {}).get("aggregation", {}).get("latest_at")
    )
    agg_age = (
        snapshot.get("latest_aggregation_age_hours")
        or snapshot.get("freshness", {}).get("aggregation", {}).get("age_hours")
        or age_hours(aggregation_at, now)
    )
    if isinstance(agg_age, str):
        try:
            agg_age = float(agg_age)
        except ValueError:
            agg_age = None

    missing_sources = [source for source in EXPECTED_SOURCES if counts.get(source, 0) == 0]
    source_states = []
    for source in EXPECTED_SOURCES:
        state, reason = classify_source(source, counts.get(source, 0), agg_age)
        source_states.append(
            {
                "source": source,
                "count": counts.get(source, 0),
                "state": state,
                "reason": reason,
            }
        )

    subject_rows = snapshot.get("freshness", {}).get("subject_rankings", [])
    if not isinstance(subject_rows, list):
        subject_rows = []
    subject_summary = {
        "latest_subject_year": snapshot.get("health", {}).get("latest_subject_year"),
        "subject_rankings_count": as_int(snapshot.get("health", {}).get("subject_rankings_count")),
        "rows": subject_rows,
    }

    freshness_state = "healthy"
    if not snapshot:
        freshness_state = "critical"
    elif agg_age is None or agg_age >= CRITICAL_HOURS or len(missing_sources) >= 2:
        freshness_state = "critical"
    elif agg_age >= STALE_HOURS:
        freshness_state = "stale"
    elif missing_sources:
        freshness_state = "degraded"

    return {
        "generated_at": now.isoformat(),
        "snapshot_timestamp": snapshot.get("snapshot_timestamp"),
        "snapshot_file": snapshot.get("snapshot_file"),
        "freshness_state": freshness_state,
        "aggregation": {
            "latest_at": aggregation_at,
            "age_hours": agg_age,
            "status": snapshot.get("last_aggregation_status")
            or snapshot.get("freshness", {}).get("aggregation", {}).get("status"),
            "aggregated_count": as_int(
                snapshot.get("aggregated_count", snapshot.get("health", {}).get("aggregated_rankings_count"))
            ),
        },
        "source_coverage": {
            "counts": counts,
            "missing_sources": missing_sources,
            "states": source_states,
        },
        "unresolved": {
            "total": as_int(snapshot.get("unresolved_total", snapshot.get("unresolved", {}).get("total"))),
            "last_7d": as_int(snapshot.get("unresolved_last_7d", snapshot.get("unresolved", {}).get("last_7d"))),
            "trend_pct": snapshot.get("unresolved_trend_pct", snapshot.get("unresolved", {}).get("trend_pct")),
        },
        "subject_freshness": subject_summary,
        "warnings": warnings,
    }


def markdown(report: dict[str, Any], maintenance: bool = False) -> str:
    title = "Maintenance Readiness Summary" if maintenance else "Source Freshness Inspection"
    lines = [
        f"# {title}",
        "",
        f"Generated: {report['generated_at']}",
        f"Snapshot: `{report.get('snapshot_timestamp') or '[missing]'}`",
        f"Freshness state: **{report['freshness_state']}**",
        "",
        "## Aggregation",
        "",
        f"- Aggregated count: {report['aggregation']['aggregated_count']}",
        f"- Latest aggregation: {report['aggregation']['latest_at']}",
        f"- Latest aggregation age hours: {report['aggregation']['age_hours']}",
        f"- Latest aggregation status: {report['aggregation']['status']}",
        "",
        "## Source Coverage",
        "",
        "| Source | Count | State | Reason |",
        "| --- | ---: | --- | --- |",
    ]
    for item in report["source_coverage"]["states"]:
        lines.append(
            f"| {item['source']} | {item['count']} | {item['state']} | {item['reason']} |"
        )
    lines.extend([
        "",
        "## Unresolved Trend",
        "",
        f"- Total unresolved: {report['unresolved']['total']}",
        f"- Last 7 days: {report['unresolved']['last_7d']}",
        f"- Trend pct: {report['unresolved']['trend_pct']}",
        "",
        "## Subject Freshness",
        "",
        f"- Latest subject year: {report['subject_freshness']['latest_subject_year']}",
        f"- Subject ranking rows: {report['subject_freshness']['subject_rankings_count']}",
    ])
    if maintenance:
        blockers = []
        if report["freshness_state"] in ("critical", "stale"):
            blockers.append(f"freshness state is {report['freshness_state']}")
        missing = report["source_coverage"]["missing_sources"]
        stale_sources = [
            item["source"]
            for item in report["source_coverage"]["states"]
            if item.get("state") == "stale"
        ]
        if missing:
            blockers.append("missing sources: " + ", ".join(missing))
        source_count = len(report["source_coverage"]["counts"])
        expected_count = len(EXPECTED_SOURCES)
        completeness = "high" if not missing else ("medium" if source_count >= expected_count - 1 else "low")
        freshness_confidence = "low" if report["freshness_state"] == "critical" else (
            "medium" if report["freshness_state"] in ("stale", "degraded") else "high"
        )
        operational_confidence = "limited" if blockers else "moderate"
        caveat_presence = "required" if blockers else "recommended"
        lines.extend([
            "",
            "## Maintenance Readiness",
            "",
            f"- Drift state: see `reports/drift_timeline.md`",
            f"- Known stale sources: {', '.join(stale_sources) if stale_sources else '[none]'}",
            f"- Known unavailable sources: {', '.join(missing) if missing else '[none]'}",
            f"- Known blockers: {', '.join(blockers) if blockers else '[none]'}",
            f"- Release/demo readiness: {'needs caveats' if blockers else 'ready for scoped demo'}",
            f"- Operational confidence level: {operational_confidence}",
            f"- Demo caveat presence: {caveat_presence}",
            f"- Freshness confidence: {freshness_confidence}",
            f"- Source completeness confidence: {completeness}",
        ])
    if report.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    lines.extend([
        "",
        "## Readonly Boundary",
        "",
        "This inspection reads snapshot JSON only. It does not rerun ingestion, mutate pipeline state, auto-repair source fetches, change scoring, or substitute fallback ranking data.",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect source freshness from snapshot evidence")
    parser.add_argument("--snapshot-file", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument(
        "--summary-output",
        default=None,
        help="Optional path for maintenance readiness Markdown output.",
    )
    args = parser.parse_args()

    snapshot, warnings = load_snapshot(Path(args.snapshot_file))
    report = inspect(snapshot, warnings)
    if args.summary_output:
        output = Path(args.summary_output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown(report, maintenance=True), encoding="utf-8")
        print(f"[source-freshness] maintenance summary written: {output}")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
