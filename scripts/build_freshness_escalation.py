#!/usr/bin/env python3
"""Build a readonly freshness escalation summary from the latest snapshot."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from build_snapshot_timeline import load_snapshot_records

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
REPORTS_DIR = REPO_ROOT / "reports"
EXPECTED_SOURCES = ("QS", "THE", "ARWU")


def source_counts(record: dict[str, Any]) -> dict[str, int]:
    return {str(k): int(v or 0) for k, v in record.get("source_counts", {}).items()}


def max_subject_age(record: dict[str, Any]) -> float | None:
    freshness = record.get("freshness", {})
    subject_rankings = freshness.get("subject_rankings", []) if isinstance(freshness, dict) else []
    ages = [
        float(item["age_hours"])
        for item in subject_rankings
        if isinstance(item, dict) and isinstance(item.get("age_hours"), (int, float))
    ]
    return max(ages) if ages else None


def classify(record: dict[str, Any], expected_sources: tuple[str, ...]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    counts = source_counts(record)
    missing_sources = [source for source in expected_sources if counts.get(source, 0) == 0]
    agg_count = int(record.get("aggregated_count", 0))
    agg_age = record.get("latest_aggregation_age_hours")
    subject_age = max_subject_age(record)

    if agg_count == 0:
        reasons.append("aggregated rankings are empty")
    if agg_age is None:
        reasons.append("latest aggregation age is unknown")
    elif agg_age >= 168:
        reasons.append(f"latest aggregation age is critical ({agg_age:.1f}h)")
    elif agg_age >= 36:
        reasons.append(f"latest aggregation is stale ({agg_age:.1f}h)")
    if missing_sources:
        reasons.append(f"expected source gaps: {', '.join(missing_sources)}")
    if subject_age is not None and subject_age >= 168:
        reasons.append(f"latest subject ranking age is critical ({subject_age:.1f}h)")
    elif subject_age is not None and subject_age >= 36:
        reasons.append(f"latest subject ranking is stale ({subject_age:.1f}h)")

    if agg_count == 0 or agg_age is None or (isinstance(agg_age, (int, float)) and agg_age >= 168):
        return "critical", reasons
    if len(missing_sources) >= 2:
        return "critical", reasons
    if record.get("overall_stale") or (isinstance(agg_age, (int, float)) and agg_age >= 36):
        return "stale", reasons
    if missing_sources or subject_age is None:
        return "degraded", reasons or ["source or subject coverage is incomplete"]
    return "healthy", ["freshness signals are within RC-1 thresholds"]


def build_markdown(records: list[dict[str, Any]], warnings: list[str], expected_sources: tuple[str, ...]) -> str:
    generated_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    latest = records[-1] if records else {}
    state, reasons = classify(latest, expected_sources) if latest else (
        "critical",
        ["no snapshots available"],
    )
    counts = source_counts(latest) if latest else {}
    missing_sources = [source for source in expected_sources if counts.get(source, 0) == 0]

    lines = [
        "# Freshness Escalation Summary",
        "",
        f"Generated: {generated_at}",
        f"Latest snapshot: `{latest.get('snapshot_timestamp', '[missing]')}`",
        f"Escalation state: **{state}**",
        "",
        "## Signals",
        "",
        f"- Aggregated count: {latest.get('aggregated_count', 0)}",
        f"- Latest aggregation age hours: {latest.get('latest_aggregation_age_hours')}",
        f"- Latest aggregation status: {latest.get('latest_aggregation_status')}",
        f"- Overall stale flag: {latest.get('overall_stale')}",
        f"- Expected source gaps: {', '.join(missing_sources) if missing_sources else '[none]'}",
        f"- Latest subject ranking age hours: {max_subject_age(latest)}",
        "",
        "## Escalation Reasons",
        "",
    ]
    for reason in reasons:
        lines.append(f"- {reason}")

    if warnings:
        lines.extend(["", "## Snapshot Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")

    lines.extend([
        "",
        "## Semantics",
        "",
        "- `healthy`: freshness and expected source signals are within normal bounds.",
        "- `degraded`: usable but incomplete source or subject coverage is present.",
        "- `stale`: data age crossed freshness thresholds, but the system can still serve cached data.",
        "- `critical`: aggregation is missing, very old, empty, or expected source gaps are severe.",
        "",
        "No pipeline rerun, source retry, selector repair, or remediation is performed by this report.",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build freshness escalation report")
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR))
    parser.add_argument("--output", default=str(REPORTS_DIR / "freshness_escalation.md"))
    parser.add_argument("--expected-sources", default=",".join(EXPECTED_SOURCES))
    args = parser.parse_args()

    expected_sources = tuple(
        source.strip() for source in args.expected_sources.split(",") if source.strip()
    )
    records, warnings = load_snapshot_records(Path(args.snapshot_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(records, warnings, expected_sources), encoding="utf-8")
    print(f"[freshness-escalation] written: {output}")
    if warnings:
        print(f"[freshness-escalation] warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
