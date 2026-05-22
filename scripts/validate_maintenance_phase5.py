#!/usr/bin/env python3
"""Minimal validation for maintenance phase 5 artifacts."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = REPO_ROOT / "reports"


def check_phase5_docs() -> list[str]:
    failures: list[str] = []
    required = [
        "OPERATIONAL_CALMNESS_REVIEW.md",
        "REPORT_LIFECYCLE.md",
        "MAINTENANCE_FATIGUE_REVIEW.md",
        "OPERATIONAL_COHERENCE_REVIEW.md",
        "MAINTENANCE_READING_MODES.md",
    ]
    for name in required:
        path = DOCS_DIR / name
        if not path.exists():
            failures.append(f"[missing doc] {path}")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip().startswith("#"):
            failures.append(f"[malformed doc] {path} — missing markdown heading")
        if len(text.strip()) < 200:
            failures.append(f"[suspiciously short doc] {path} — {len(text.strip())} chars")
    return failures


def check_calm_summary_script() -> list[str]:
    failures: list[str] = []
    script = SCRIPTS_DIR / "build_maintenance_calm_summary.py"
    if not script.exists():
        failures.append(f"[missing script] {script}")
        return failures

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from build_maintenance_calm_summary import build  # type: ignore[import]

        with tempfile.TemporaryDirectory(prefix="crawlernest-calm-p5-") as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()
            releases = Path(tmp) / "releases"
            (releases / "v0.1-demo").mkdir(parents=True)

            result_empty = build(reports, Path(tmp) / "latest_status.json", releases)
            if "Maintenance Calm Summary" not in result_empty:
                failures.append("[calm-summary] missing heading in empty output")
            if "Known Stable Conditions" not in result_empty:
                failures.append("[calm-summary] missing RC1 stable conditions section")
            if "Release Honesty Reminder" not in result_empty:
                failures.append("[calm-summary] missing release honesty reminder")
            if "missing" not in result_empty.lower():
                failures.append("[calm-summary] expected input warnings in empty-reports output")

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
            import json
            (Path(tmp) / "latest_status.json").write_text(
                json.dumps({
                    "snapshot_timestamp": "2026-05-22T15:00:00+00:00",
                    "source_counts": [{"source_code": "QS", "count": 1499}],
                }),
                encoding="utf-8",
            )
            result_ok = build(reports, Path(tmp) / "latest_status.json", releases)
            if "1499" not in result_ok:
                failures.append("[calm-summary] aggregated count not reflected in output")
            if "No New Signals" not in result_ok:
                failures.append("[calm-summary] expected 'No New Signals' for healthy posture")

            (Path(tmp) / "latest_status.json").write_text(
                json.dumps({
                    "snapshot_timestamp": "2026-05-22T15:00:00+00:00",
                    "source_counts": [{"source_code": "QS", "count": 5}],
                }),
                encoding="utf-8",
            )
            result_concern = build(reports, Path(tmp) / "latest_status.json", releases)
            if "Signals Requiring Attention" not in result_concern:
                failures.append("[calm-summary] expected concern signal for low aggregated count")

    except Exception as exc:
        failures.append(f"[calm-summary] import or runtime error: {exc}")
    finally:
        sys.path.pop(0)

    return failures


def check_maintenance_overview_hints() -> list[str]:
    failures: list[str] = []
    script = SCRIPTS_DIR / "maintenance_overview.sh"
    if not script.exists():
        failures.append(f"[missing script] {script}")
        return failures
    text = script.read_text(encoding="utf-8")
    for expected in [
        "Calm Posture Summary",
        "Maintenance Reading Mode",
        "7/7",
        "maintenance_calm_summary",
        "MAINTENANCE_READING_MODES.md",
    ]:
        if expected not in text:
            failures.append(f"[maintenance_overview.sh] missing expected content: '{expected}'")
    return failures


def check_bundle_script_includes_calm() -> list[str]:
    failures: list[str] = []
    script = SCRIPTS_DIR / "build_demo_bundle.sh"
    if not script.exists():
        failures.append(f"[missing script] {script}")
        return failures
    text = script.read_text(encoding="utf-8")
    if "maintenance_calm_summary" not in text:
        failures.append("[build_demo_bundle.sh] maintenance_calm_summary.md not included in bundle")
    if "Report Lifecycle" not in text:
        failures.append("[build_demo_bundle.sh] Report Lifecycle section missing from OPERATIONAL_ARTIFACTS")
    if "Reading Mode" not in text:
        failures.append("[build_demo_bundle.sh] Reading Mode section missing from OPERATIONAL_ARTIFACTS")
    return failures


def check_readme_phase5_references() -> list[str]:
    failures: list[str] = []
    for readme_path in [REPO_ROOT / "README.md", REPO_ROOT / "README.zh-TW.md"]:
        if not readme_path.exists():
            failures.append(f"[missing] {readme_path}")
            continue
        text = readme_path.read_text(encoding="utf-8")
        if "OPERATIONAL_CALMNESS_REVIEW" not in text:
            failures.append(f"[{readme_path.name}] missing OPERATIONAL_CALMNESS_REVIEW reference")
        if "MAINTENANCE_READING_MODES" not in text:
            failures.append(f"[{readme_path.name}] missing MAINTENANCE_READING_MODES reference")
        if "REPORT_LIFECYCLE" not in text:
            failures.append(f"[{readme_path.name}] missing REPORT_LIFECYCLE reference")
    return failures


def check_lifecycle_doc_completeness() -> list[str]:
    failures: list[str] = []
    path = DOCS_DIR / "REPORT_LIFECYCLE.md"
    if not path.exists():
        failures.append(f"[missing] {path}")
        return failures
    text = path.read_text(encoding="utf-8")
    for expected_report in ["demo_caveats", "operational_trust_summary", "freshness_escalation",
                             "maintenance_calm_summary", "drift_timeline"]:
        if expected_report not in text:
            failures.append(f"[REPORT_LIFECYCLE.md] missing report entry: '{expected_report}'")
    for expected_category in ["ephemeral", "operational", "release-facing", "historical", "reference-only"]:
        if expected_category not in text:
            failures.append(f"[REPORT_LIFECYCLE.md] missing lifecycle category: '{expected_category}'")
    return failures


def check_reading_modes_doc() -> list[str]:
    failures: list[str] = []
    path = DOCS_DIR / "MAINTENANCE_READING_MODES.md"
    if not path.exists():
        failures.append(f"[missing] {path}")
        return failures
    text = path.read_text(encoding="utf-8")
    for mode in ["Quick Status", "Release", "Freshness", "Incident", "Long-Term", "Onboarding"]:
        if mode not in text:
            failures.append(f"[MAINTENANCE_READING_MODES.md] missing mode: '{mode}'")
    return failures


def main() -> int:
    all_failures: list[str] = []

    all_failures += check_phase5_docs()
    all_failures += check_calm_summary_script()
    all_failures += check_maintenance_overview_hints()
    all_failures += check_bundle_script_includes_calm()
    all_failures += check_readme_phase5_references()
    all_failures += check_lifecycle_doc_completeness()
    all_failures += check_reading_modes_doc()

    if all_failures:
        print("[maintenance-phase5-validation] FAILURES:")
        for f in all_failures:
            print(f"  {f}")
        return 1

    print("[maintenance-phase5-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
