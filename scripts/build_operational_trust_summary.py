#!/usr/bin/env python3
"""Build a readonly operational trust summary from existing evidence."""

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
OUTPUT_FILE = REPORTS_DIR / "operational_trust_summary.md"


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
    if not isinstance(payload, dict):
        warnings.append(f"malformed snapshot: {path} (root is not object)")
        return {}
    return payload


def match(text: str, pattern: str, default: str = "unknown") -> str:
    found = re.search(pattern, text, re.MULTILINE)
    return found.group(1).strip() if found else default


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


def min_level(*levels: str) -> str:
    order = {"high": 4, "medium": 3, "limited": 2, "low": 1, "critical": 0}
    clean = [level if level in order else "limited" for level in levels]
    return min(clean, key=lambda level: order[level]) if clean else "limited"


def derive_trust(reports_dir: Path, snapshot_file: Path) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    maintenance = read_text(reports_dir / "maintenance_readiness_summary.md", warnings)
    caveats = read_text(reports_dir / "demo_caveats.md", warnings)
    drift = read_text(reports_dir / "drift_timeline.md", warnings)
    freshness = read_text(reports_dir / "freshness_escalation.md", warnings)
    snapshot = read_snapshot(snapshot_file, warnings)

    freshness_state = match(maintenance, r"^Freshness state:\s*\*\*([^*]+)\*\*")
    freshness_confidence = match(maintenance, r"^- Freshness confidence:\s*(.+)$", "low")
    source_confidence = match(maintenance, r"^- Source completeness confidence:\s*(.+)$", "low")
    operational_confidence = match(maintenance, r"^- Operational confidence level:\s*(.+)$", "limited")
    caveat_presence = match(maintenance, r"^- Demo caveat presence:\s*(.+)$", "required")
    drift_severity = match(drift, r"^Overall severity:\s*(.+)$", "unknown")

    counts = source_counts(snapshot)
    missing_sources = [source for source in ("QS", "THE", "ARWU") if counts.get(source, 0) == 0]
    caveat_text = caveats.lower()

    if freshness_state == "critical":
        release_confidence = "low"
        demo_confidence = "limited"
    elif freshness_state in ("stale", "degraded"):
        release_confidence = "limited"
        demo_confidence = "medium"
    else:
        release_confidence = "medium"
        demo_confidence = "high"

    if missing_sources:
        release_confidence = min_level(release_confidence, "low")
        demo_confidence = min_level(demo_confidence, "limited")
    if "does not hide stale data" not in caveat_text:
        demo_confidence = min_level(demo_confidence, "limited")
    if drift_severity in ("critical", "warning"):
        release_confidence = min_level(release_confidence, "limited")
    maintenance_confidence = min_level(operational_confidence, "limited" if warnings else "medium")
    operational_trust = min_level(
        freshness_confidence,
        source_confidence,
        release_confidence,
        demo_confidence,
        maintenance_confidence,
    )
    if freshness_state == "critical" and missing_sources:
        operational_trust = "critical"

    return {
        "freshness_confidence": freshness_confidence,
        "source_completeness_confidence": source_confidence,
        "release_confidence": release_confidence,
        "demo_confidence": demo_confidence,
        "maintenance_confidence": maintenance_confidence,
        "operational_trust_level": operational_trust,
        "freshness_state": freshness_state,
        "drift_severity": drift_severity,
        "missing_sources": ", ".join(missing_sources) if missing_sources else "[none]",
        "caveat_presence": caveat_presence,
        "snapshot_timestamp": str(snapshot.get("snapshot_timestamp") or "[missing]"),
    }, warnings


def markdown(summary: dict[str, str], warnings: list[str]) -> str:
    lines = [
        "# Operational Trust Summary",
        "",
        f"Generated: {dt.datetime.now(tz=dt.timezone.utc).isoformat()}",
        f"Snapshot: `{summary['snapshot_timestamp']}`",
        "",
        "## Confidence",
        "",
        "| Dimension | Level | Evidence |",
        "| --- | --- | --- |",
        f"| Freshness confidence | {summary['freshness_confidence']} | Freshness state: {summary['freshness_state']} |",
        f"| Source completeness confidence | {summary['source_completeness_confidence']} | Missing sources: {summary['missing_sources']} |",
        f"| Release confidence | {summary['release_confidence']} | Release claims require caveats when freshness/source gaps exist. |",
        f"| Demo confidence | {summary['demo_confidence']} | Demo caveat presence: {summary['caveat_presence']} |",
        f"| Maintenance confidence | {summary['maintenance_confidence']} | Derived from maintenance readiness and report availability. |",
        f"| Operational trust level | {summary['operational_trust_level']} | Conservative minimum across dimensions. |",
        "",
        "## Interpretation",
        "",
        "- Confidence is explanatory, not an automatic release gate.",
        "- Low or critical confidence must be stated honestly in demo/release context.",
        "- No hidden scoring, fallback source substitution, or automatic repair is performed.",
    ]
    if warnings:
        lines.extend(["", "## Input Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def build(reports_dir: Path, snapshot_file: Path) -> str:
    summary, warnings = derive_trust(reports_dir, snapshot_file)
    return markdown(summary, warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build operational trust summary")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build(Path(args.reports_dir), Path(args.snapshot_file)), encoding="utf-8")
    print(f"[operational-trust] written: {output}")
    return 0


def validate_trust_summary() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-trust-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        (reports / "maintenance_readiness_summary.md").write_text("not markdown", encoding="utf-8")
        (reports / "demo_caveats.md").write_text("", encoding="utf-8")
        (reports / "drift_timeline.md").write_text("# Drift\nOverall severity: info\n", encoding="utf-8")
        (reports / "freshness_escalation.md").write_text("# Freshness\n", encoding="utf-8")
        snapshot = root / "latest_status.json"
        snapshot.write_text("{broken", encoding="utf-8")
        result = build(reports, snapshot)
        assert "malformed input" in result
        assert "empty input" in result
        assert "malformed snapshot" in result


if __name__ == "__main__":
    raise SystemExit(main())
