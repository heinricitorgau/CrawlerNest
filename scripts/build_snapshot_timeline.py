#!/usr/bin/env python3
"""Build readonly timeline intelligence from CrawlerNest snapshot JSON files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshots"
REPORTS_DIR = REPO_ROOT / "reports"


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def timestamp_from_path(path: Path) -> str | None:
    match = re.search(r"system_snapshot_(\d{8})_(\d{6})", path.name)
    if not match:
        return None
    stamp = f"{match.group(1)}{match.group(2)}"
    try:
        parsed = dt.datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(
            tzinfo=dt.timezone.utc
        )
        return parsed.isoformat()
    except ValueError:
        return None


def as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_sources(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(k): as_int(v) for k, v in value.items()}
    if isinstance(value, list):
        result: dict[str, int] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            source = item.get("source_code") or item.get("source")
            if source:
                result[str(source)] = as_int(
                    item.get("count", item.get("records_in", item.get("record_count", 0)))
                )
        return result
    return {}


def extract_record(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    timestamp = (
        data.get("snapshot_timestamp")
        or timestamp_from_path(path)
        or dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()
    )
    source_counts = normalize_sources(
        data.get("source_counts") or nested(data, "health", "sources")
    )
    freshness = data.get("freshness") if isinstance(data.get("freshness"), dict) else {}
    aggregation = freshness.get("aggregation") if isinstance(freshness, dict) else {}
    if not isinstance(aggregation, dict):
        aggregation = {}

    return {
        "file": path.name,
        "snapshot_timestamp": timestamp,
        "aggregated_count": as_int(
            data.get(
                "aggregated_count",
                nested(data, "health", "aggregated_rankings_count")
                or nested(data, "regression_summary", "aggregated_count"),
            )
        ),
        "unresolved_total": as_int(
            data.get("unresolved_total", nested(data, "unresolved", "total"))
        ),
        "unresolved_last_7d": as_int(
            data.get("unresolved_last_7d", nested(data, "unresolved", "last_7d"))
        ),
        "unresolved_trend_pct": as_float(
            data.get("unresolved_trend_pct", nested(data, "unresolved", "trend_pct"))
        ),
        "source_counts": source_counts,
        "source_count_total": sum(source_counts.values()),
        "overall_stale": bool(data.get("overall_stale", freshness.get("overall_stale", False))),
        "latest_aggregation_at": data.get(
            "last_aggregation_at", aggregation.get("latest_at")
        ),
        "latest_aggregation_age_hours": as_float(
            data.get("latest_aggregation_age_hours", aggregation.get("age_hours"))
        ),
        "latest_aggregation_status": data.get(
            "last_aggregation_status", aggregation.get("status")
        ),
        "latest_subject_year": nested(data, "health", "latest_subject_year"),
        "subject_rankings_count": as_int(nested(data, "health", "subject_rankings_count")),
        "drift_warning_count": as_int(
            data.get("drift_warning_count", len(data.get("drift_warnings", []) or []))
        ),
        "drift_warnings": data.get("drift_warnings", []) if isinstance(
            data.get("drift_warnings", []), list
        ) else [],
        "freshness": freshness if isinstance(freshness, dict) else {},
    }


def load_snapshot_records(snapshot_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    records: list[dict[str, Any]] = []

    if not snapshot_dir.exists():
        warnings.append(f"snapshot directory not found: {snapshot_dir}")
        return records, warnings

    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(f"{path.name}: malformed JSON skipped ({exc})")
            continue
        if not isinstance(data, dict):
            warnings.append(f"{path.name}: non-object snapshot skipped")
            continue
        try:
            records.append(extract_record(path, data))
        except Exception as exc:
            warnings.append(f"{path.name}: snapshot skipped ({exc})")

    records.sort(
        key=lambda item: parse_time(item.get("snapshot_timestamp")) or dt.datetime.min.replace(
            tzinfo=dt.timezone.utc
        )
    )
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        key = (
            record.get("snapshot_timestamp"),
            record.get("aggregated_count"),
            record.get("unresolved_total"),
            tuple(sorted(record.get("source_counts", {}).items())),
        )
        existing = deduped.get(key)
        if existing is None or (
            existing.get("file") == "latest_status.json"
            and record.get("file") != "latest_status.json"
        ):
            deduped[key] = record

    return list(deduped.values()), warnings


def build_payload(records: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    return {
        "generated_at": dt.datetime.now(tz=dt.timezone.utc).isoformat(),
        "snapshot_count": len(records),
        "warnings": warnings,
        "timeline": records,
        "freshness_timeline": [
            {
                "snapshot_timestamp": item["snapshot_timestamp"],
                "overall_stale": item["overall_stale"],
                "latest_aggregation_age_hours": item["latest_aggregation_age_hours"],
                "latest_aggregation_status": item["latest_aggregation_status"],
            }
            for item in records
        ],
        "unresolved_trend": [
            {
                "snapshot_timestamp": item["snapshot_timestamp"],
                "unresolved_total": item["unresolved_total"],
                "unresolved_last_7d": item["unresolved_last_7d"],
                "unresolved_trend_pct": item["unresolved_trend_pct"],
            }
            for item in records
        ],
        "source_coverage_timeline": [
            {
                "snapshot_timestamp": item["snapshot_timestamp"],
                "source_counts": item["source_counts"],
            }
            for item in records
        ],
        "aggregation_count_timeline": [
            {
                "snapshot_timestamp": item["snapshot_timestamp"],
                "aggregated_count": item["aggregated_count"],
            }
            for item in records
        ],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Snapshot Timeline Intelligence",
        "",
        f"Generated: {payload['generated_at']}",
        f"Snapshots analyzed: {payload['snapshot_count']}",
        "",
    ]
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    timeline = payload.get("timeline", [])
    if not timeline:
        lines.extend([
            "## Timeline",
            "",
            "No snapshot JSON files were available for timeline analysis.",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "## Timeline Summary",
        "",
        "| Snapshot | Aggregated | Unresolved | Sources | Stale | Aggregation age (h) | Drift warnings |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: |",
    ])
    for item in timeline:
        sources = ", ".join(f"{k}:{v}" for k, v in sorted(item["source_counts"].items()))
        lines.append(
            f"| `{item['snapshot_timestamp']}` | {item['aggregated_count']} | "
            f"{item['unresolved_total']} | {sources or '[none]'} | "
            f"{item['overall_stale']} | {item['latest_aggregation_age_hours']} | "
            f"{item['drift_warning_count']} |"
        )

    lines.extend(["", "## Aggregation Count Timeline", ""])
    for item in payload["aggregation_count_timeline"]:
        lines.append(f"- `{item['snapshot_timestamp']}`: {item['aggregated_count']}")

    lines.extend(["", "## Unresolved Trend", ""])
    for item in payload["unresolved_trend"]:
        lines.append(
            f"- `{item['snapshot_timestamp']}`: total={item['unresolved_total']}, "
            f"last_7d={item['unresolved_last_7d']}, trend_pct={item['unresolved_trend_pct']}"
        )

    lines.extend(["", "## Source Coverage Timeline", ""])
    for item in payload["source_coverage_timeline"]:
        sources = ", ".join(f"{k}:{v}" for k, v in sorted(item["source_counts"].items()))
        lines.append(f"- `{item['snapshot_timestamp']}`: {sources or '[none]'}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build snapshot timeline intelligence")
    parser.add_argument("--snapshot-dir", default=str(SNAPSHOT_DIR))
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--md-output", default=None)
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_output = Path(args.json_output) if args.json_output else reports_dir / "snapshot_timeline.json"
    md_output = Path(args.md_output) if args.md_output else reports_dir / "snapshot_timeline.md"

    records, warnings = load_snapshot_records(Path(args.snapshot_dir))
    payload = build_payload(records, warnings)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_output.write_text(build_markdown(payload), encoding="utf-8")
    print(f"[snapshot-timeline] written: {md_output}")
    print(f"[snapshot-timeline] written: {json_output}")
    if warnings:
        print(f"[snapshot-timeline] warnings: {len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
