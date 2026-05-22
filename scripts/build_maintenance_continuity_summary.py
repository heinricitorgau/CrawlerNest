#!/usr/bin/env python3
"""Build a maintenance continuity summary assessing RC-1 operational continuity posture."""

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
OUTPUT_FILE = REPORTS_DIR / "maintenance_continuity_summary.md"

RC1_STABLE_CONDITIONS = [
    "QS data is stale (no new crawl since RC-1 packaging)",
    "THE and ARWU source files not acquired (out-of-scope for RC-1)",
    "Subject ranking rows at zero (MVP scope: QS global rankings only)",
    "Release confidence limited (localhost demo, caveats documented)",
]

CONTINUITY_DIMENSIONS = [
    ("Stable degraded continuity", "RC-1 degraded conditions unchanged and non-worsening"),
    ("Report continuity", "Report semantics stable; no classification drift detected"),
    ("Snapshot continuity", "Named snapshots append-only; latest_status.json is current pointer"),
    ("Confidence continuity", "Trust levels derived from observable signals; not manually adjusted"),
    ("Release honesty continuity", "demo_caveats.md exists and was last generated this session"),
    ("Operational vocabulary continuity", "Terminology consistent with docs/OPERATIONAL_VOCABULARY.md"),
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
    caveats = read_text(reports_dir / "demo_caveats.md", warnings)
    snapshot = read_json(snapshot_file, warnings)

    freshness_state = match(maintenance, r"^Freshness state:\s*\*\*([^*]+)\*\*", "unknown")
    agg_count = match(maintenance, r"^- Aggregated count:\s*(\d+)", "unknown")
    trust_level = match(trust, r"^\| Operational trust level \| ([^|]+) \|", "unknown").strip()
    snap_ts = str(snapshot.get("snapshot_timestamp") or "[missing]")
    counts = source_states(snapshot)

    available_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) > 0]
    missing_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) == 0]
    smoke_result = smoke_status(releases_dir)

    # Determine genuine continuity regressions (new, unexpected conditions).
    new_concerns: list[str] = []
    if smoke_result == "failed":
        new_concerns.append("Smoke check is showing failures — runtime continuity at risk.")
    if agg_count not in ("unknown",) and int(agg_count) < 1000:
        new_concerns.append(
            f"Aggregated count dropped to {agg_count}. Expected ~1,499. Report continuity risk."
        )
    if "QS" in missing_sources:
        new_concerns.append(
            "QS source has zero records — unexpected loss of primary source. Snapshot continuity risk."
        )
    qs_count = counts.get("QS", 0)
    if 0 < qs_count < 100:
        new_concerns.append(
            f"QS record count anomalously low ({qs_count}). Expected ~1,499. Investigate."
        )
    if not caveats:
        new_concerns.append(
            "demo_caveats.md is missing — release honesty continuity risk. Regenerate before demo."
        )

    # Release honesty continuity note.
    honesty_status = "present" if caveats else "missing"

    now = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    lines = [
        "# Maintenance Continuity Summary",
        "",
        f"Generated: {now}",
        f"Snapshot: `{snap_ts}`",
        "",
        "This summary assesses operational continuity at RC-1.",
        "Read this alongside the calm and steadiness summaries to confirm",
        "the system remains coherent across sessions and operators.",
        "",
        "---",
        "",
        "## Continuity Posture",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Aggregated universities | {agg_count} |",
        f"| Available sources | {', '.join(available_sources) if available_sources else '[none]'} |",
        f"| Freshness state | {freshness_state} |",
        f"| Operational trust level | {trust_level} |",
        f"| Smoke | {smoke_result} |",
        f"| Demo caveats | {honesty_status} |",
        "",
        "---",
        "",
        "## Stable Degraded Continuity",
        "",
        "The following conditions have been stable since RC-1 packaging.",
        "They are expected, documented, and non-worsening.",
        "They do not represent continuity regressions.",
        "",
    ]
    for condition in RC1_STABLE_CONDITIONS:
        lines.append(f"- {condition}")

    lines += [
        "",
        "See `docs/STABLE_DEGRADED_CONTINUITY.md` for long-term maintenance guidance.",
        "",
        "---",
        "",
        "## Operational Memory Durability Posture",
        "",
        "| Artifact Class | Status |",
        "| --- | --- |",
        "| Named snapshots | append-only; durable |",
        f"| Release bundle (v0.1-demo) | frozen at bundle-build time; durable |",
        "| Live reports (reports/*.md) | ephemeral; regenerated each session |",
        "| Demo caveats | " + honesty_status + " |",
        "",
        "See `docs/OPERATIONAL_MEMORY_DURABILITY.md` for full durability classification.",
        "",
        "---",
        "",
        "## Release Honesty Continuity",
        "",
    ]

    if caveats:
        lines += [
            "demo_caveats.md is present. Before any demo or release:",
            "",
            "1. Read `reports/demo_caveats.md` in full.",
            "2. State all listed caveats to the audience explicitly.",
            "3. Do not omit caveats for audiences who have heard them before.",
            "",
        ]
    else:
        lines += [
            "**demo_caveats.md is missing.** Regenerate before any demo or release:",
            "",
            "```bash",
            "python3 scripts/build_demo_caveats.py",
            "```",
            "",
        ]

    lines += [
        "See `docs/DEMO_HONESTY_GUIDELINES.md` for required phrasing.",
        "",
        "---",
        "",
        "## Continuity Dimensions",
        "",
        "| Dimension | Assessment |",
        "| --- | --- |",
    ]
    for dimension, assessment in CONTINUITY_DIMENSIONS:
        lines.append(f"| {dimension} | {assessment} |")

    lines += [
        "",
        "---",
        "",
    ]

    if new_concerns:
        lines += [
            "## Continuity Regressions Detected",
            "",
            "The following signals are outside the known stable posture.",
            "They represent continuity risks that should be investigated:",
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
            "## No Continuity Regressions Detected",
            "",
            "All signals are within the known stable RC-1 posture.",
            "No continuity regressions were detected in this session.",
            "",
            "---",
            "",
        ]

    lines += [
        "## Maintenance Steadiness Posture",
        "",
        "See `reports/maintenance_steadiness_summary.md` for caution level and",
        "steadiness guidance. See `reports/maintenance_calm_summary.md` for the",
        "full calm posture context.",
        "",
        "---",
        "",
        "## Readonly Guarantee",
        "",
        "This script reads existing report and snapshot files only.",
        "It does not connect to PostgreSQL, mutate application state,",
        "rerun crawlers, or change any operational artifact other than",
        "`reports/maintenance_continuity_summary.md`.",
    ]

    if warnings:
        lines += ["", "---", "", "## Input Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build maintenance continuity summary")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE))
    parser.add_argument("--releases-dir", default=str(REPO_ROOT / "releases"))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build(Path(args.reports_dir), Path(args.snapshot_file), Path(args.releases_dir))
    output.write_text(content, encoding="utf-8")
    print(f"[maintenance-continuity-summary] written: {output}")
    return 0


