#!/usr/bin/env python3
"""Build a maintenance steadiness summary assessing RC-1 operational stability."""

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
OUTPUT_FILE = REPORTS_DIR / "maintenance_steadiness_summary.md"

RC1_STABLE_CONDITIONS = [
    "QS data is stale (no new crawl since RC-1 packaging)",
    "THE and ARWU source files not acquired (out-of-scope for RC-1)",
    "Subject ranking rows at zero (MVP scope: QS global rankings only)",
    "Release confidence limited (localhost demo, caveats documented)",
]

RC1_DEGRADED_INDICATORS = [
    ("QS freshness", "stale (~354h)", "No crawl run since RC-1 packaging; expected for packaged demo"),
    ("THE availability", "unavailable (0 records)", "Source files not acquired; out-of-scope at RC-1"),
    ("ARWU availability", "unavailable (0 records)", "Source files not acquired; out-of-scope at RC-1"),
    ("Subject ranking rows", "0 — no subject data", "QS subject ranking not yet ingested at MVP scope"),
    ("Release confidence", "limited", "Derived from freshness and source gaps; documented and caveat-covered"),
    ("Operational trust level", "critical", "Derived from freshness + source gaps; known and disclosed"),
]


def read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"missing: {path.name}")
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"unreadable: {path.name} ({exc})")
        return ""


def read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing: {path.name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        warnings.append(f"malformed json: {path.name} ({exc})")
        return {}


def match(text: str, pattern: str, default: str = "unknown") -> str:
    found = re.search(pattern, text, re.MULTILINE)
    return found.group(1).strip() if found else default


def source_states(snapshot: dict[str, Any]) -> dict[str, int]:
    raw = snapshot.get("source_counts", [])
    if isinstance(raw, dict):
        return {str(k): int(v or 0) for k, v in raw.items()}
    result: dict[str, int] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("source_code"):
                result[str(item["source_code"])] = int(item.get("count") or 0)
    return result


def smoke_status(releases_dir: Path) -> str:
    """Return 'passed', 'failed', or 'missing'."""
    smoke = releases_dir / "v0.1-demo" / "smoke_release_output.txt"
    if not smoke.exists():
        return "missing"
    text = smoke.read_text(encoding="utf-8", errors="replace")
    if "0 failed" in text and "passed" in text:
        return "passed"
    return "failed"


def build(reports_dir: Path, snapshot_file: Path, releases_dir: Path) -> str:
    warnings: list[str] = []

    maintenance = read_text(reports_dir / "maintenance_readiness_summary.md", warnings)
    trust = read_text(reports_dir / "operational_trust_summary.md", warnings)
    snapshot = read_json(snapshot_file, warnings)

    freshness_state = match(maintenance, r"^Freshness state:\s*\*\*([^*]+)\*\*", "unknown")
    agg_count = match(maintenance, r"^- Aggregated count:\s*(\d+)", "unknown")
    agg_age = match(maintenance, r"^- Latest aggregation age hours:\s*([\d.]+)", "unknown")
    trust_level = match(trust, r"^\| Operational trust level \| ([^|]+) \|", "unknown").strip()
    snap_ts = str(snapshot.get("snapshot_timestamp") or "[missing]")
    counts = source_states(snapshot)

    available_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) > 0]
    missing_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) == 0]
    smoke_result = smoke_status(releases_dir)

    new_concerns: list[str] = []
    if smoke_result == "failed":
        new_concerns.append("Smoke check is showing failures — investigate before demo.")
    if agg_count not in ("unknown",) and int(agg_count) < 1000:
        new_concerns.append(
            f"Aggregated count is low ({agg_count}). Expected ~1,499. Investigate before demo."
        )
    if "QS" in missing_sources:
        new_concerns.append(
            "QS source has zero records — this is unexpected. Check snapshot and pipeline."
        )
    qs_count = counts.get("QS", 0)
    if 0 < qs_count < 100:
        new_concerns.append(
            f"QS record count is anomalously low ({qs_count}). Expected ~1,499. Investigate."
        )

    caution_level = "low — no action required" if not new_concerns else "elevated — review before demo"

    now = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    lines = [
        "# Maintenance Steadiness Summary",
        "",
        f"Generated: {now}",
        f"Snapshot: `{snap_ts}`",
        "",
        "This summary assesses the operational steadiness of CrawlerNest at RC-1.",
        "Read this alongside the calm summary to confirm the system remains in its",
        "expected stable degraded posture.",
        "",
        "---",
        "",
        "## Current Posture",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Aggregated universities | {agg_count} |",
        f"| Available sources | {', '.join(available_sources) if available_sources else '[none]'} |",
        f"| Freshness state | {freshness_state} |",
        f"| Data age (hours) | {agg_age} |",
        f"| Operational trust level | {trust_level} |",
        f"| Smoke | {smoke_result} |",
        "",
        "---",
        "",
        "## Stable Degraded Posture",
        "",
        "The following degraded indicators are present at RC-1. They are expected,",
        "documented, and non-worsening. They do not constitute an active incident.",
        "",
    ]
    for indicator, value, rationale in RC1_DEGRADED_INDICATORS:
        lines.append(f"- **{indicator}**: {value} — {rationale}")

    lines += [
        "",
        "See `docs/STABLE_DEGRADED_STATE.md` for the full posture definition and",
        "communication guidance.",
        "",
        "---",
        "",
        "## Caution Level",
        "",
        f"**{caution_level}**",
        "",
    ]

    if new_concerns:
        lines += [
            "The following signals are NOT part of the known stable posture:",
            "",
        ]
        for concern in new_concerns:
            lines.append(f"- {concern}")
        lines += [
            "",
            "Use Mode 4 (Incident Investigation) from `docs/MAINTENANCE_READING_MODES.md`.",
        ]
    else:
        lines += [
            "No signals outside the known stable RC-1 posture were detected.",
        ]

    lines += [
        "",
        "---",
        "",
    ]

    if new_concerns:
        lines += [
            "## Signals Requiring Attention",
            "",
            "The following signals are NOT part of the known stable posture.",
            "They should be investigated before a demo or release:",
            "",
        ]
        for concern in new_concerns:
            lines.append(f"- {concern}")
        lines += [
            "",
            "Use Mode 4 (Incident Investigation) from `docs/MAINTENANCE_READING_MODES.md`.",
            "",
            "---",
            "",
        ]
    else:
        lines += [
            "## No New Signals",
            "",
            "No signals outside the known stable posture were detected.",
            "The system is in expected RC-1 maintenance state.",
            "",
            "---",
            "",
        ]

    lines += [
        "## Steadiness Guidance",
        "",
        "- Daily maintenance check: run `maintenance_overview.sh` only. No additional scripts needed.",
        "- Any concern listed above requires Mode 4 investigation before demo or release.",
        "- Full maintenance cadence (daily/weekly/release-demo/incident-only) is in",
        "  `docs/MAINTENANCE_CADENCE_REVIEW.md`.",
        "",
        "---",
        "",
        "## Readonly Guarantee",
        "",
        "This script reads existing report and snapshot files only.",
        "It does not connect to PostgreSQL, mutate application state,",
        "rerun crawlers, or change any operational artifact other than",
        "`reports/maintenance_steadiness_summary.md`.",
    ]

    if warnings:
        lines += ["", "---", "", "## Input Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build maintenance steadiness summary")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE))
    parser.add_argument("--releases-dir", default=str(REPO_ROOT / "releases"))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build(Path(args.reports_dir), Path(args.snapshot_file), Path(args.releases_dir))
    output.write_text(content, encoding="utf-8")
    print(f"[maintenance-steadiness-summary] written: {output}")
    return 0


