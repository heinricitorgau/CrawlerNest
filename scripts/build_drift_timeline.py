#!/usr/bin/env python3
"""Classify historical drift signals from readonly CrawlerNest snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from build_snapshot_timeline import load_snapshot_records

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
REPORTS_DIR = REPO_ROOT / "reports"

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def event(severity: str, kind: str, message: str, timestamp: str) -> dict[str, str]:
    return {
        "severity": severity,
        "kind": kind,
        "message": message,
        "snapshot_timestamp": timestamp,
    }


def classify_pair(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    ts = str(after.get("snapshot_timestamp", "unknown"))

    unresolved_delta = int(after.get("unresolved_total", 0)) - int(
        before.get("unresolved_total", 0)
    )
    if unresolved_delta > 0:
        base = max(int(before.get("unresolved_total", 0)), 1)
        ratio = unresolved_delta / base
        severity = "critical" if unresolved_delta >= 25 or ratio >= 0.5 else "warning"
        events.append(
            event(
                severity,
                "unresolved_increase",
                f"unresolved total increased by {unresolved_delta}",
                ts,
            )
        )
    elif unresolved_delta < 0:
        events.append(
            event("info", "unresolved_decrease", f"unresolved total decreased by {abs(unresolved_delta)}", ts)
        )

    before_sources = before.get("source_counts", {})
    after_sources = after.get("source_counts", {})
    for source in sorted(set(before_sources) | set(after_sources)):
        before_count = int(before_sources.get(source, 0))
        after_count = int(after_sources.get(source, 0))
        if before_count > 0 and after_count == 0:
            events.append(
                event("critical", "source_disappearance", f"{source} disappeared from source coverage", ts)
            )
        elif before_count == 0 and after_count > 0:
            events.append(event("info", "source_appearance", f"{source} appeared in source coverage", ts))

    if not before.get("overall_stale") and after.get("overall_stale"):
        events.append(event("warning", "stale_transition", "snapshot state changed from fresh to stale", ts))
    elif before.get("overall_stale") and not after.get("overall_stale"):
        events.append(event("info", "fresh_transition", "snapshot state changed from stale to fresh", ts))

    before_count = int(before.get("aggregated_count", 0))
    after_count = int(after.get("aggregated_count", 0))
    if before_count > 0 and after_count == 0:
        events.append(event("critical", "aggregated_count_collapse", "aggregated count collapsed to zero", ts))
    elif before_count > 0 and after_count < before_count:
        drop_ratio = (before_count - after_count) / before_count
        if drop_ratio >= 0.5:
            severity = "critical"
        elif drop_ratio >= 0.1:
            severity = "warning"
        else:
            severity = "info"
        events.append(
            event(
                severity,
                "aggregated_count_drop",
                f"aggregated count dropped by {before_count - after_count} ({drop_ratio:.1%})",
                ts,
            )
        )

    drift_delta = int(after.get("drift_warning_count", 0)) - int(
        before.get("drift_warning_count", 0)
    )
    if drift_delta > 0:
        severity = "critical" if after.get("drift_warning_count", 0) >= 5 else "warning"
        events.append(
            event(severity, "drift_warning_increase", f"drift warnings increased by {drift_delta}", ts)
        )
    elif int(after.get("drift_warning_count", 0)) > 0:
        events.append(
            event("warning", "drift_warning_present", "drift warnings remain present", ts)
        )

    return events


def overall_severity(events: list[dict[str, str]]) -> str:
    if not events:
        return "info"
    return max(events, key=lambda item: SEVERITY_ORDER[item["severity"]])["severity"]


def build_markdown(records: list[dict[str, Any]], warnings: list[str]) -> str:
    generated_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    all_events: list[dict[str, str]] = []
    for before, after in zip(records, records[1:]):
        all_events.extend(classify_pair(before, after))

    lines = [
        "# Drift Timeline",
        "",
        f"Generated: {generated_at}",
        f"Snapshots analyzed: {len(records)}",
        f"Overall severity: {overall_severity(all_events)}",
        "",
    ]
    if warnings:
        lines.extend(["## Snapshot Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend([
        "## Classification Rules",
        "",
        "- `info`: expected movement, recovery, or small count movement.",
        "- `warning`: unresolved growth, stale transition, source drift, or moderate aggregation drop.",
        "- `critical`: source disappearance, aggregation collapse, large unresolved growth, or major count drop.",
        "",
        "## Events",
        "",
    ])
    if not all_events:
        lines.append("No drift events detected across available snapshots.")
    else:
        lines.extend(["| Severity | Kind | Snapshot | Detail |", "| --- | --- | --- | --- |"])
        for item in all_events:
            lines.append(
                f"| {item['severity']} | `{item['kind']}` | "
                f"`{item['snapshot_timestamp']}` | {item['message']} |"
            )

    lines.extend(["", "## Latest Snapshot Drift Warnings", ""])
    if records:
        latest = records[-1]
        warnings_count = latest.get("drift_warning_count", 0)
        lines.append(f"- Latest snapshot: `{latest.get('snapshot_timestamp')}`")
        lines.append(f"- Drift warning count: {warnings_count}")
    else:
        lines.append("No snapshots available.")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build drift timeline report")
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR))
    parser.add_argument("--output", default=str(REPORTS_DIR / "drift_timeline.md"))
    args = parser.parse_args()

    records, warnings = load_snapshot_records(Path(args.snapshot_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(records, warnings), encoding="utf-8")
    print(f"[drift-timeline] written: {output}")
    if warnings:
        print(f"[drift-timeline] warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
