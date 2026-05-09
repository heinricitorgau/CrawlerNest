#!/usr/bin/env python3
"""Compare two CrawlerNest operational snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"snapshot not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"snapshot must be a JSON object: {path}")
    return payload


def number(snapshot: dict[str, Any], key: str) -> int | float | None:
    value = snapshot.get(key)
    return value if isinstance(value, (int, float)) else None


def source_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    counts = snapshot.get("source_counts", {})
    if isinstance(counts, dict):
        return {str(k): int(v or 0) for k, v in counts.items()}
    if isinstance(counts, list):
        result: dict[str, int] = {}
        for item in counts:
            if isinstance(item, dict) and item.get("source_code"):
                result[str(item["source_code"])] = int(
                    item.get("count") or item.get("records_in") or 0
                )
        return result
    return {}


def freshness_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    freshness = snapshot.get("freshness", {})
    if not isinstance(freshness, dict):
        freshness = {}
    return {
        "overall_stale": bool(snapshot.get("overall_stale", False)),
        "global_rankings": freshness.get("global_rankings", []),
        "subject_rankings": freshness.get("subject_rankings", []),
        "last_aggregation_at": snapshot.get("last_aggregation_at"),
        "last_aggregation_status": snapshot.get("last_aggregation_status"),
    }


def diff_number(before: dict[str, Any], after: dict[str, Any], key: str) -> dict[str, Any]:
    before_value = number(before, key)
    after_value = number(after, key)
    delta = None
    if before_value is not None and after_value is not None:
        delta = after_value - before_value
    return {"before": before_value, "after": after_value, "delta": delta}


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_sources = source_counts(before)
    after_sources = source_counts(after)
    all_sources = sorted(set(before_sources) | set(after_sources))
    coverage_diff = {
        source: {
            "before": before_sources.get(source, 0),
            "after": after_sources.get(source, 0),
            "delta": after_sources.get(source, 0) - before_sources.get(source, 0),
        }
        for source in all_sources
    }

    return {
        "before_snapshot_timestamp": before.get("snapshot_timestamp"),
        "after_snapshot_timestamp": after.get("snapshot_timestamp"),
        "aggregated_count": diff_number(before, after, "aggregated_count"),
        "unresolved_total": diff_number(before, after, "unresolved_total"),
        "source_coverage": coverage_diff,
        "stale_status": {
            "before": bool(before.get("overall_stale", False)),
            "after": bool(after.get("overall_stale", False)),
            "changed": (
                bool(before.get("overall_stale", False))
                != bool(after.get("overall_stale", False))
            ),
        },
        "drift_warning_count": diff_number(before, after, "drift_warning_count"),
        "freshness": {
            "before": freshness_state(before),
            "after": freshness_state(after),
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Snapshot Comparison",
        "",
        f"Before: `{report.get('before_snapshot_timestamp') or '[missing]'}`",
        f"After: `{report.get('after_snapshot_timestamp') or '[missing]'}`",
        "",
        "## Summary",
        "",
    ]

    for label, key in (
        ("Aggregated count", "aggregated_count"),
        ("Unresolved total", "unresolved_total"),
        ("Drift warnings", "drift_warning_count"),
    ):
        item = report[key]
        lines.append(
            f"- {label}: {item.get('before')} -> {item.get('after')} "
            f"(delta {item.get('delta')})"
        )

    stale = report["stale_status"]
    lines.append(
        f"- Stale status: {stale.get('before')} -> {stale.get('after')} "
        f"(changed={stale.get('changed')})"
    )

    lines.extend(["", "## Source Coverage", ""])
    coverage = report["source_coverage"]
    if coverage:
        lines.append("| Source | Before | After | Delta |")
        lines.append("| --- | ---: | ---: | ---: |")
        for source, item in coverage.items():
            lines.append(
                f"| {source} | {item['before']} | {item['after']} | {item['delta']} |"
            )
    else:
        lines.append("[missing] source coverage")

    lines.extend(["", "## Freshness", ""])
    lines.append("```json")
    lines.append(json.dumps(report["freshness"], indent=2, ensure_ascii=False))
    lines.append("```")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two operational snapshots")
    parser.add_argument("before", help="Before snapshot JSON")
    parser.add_argument("after", help="After snapshot JSON")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    report = compare(load_json(Path(args.before)), load_json(Path(args.after)))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(markdown_report(report))
        print("")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