def _validate() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-steadiness-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        releases = root / "releases"
        (releases / "v0.1-demo").mkdir(parents=True)

        result_empty = build(reports, root / "latest_status.json", releases)
        assert "Maintenance Steadiness Summary" in result_empty, "heading missing"
        assert "Caution Level" in result_empty, "caution level section missing"
        assert "missing" in result_empty.lower(), "expected missing warnings"

        (reports / "maintenance_readiness_summary.md").write_text(
            "# Maintenance\nFreshness state: **critical**\n"
            "- Aggregated count: 1499\n"
            "- Latest aggregation age hours: 354.0\n",
            encoding="utf-8",
        )
        (reports / "operational_trust_summary.md").write_text(
            "# Trust\n| Operational trust level | limited |\n",
            encoding="utf-8",
        )
        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-22T15:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 1499}]}',
            encoding="utf-8",
        )
        result_ok = build(reports, root / "latest_status.json", releases)
        assert "1499" in result_ok, "aggregated count missing"
        assert "No New Signals" in result_ok, "expected no-new-signals section"
        assert "Caution Level" in result_ok, "caution level section missing"
        assert "low" in result_ok, "expected low caution level"

        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-22T15:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 5}]}',
            encoding="utf-8",
        )
        result_concern = build(reports, root / "latest_status.json", releases)
        assert "Signals Requiring Attention" in result_concern, "concern section missing"
        assert "elevated" in result_concern, "expected elevated caution level"


if __name__ == "__main__":
    raise SystemExit(main())
