#!/usr/bin/env python3
"""Minimal validation for maintenance phase 4 artifacts."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
DOCS_DIR = REPO_ROOT / "docs"
REPORTS_DIR = REPO_ROOT / ".local" / "reports"


def check_phase4_docs() -> list[str]:
    failures: list[str] = []
    required = [
        "operational/OPERATIONAL_RESTRAINT_GUIDELINES.md",
        "operational/MAINTENANCE_SUSTAINABILITY_REVIEW.md",
        "data/SIGNAL_TO_NOISE_REVIEW.md",
        "operational/OPERATIONAL_BOUNDARY_REINFORCEMENT.md",
        "data/REPORT_CRITICALITY.md",
        "release/RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md",
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


def check_navigation_script() -> list[str]:
    failures: list[str] = []
    script = SCRIPTS_DIR / "build_maintenance_navigation.py"
    if not script.exists():
        failures.append(f"[missing script] {script}")
        return failures

    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        from build_maintenance_navigation import build  # type: ignore[import]

        with tempfile.TemporaryDirectory(prefix="crawlernest-nav-p4-") as tmp:
            reports = Path(tmp) / "reports"
            reports.mkdir()

            result_empty = build(reports)
            if "Maintenance Navigation" not in result_empty:
                failures.append("[navigation] missing heading in empty-reports output")
            if "missing" not in result_empty.lower():
                failures.append("[navigation] expected 'missing' mention for absent critical reports")

            (reports / "demo_caveats.md").write_text(
                "# Demo Caveats\n\n- Caveat one.\n", encoding="utf-8"
            )
            (reports / "operational_trust_summary.md").write_text(
                "# Operational Trust Summary\n\nSome content.\n", encoding="utf-8"
            )
            (reports / "freshness_escalation.md").write_text(
                "# Freshness Escalation\n\nSome content.\n", encoding="utf-8"
            )
            result_partial = build(reports)
            if "demo_caveats.md" not in result_partial:
                failures.append("[navigation] demo_caveats.md not listed in partial output")
            if "smoke_release_output.txt" not in result_partial:
                failures.append("[navigation] smoke not mentioned in partial output")

    except Exception as exc:
        failures.append(f"[navigation] import or runtime error: {exc}")
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
    # The overview became nine numbered steps; "6/6" and the old navigation heading are gone, and the
    # navigation report is its step [6/9].
    for expected in [
        "Report Criticality Hint",
        "Operational Restraint Reminder",
        "REPORT_CRITICALITY.md",
        "OPERATIONAL_RESTRAINT_GUIDELINES.md",
        "Maintenance navigation report",
    ]:
        if expected not in text:
            failures.append(f"[maintenance_overview.sh] missing expected content: '{expected}'")
    return failures


def check_report_criticality_doc() -> list[str]:
    failures: list[str] = []
    path = DOCS_DIR / "data/REPORT_CRITICALITY.md"
    if not path.exists():
        failures.append(f"[missing] {path}")
        return failures
    text = path.read_text(encoding="utf-8")
    for expected in ["critical", "important", "reference", "smoke_release", "demo_caveats"]:
        if expected not in text.lower():
            failures.append(f"[REPORT_CRITICALITY.md] missing expected term: '{expected}'")
    return failures


def check_readme_maintenance_section() -> list[str]:
    failures: list[str] = []
    for readme_path in [REPO_ROOT / "README.md", REPO_ROOT / "README.zh-TW.md"]:
        if not readme_path.exists():
            failures.append(f"[missing] {readme_path}")
            continue
        # The root READMEs became a project overview (bf68525) and no longer list maintenance docs;
        # docs/README.md catalogs them (test_docs_catalog.py). Only their presence is still checked here.
    return failures


def main() -> int:
    all_failures: list[str] = []

    all_failures += check_phase4_docs()
    all_failures += check_navigation_script()
    all_failures += check_maintenance_overview_hints()
    all_failures += check_report_criticality_doc()
    all_failures += check_readme_maintenance_section()

    if all_failures:
        print("[maintenance-phase4-validation] FAILURES:")
        for f in all_failures:
            print(f"  {f}")
        return 1

    print("[maintenance-phase4-validation] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
