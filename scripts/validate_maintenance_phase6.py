#!/usr/bin/env python3
"""Validate Phase 6 maintenance milestone artifacts."""

from __future__ import annotations

import py_compile
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

FAILURES: list[str] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    if passed:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. Phase 6 docs exist
# ---------------------------------------------------------------------------
def check_phase6_docs() -> None:
    print("[1/7] Phase 6 docs")
    docs = [
        "docs/MAINTENANCE_CADENCE_REVIEW.md",
        "docs/OPERATIONAL_MEMORY_PRESERVATION.md",
        "docs/STABLE_DEGRADED_STATE.md",
        "docs/MAINTENANCE_DISCIPLINE.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")


# ---------------------------------------------------------------------------
# 2. Steadiness script exists and compiles
# ---------------------------------------------------------------------------
def check_steadiness_script() -> None:
    print("[2/7] Steadiness script")
    script = REPO_ROOT / "scripts" / "build_maintenance_steadiness_summary.py"
    check("scripts/build_maintenance_steadiness_summary.py exists", script.exists(), "file missing")
    if script.exists():
        try:
            py_compile.compile(str(script), doraise=True)
            check("steadiness script syntax", True)
        except py_compile.PyCompileError as exc:
            check("steadiness script syntax", False, str(exc))


# ---------------------------------------------------------------------------
# 3. Steadiness output contains expected sections
# ---------------------------------------------------------------------------
def check_steadiness_output() -> None:
    print("[3/7] Steadiness output")
    script = REPO_ROOT / "scripts" / "build_maintenance_steadiness_summary.py"
    if not script.exists():
        check("steadiness script runnable", False, "script missing — skipping output checks")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    check(
        "steadiness script exits 0",
        result.returncode == 0,
        f"rc={result.returncode} stderr={result.stderr[:120]}",
    )
    output_file = REPO_ROOT / "reports" / "maintenance_steadiness_summary.md"
    check("reports/maintenance_steadiness_summary.md exists", output_file.exists(), "file not written")
    if output_file.exists():
        content = output_file.read_text(encoding="utf-8")
        check(
            "steadiness output contains heading",
            "Maintenance Steadiness Summary" in content,
            "heading missing",
        )
        check(
            "steadiness output contains Caution Level",
            "Caution Level" in content,
            "section missing",
        )
        check(
            "steadiness output contains Stable Degraded Posture",
            "Stable Degraded Posture" in content,
            "section missing",
        )


# ---------------------------------------------------------------------------
# 4. Overview step count is 8/8
# ---------------------------------------------------------------------------
def check_overview_step_count() -> None:
    print("[4/7] Overview step count")
    overview = REPO_ROOT / "scripts" / "maintenance_overview.sh"
    check("maintenance_overview.sh exists", overview.exists(), "file missing")
    if overview.exists():
        text = overview.read_text(encoding="utf-8")
        check(
            "overview contains [8/8]",
            "[8/8]" in text,
            "step [8/8] not found — script may not have been updated",
        )
        check(
            "overview does not contain [7/7]",
            "[7/7]" not in text,
            "old [7/7] step label still present",
        )


# ---------------------------------------------------------------------------
# 5. Overview hints reference Phase 6 docs
# ---------------------------------------------------------------------------
def check_overview_hints() -> None:
    print("[5/7] Overview hints")
    overview = REPO_ROOT / "scripts" / "maintenance_overview.sh"
    if not overview.exists():
        check("maintenance_overview.sh readable", False, "file missing")
        return
    text = overview.read_text(encoding="utf-8")
    check(
        "overview references MAINTENANCE_CADENCE_REVIEW",
        "MAINTENANCE_CADENCE_REVIEW" in text,
        "cadence hint missing",
    )
    check(
        "overview references STABLE_DEGRADED_STATE",
        "STABLE_DEGRADED_STATE" in text,
        "stable degraded state hint missing",
    )
    check(
        "overview references build_maintenance_steadiness_summary",
        "build_maintenance_steadiness_summary" in text,
        "steadiness step missing",
    )


# ---------------------------------------------------------------------------
# 6. Bundle script includes steadiness summary
# ---------------------------------------------------------------------------
def check_bundle_includes_steadiness() -> None:
    print("[6/7] Bundle script includes steadiness summary")
    bundle = REPO_ROOT / "scripts" / "build_demo_bundle.sh"
    check("build_demo_bundle.sh exists", bundle.exists(), "file missing")
    if bundle.exists():
        text = bundle.read_text(encoding="utf-8")
        check(
            "bundle script copies maintenance_steadiness_summary",
            "maintenance_steadiness_summary" in text,
            "steadiness summary not included in bundle",
        )
        check(
            "bundle heredoc references STABLE_DEGRADED_STATE",
            "STABLE_DEGRADED_STATE" in text,
            "stable degraded posture section missing from OPERATIONAL_ARTIFACTS.md heredoc",
        )
        check(
            "bundle heredoc references MAINTENANCE_CADENCE_REVIEW",
            "MAINTENANCE_CADENCE_REVIEW" in text,
            "cadence reference missing from OPERATIONAL_ARTIFACTS.md heredoc",
        )


# ---------------------------------------------------------------------------
# 7. Root README references Phase 6 docs
# ---------------------------------------------------------------------------
def check_readme_phase6_references() -> None:
    print("[7/7] README Phase 6 references")
    readme = REPO_ROOT / "README.md"
    check("README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        check(
            "README references MAINTENANCE_CADENCE_REVIEW",
            "MAINTENANCE_CADENCE_REVIEW" in text,
            "cadence doc not listed",
        )
        check(
            "README references STABLE_DEGRADED_STATE",
            "STABLE_DEGRADED_STATE" in text,
            "stable degraded state doc not listed",
        )
        check(
            "README references MAINTENANCE_DISCIPLINE",
            "MAINTENANCE_DISCIPLINE" in text,
            "discipline doc not listed",
        )
        check(
            "README references build_maintenance_steadiness_summary",
            "build_maintenance_steadiness_summary" in text,
            "steadiness summary script not listed",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("Phase 6 Validation")
    print("==================")

    check_phase6_docs()
    check_steadiness_script()
    check_steadiness_output()
    check_overview_step_count()
    check_overview_hints()
    check_bundle_includes_steadiness()
    check_readme_phase6_references()

    print("")
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s) did not pass:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All Phase 6 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