def _validate() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-continuity-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        releases = root / "releases"
        (releases / "v0.1-demo").mkdir(parents=True)

        result_empty = build(reports, root / "latest_status.json", releases)
        assert "Maintenance Continuity Summary" in result_empty, "heading missing"
        assert "Continuity Posture" in result_empty, "posture section missing"
        assert "missing" in result_empty.lower(), "expected missing warnings"
        # Missing demo_caveats.md should trigger a concern
        assert "Continuity Regressions Detected" in result_empty, "expected concern for missing caveats"

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
        (reports / "demo_caveats.md").write_text(
            "# Demo Caveats\n- QS data is stale.\n",
            encoding="utf-8",
        )
        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-22T15:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 1499}]}',
            encoding="utf-8",
        )
        result_ok = build(reports, root / "latest_status.json", releases)
        assert "1499" in result_ok, "aggregated count missing"
        assert "No Continuity Regressions Detected" in result_ok, "expected no-regression section"
        assert "Stable Degraded Continuity" in result_ok, "stable degraded section missing"

        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-22T15:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 5}]}',
            encoding="utf-8",
        )
        result_concern = build(reports, root / "latest_status.json", releases)
        assert "Continuity Regressions Detected" in result_concern, "concern section missing"


if __name__ == "__main__":
    raise SystemExit(main())
