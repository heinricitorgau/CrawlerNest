#!/usr/bin/env python3
"""Build a demo-friendly readonly operational summary."""

from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path
from typing import Any

from build_freshness_escalation import EXPECTED_SOURCES, classify as classify_freshness
from build_snapshot_timeline import load_snapshot_records

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
REPORTS_DIR = REPO_ROOT / "reports"
VALIDATION_DOC = REPO_ROOT / "docs" / "RC1_VALIDATION_RESULTS.md"


def validation_summary() -> str:
    if not VALIDATION_DOC.exists():
        return "Validation doc not found."
    text = VALIDATION_DOC.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"\| `([^`]+)` \| ([^|]+) \| ([^|]+) \|", text)
    if not matches:
        return "Validation doc exists; no pass/fail table parsed."
    parts = [f"`{name}`: {result.strip()}" for name, result, _ in matches[:6]]
    return "; ".join(parts)


def source_health(record: dict[str, Any]) -> list[tuple[str, str, str]]:
    counts = {str(k): int(v or 0) for k, v in record.get("source_counts", {}).items()}
    freshness = record.get("freshness", {})
    global_rows = freshness.get("global_rankings", []) if isinstance(freshness, dict) else []
    by_source = {
        str(item.get("source_code")): item
        for item in global_rows
        if isinstance(item, dict) and item.get("source_code")
    }
    rows: list[tuple[str, str, str]] = []
    for source in EXPECTED_SOURCES:
        count = counts.get(source, 0)
        info = by_source.get(source, {})
        age = info.get("age_hours")
        if count == 0:
            rows.append((source, "unavailable", "missing expected source"))
        elif info.get("missing"):
            rows.append((source, "unavailable", "freshness row is marked missing"))
        elif isinstance(age, (int, float)) and age >= 168:
            rows.append((source, "stale", f"age={age:.1f}h"))
        elif isinstance(age, (int, float)) and age >= 36:
            rows.append((source, "degraded", f"age={age:.1f}h"))
        else:
            rows.append((source, "healthy", f"count={count}"))
    for source, count in sorted(counts.items()):
        if source not in EXPECTED_SOURCES:
            rows.append((source, "partial", f"observed non-baseline source count={count}"))
    return rows


def first_heading(path: Path) -> str:
    if not path.exists():
        return "not generated"
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("Overall severity:") or line.startswith("Escalation state:"):
            return line
    return "generated"


def build_markdown(records: list[dict[str, Any]], warnings: list[str]) -> str:
    generated_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    latest = records[-1] if records else {}
    freshness_state, freshness_reasons = classify_freshness(latest, EXPECTED_SOURCES) if latest else (
        "critical",
        ["no snapshots available"],
    )
    drift_report = first_heading(REPORTS_DIR / "drift_timeline.md")
    freshness_report = first_heading(REPORTS_DIR / "freshness_escalation.md")

    lines = [
        "# Operational Summary",
        "",
        f"Generated: {generated_at}",
        f"Latest snapshot timestamp: `{latest.get('snapshot_timestamp', '[missing]')}`",
        "",
        "## Release / Demo Readiness",
        "",
        f"- Freshness state: **{freshness_state}**",
        f"- Aggregated count: {latest.get('aggregated_count', 0)}",
        f"- Unresolved total: {latest.get('unresolved_total', 0)}",
        f"- Drift warning count: {latest.get('drift_warning_count', 0)}",
        f"- Latest validation: {validation_summary()}",
        f"- Latest drift report: {drift_report}",
        f"- Latest freshness report: {freshness_report}",
        "",
        "## Freshness Reasons",
        "",
    ]
    for reason in freshness_reasons:
        lines.append(f"- {reason}")

    lines.extend(["", "## Source Health Summary", "", "| Source | State | Signal |", "| --- | --- | --- |"])
    for source, state, signal in source_health(latest) if latest else []:
        lines.append(f"| {source} | {state} | {signal} |")
    if not latest:
        lines.append("| [none] | critical | no snapshots available |")

    lines.extend([
        "",
        "## Readonly Boundary",
        "",
        "This report only reads snapshot files, generated reports, and validation documentation. "
        "It does not rerun the pipeline, retry sources, mutate runtime state, change scoring, "
        "or write application data.",
    ])
    if warnings:
        lines.extend(["", "## Snapshot Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operational summary report")
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR))
    parser.add_argument("--output", default=str(REPORTS_DIR / "operational_summary.md"))
    args = parser.parse_args()

    records, warnings = load_snapshot_records(Path(args.snapshot_dir))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(records, warnings), encoding="utf-8")
    print(f"[operational-summary] written: {output}")
    if warnings:
        print(f"[operational-summary] warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
