#!/usr/bin/env python3
"""Build a single-page readonly maintenance navigation guide."""

from __future__ import annotations

import argparse
import datetime as dt
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_FILE = REPORTS_DIR / "maintenance_navigation.md"

REPORT_CRITICALITY: dict[str, str] = {
    "smoke_release_output.txt": "critical",
    "operational_trust_summary.md": "critical",
    "freshness_escalation.md": "critical",
    "demo_caveats.md": "critical",
    "operational_summary.md": "important",
    "maintenance_readiness_summary.md": "important",
    "drift_timeline.md": "important",
    "operational_index_summary.md": "reference",
    "snapshot_timeline.md": "reference",
    "snapshot_timeline.json": "reference",
    "latest_failure_summary.md": "reference",
    "maintenance_navigation.md": "reference",
}

DEMO_FACING = {"demo_caveats.md", "operational_trust_summary.md", "maintenance_readiness_summary.md"}
HISTORICAL = {"snapshot_timeline.md", "snapshot_timeline.json", "latest_failure_summary.md"}


def probe_report(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.stat().st_size == 0:
        return "empty"
    return "present"


def probe_reports(reports_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in REPORT_CRITICALITY:
        candidate = reports_dir / name
        result[name] = probe_report(candidate)
    smoke = REPO_ROOT / "releases" / "v0.1-demo" / "smoke_release_output.txt"
    result["smoke_release_output.txt"] = probe_report(smoke)
    return result


def status_icon(status: str) -> str:
    return {"present": "[ok]", "missing": "[missing]", "empty": "[empty]"}.get(status, "[?]")


def build(reports_dir: Path) -> str:
    statuses = probe_reports(reports_dir)
    now = dt.datetime.now(tz=dt.timezone.utc).isoformat()

    lines: list[str] = [
        "# Maintenance Navigation",
        "",
        f"Generated: {now}",
        "",
        "Single-page operator guide. Read this first when starting a maintenance",
        "or demo-preparation session.",
        "",
        "---",
        "",
        "## Where To Start",
        "",
        "Run the maintenance overview first:",
        "",
        "```bash",
        "./scripts/maintenance_overview.sh",
        "```",
        "",
        "This is always the first step. It calls the key report builders and",
        "surfaces the most important signals in one pass.",
        "",
        "---",
        "",
        "## Which Report To Read First",
        "",
        "| Context | First Report |",
        "| --- | --- |",
        "| Daily check | `reports/operational_trust_summary.md` |",
        "| Pre-demo | `reports/demo_caveats.md` |",
        "| Freshness concern | `reports/freshness_escalation.md` |",
        "| Release gate | `releases/v0.1-demo/smoke_release_output.txt` |",
        "| New operator onboarding | `docs/README.md` |",
        "",
        "---",
        "",
        "## Authoritative Signals",
        "",
        "These signals are authoritative. When they disagree with secondary sources,",
        "trust these:",
        "",
        "| Signal | Location | Status |",
        "| --- | --- | --- |",
    ]

    authoritative = [
        ("smoke_release_output.txt", "releases/v0.1-demo/smoke_release_output.txt"),
        ("operational_trust_summary.md", "reports/operational_trust_summary.md"),
        ("freshness_escalation.md", "reports/freshness_escalation.md"),
        ("demo_caveats.md", "reports/demo_caveats.md"),
    ]
    for name, display_path in authoritative:
        icon = status_icon(statuses.get(name, "missing"))
        lines.append(f"| `{display_path}` | Authoritative | {icon} |")

    lines += [
        "",
        "---",
        "",
        "## Release-Critical Caveats",
        "",
    ]

    caveats_status = statuses.get("demo_caveats.md", "missing")
    if caveats_status == "present":
        lines += [
            "Demo caveats file is present. Read `reports/demo_caveats.md` for the",
            "current list of caveats that must be stated before any demo or release.",
            "",
        ]
    else:
        lines += [
            f"[{caveats_status.upper()}] `reports/demo_caveats.md` — regenerate with:",
            "",
            "```bash",
            "./scripts/build_demo_caveats.py",
            "```",
            "",
        ]

    lines += [
        "Caveats are required reading before presenting or releasing. They are not",
        "optional context.",
        "",
        "---",
        "",
        "## Demo-Facing vs Maintenance-Only Reports",
        "",
        "| Report | Audience | Status |",
        "| --- | --- | --- |",
    ]

    for name in REPORT_CRITICALITY:
        if name in ("smoke_release_output.txt", "maintenance_navigation.md"):
            continue
        audience = "Demo + Maintenance" if name in DEMO_FACING else (
            "Historical" if name in HISTORICAL else "Maintenance"
        )
        icon = status_icon(statuses.get(name, "missing"))
        lines.append(f"| `reports/{name}` | {audience} | {icon} |")

    lines += [
        "",
        "---",
        "",
        "## Historical-Only Artifacts",
        "",
        "Do not use these for current-state decisions. They are point-in-time",
        "evidence and may be stale:",
        "",
        "- `snapshots/system_snapshot_*.json` — named point-in-time snapshots",
        "- `reports/snapshot_timeline.md` / `snapshot_timeline.json` — historical comparison",
        "- `reports/latest_failure_summary.md` — diagnostics-era failure log",
        "- `releases/v0.1-demo/*.md` (report copies) — bundle time snapshots",
        "",
        "For current state, always use live `reports/` files.",
        "",
        "---",
        "",
        "## Maintenance Restraint Reminder",
        "",
        "Before adding any new script, report, or diagnostic tool, consult:",
        "",
        "- `docs/OPERATIONAL_RESTRAINT_GUIDELINES.md` — when NOT to add tooling",
        "- `docs/REPORT_CRITICALITY.md` — criticality hierarchy",
        "- `docs/SIGNAL_TO_NOISE_REVIEW.md` — signal value classification",
        "",
        "The operational surface is intentionally bounded. New additions require",
        "justification against the safe addition criteria.",
        "",
        "---",
        "",
        "## Readonly Guarantee",
        "",
        "This script reads existing report files and generates a static Markdown",
        "summary. It does not connect to PostgreSQL, modify application state,",
        "retrigger crawlers, or mutate any operational artifact other than",
        "`reports/maintenance_navigation.md`.",
    ]

    missing_critical = [
        name for name, status in statuses.items()
        if REPORT_CRITICALITY.get(name) == "critical" and status != "present"
    ]
    if missing_critical:
        lines += [
            "",
            "---",
            "",
            "## Missing Critical Reports",
            "",
            "The following critical reports are not present. Regenerate them before",
            "demo or release:",
            "",
        ]
        for name in missing_critical:
            lines.append(f"- `{name}` — {statuses[name]}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build maintenance navigation guide")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build(reports_dir), encoding="utf-8")
    print(f"[maintenance-navigation] written: {output}")
    return 0


def _validate() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-nav-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        result = build(reports)
        assert "Maintenance Navigation" in result
        assert "missing" in result.lower()
        assert "MISSING CRITICAL REPORTS" in result.upper() or "missing" in result.lower()
        (reports / "demo_caveats.md").write_text("# Demo Caveats\n\n- caveat one\n", encoding="utf-8")
        result2 = build(reports)
        assert "demo_caveats.md" in result2


if __name__ == "__main__":
    raise SystemExit(main())
