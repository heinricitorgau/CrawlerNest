#!/usr/bin/env python3
"""Build readonly demo caveats from existing operational reports."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
SNAPSHOT_FILE = REPO_ROOT / "snapshots" / "latest_status.json"
OUTPUT_FILE = REPORTS_DIR / "demo_caveats.md"


def read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"missing input: {path}")
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"unreadable input: {path} ({exc})")
        return ""
    if not text.strip():
        warnings.append(f"empty input: {path}")
    elif not text.lstrip().startswith("#"):
        warnings.append(f"malformed input: {path} (missing markdown heading)")
    return text


def read_snapshot(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing snapshot: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"malformed snapshot: {path} ({exc})")
        return {}
    return payload if isinstance(payload, dict) else {}


def match_one(text: str, pattern: str, default: str = "unknown") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default


def source_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    raw = snapshot.get("source_counts", [])
    if isinstance(raw, dict):
        return {str(k): int(v or 0) for k, v in raw.items()}
    result: dict[str, int] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("source_code"):
                result[str(item["source_code"])] = int(item.get("count") or 0)
    return result


def build_caveats(reports_dir: Path, snapshot_file: Path) -> str:
    warnings: list[str] = []
    freshness = read_text(reports_dir / "freshness_escalation.md", warnings)
    operational = read_text(reports_dir / "operational_summary.md", warnings)
    maintenance = read_text(reports_dir / "maintenance_readiness_summary.md", warnings)
    snapshot = read_snapshot(snapshot_file, warnings)

    freshness_state = match_one(freshness, r"^Escalation state:\s*\*\*([^*]+)\*\*")
    operational_state = match_one(operational, r"^- Freshness state:\s*\*\*([^*]+)\*\*")
    readiness = match_one(maintenance, r"^- Release/demo readiness:\s*(.+)$")
    counts = source_counts(snapshot)
    missing = [source for source in ("QS", "THE", "ARWU") if counts.get(source, 0) == 0]
    agg_age = match_one(maintenance, r"^- Latest aggregation age hours:\s*(.+)$", "unknown")
    subject_rows = match_one(maintenance, r"^- Subject ranking rows:\s*(.+)$", "unknown")

    caveats: list[str] = []
    if freshness_state in ("critical", "stale") or operational_state in ("critical", "stale"):
        caveats.append(
            f"Ranking data freshness is {freshness_state}; latest aggregation age is {agg_age} hours."
        )
    if missing:
        caveats.append("Expected sources unavailable in latest coverage: " + ", ".join(missing) + ".")
    if subject_rows in ("0", "None", "unknown"):
        caveats.append("Subject ranking freshness/completeness is limited in the latest snapshot.")
    caveats.extend([
        "This is a localhost/single-node demo posture, not a production deployment.",
        "Sessions are in-memory; API restart signs users out.",
    ])

    lines = [
        "# Demo Caveats",
        "",
        f"Generated: {dt.datetime.now(tz=dt.timezone.utc).isoformat()}",
        f"Snapshot: `{snapshot.get('snapshot_timestamp', '[missing]')}`",
        f"Release/demo readiness: {readiness}",
        "",
        "## Caveats To State",
        "",
    ]
    for caveat in caveats:
        lines.append(f"- {caveat}")

    lines.extend([
        "",
        "## What This Does Not Mean",
        "",
        "- It does not hide stale data.",
        "- It does not substitute missing source data.",
        "- It does not soften critical freshness warnings.",
        "- It does not authorize automatic source retry or pipeline repair.",
    ])
    if warnings:
        lines.extend(["", "## Input Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build demo caveats from operational reports")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_caveats(Path(args.reports_dir), Path(args.snapshot_file)), encoding="utf-8")
    print(f"[demo-caveats] written: {output}")
    return 0


def validate_demo_caveats() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-caveats-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        (reports / "freshness_escalation.md").write_text("not markdown", encoding="utf-8")
        (reports / "operational_summary.md").write_text("", encoding="utf-8")
        (reports / "maintenance_readiness_summary.md").write_text(
            "# Maintenance\n- Latest aggregation age hours: unknown\n", encoding="utf-8"
        )
        snapshot = root / "latest_status.json"
        snapshot.write_text("{broken", encoding="utf-8")
        result = build_caveats(reports, snapshot)
        assert "malformed input" in result
        assert "empty input" in result
        assert "malformed snapshot" in result


if __name__ == "__main__":
    raise SystemExit(main())
