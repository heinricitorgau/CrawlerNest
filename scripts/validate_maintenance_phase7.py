#!/usr/bin/env python3
"""Validate Phase 7 maintenance milestone artifacts."""

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
# 1. Phase 7 docs exist
# ---------------------------------------------------------------------------
def check_phase7_docs() -> None:
    print("[1/7] Phase 7 docs")
    docs = [
        "docs/OPERATIONAL_CONTINUITY_REVIEW.md",
        "docs/MAINTENANCE_CONTINUITY_MODEL.md",
        "docs/OPERATIONAL_MEMORY_DURABILITY.md",
        "docs/STABLE_DEGRADED_CONTINUITY.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")


# ---------------------------------------------------------------------------
# 2. Continuity script exists and compiles
# ---------------------------------------------------------------------------
def check_continuity_script() -> None:
    print("[2/7] Continuity script")
    script = REPO_ROOT / "scripts" / "build_maintenance_continuity_summary.py"
    check("scripts/build_maintenance_continuity_summary.py exists", script.exists(), "file missing")
    if script.exists():
        try:
            py_compile.compile(str(script), doraise=True)
            check("continuity script syntax", True)
        except py_compile.PyCompileError as exc:
            check("continuity script syntax", False, str(exc))


# ---------------------------------------------------------------------------
# 3. Continuity output contains expected sections
# ---------------------------------------------------------------------------
def check_continuity_output() -> None:
    print("[3/7] Continuity output")
    script = REPO_ROOT / "scripts" / "build_maintenance_continuity_summary.py"
    if not script.exists():
        check("continuity script runnable", False, "script missing — skipping output checks")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    check(
        "continuity script exits 0",
        result.returncode == 0,
        f"rc={result.returncode} stderr={result.stderr[:120]}",
    )
    output_file = REPO_ROOT / "reports" / "maintenance_continuity_summary.md"
    check(
        "reports/maintenance_continuity_summary.md exists",
        output_file.exists(),
        "file not written",
    )
    if output_file.exists():
        content = output_file.read_text(encoding="utf-8")
        check(
            "continuity output contains heading",
            "Maintenance Continuity Summary" in content,
            "heading missing",
        )
        check(
            "continuity output contains Stable Degraded Continuity",
            "Stable Degraded Continuity" in content,
            "section missing",
        )
        check(
            "continuity output contains Operational Memory Durability",
            "Operational Memory Durability" in content,
            "section missing",
        )
        check(
            "continuity output contains Release Honesty",
            "Release Honesty" in content,
            "section missing",
        )


# ---------------------------------------------------------------------------
# 4. Overview step count is 9/9
# ---------------------------------------------------------------------------
def check_overview_step_count() -> None:
    print("[4/7] Overview step count")
    overview = REPO_ROOT / "scripts" / "maintenance_overview.sh"
    check("maintenance_overview.sh exists", overview.exists(), "file missing")
    if overview.exists():
        text = overview.read_text(encoding="utf-8")
        check(
            "overview contains [9/9]",
            "[9/9]" in text,
            "step [9/9] not found — script may not have been updated",
        )
        check(
            "overview does not contain [8/8]",
            "[8/8]" not in text,
            "old [8/8] step label still present",
        )
        check(
            "overview references MAINTENANCE_CONTINUITY_MODEL",
            "MAINTENANCE_CONTINUITY_MODEL" in text,
            "continuity model hint missing",
        )
        check(
            "overview references build_maintenance_continuity_summary",
            "build_maintenance_continuity_summary" in text,
            "continuity step missing",
        )


# ---------------------------------------------------------------------------
# 5. Continuity script handles malformed inputs gracefully
# ---------------------------------------------------------------------------
def check_malformed_inputs() -> None:
    print("[5/7] Malformed input handling")
    import tempfile
    import json

    script = REPO_ROOT / "scripts" / "build_maintenance_continuity_summary.py"
    if not script.exists():
        check("malformed input test", False, "script missing")
        return

    with tempfile.TemporaryDirectory(prefix="crawlernest-phase7-val-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        releases = root / "releases"
        (releases / "v0.1-demo").mkdir(parents=True)

        # Malformed JSON snapshot
        (root / "latest_status.json").write_text("not valid json {{{", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--reports-dir", str(reports),
                "--snapshot-file", str(root / "latest_status.json"),
                "--releases-dir", str(releases),
                "--output", str(root / "out.md"),
            ],
            capture_output=True,
            text=True,
        )
        check(
            "malformed JSON snapshot: script exits 0",
            result.returncode == 0,
            f"rc={result.returncode}",
        )
        out_path = root / "out.md"
        check(
            "malformed JSON snapshot: output written",
            out_path.exists(),
            "output file not created",
        )
        if out_path.exists():
            content = out_path.read_text(encoding="utf-8")
            check(
                "malformed JSON snapshot: warns about malformed json",
                "malformed json" in content.lower() or "missing" in content.lower(),
                "no warning in output",
            )

        # Missing all reports
        (root / "latest_status.json").write_text(
            json.dumps({"snapshot_timestamp": "2026-05-22T15:00:00+00:00", "source_counts": []}),
            encoding="utf-8",
        )
        result2 = subprocess.run(
            [
                sys.executable,
                str(script),
                "--reports-dir", str(reports),
                "--snapshot-file", str(root / "latest_status.json"),
                "--releases-dir", str(releases),
                "--output", str(root / "out2.md"),
            ],
            capture_output=True,
            text=True,
        )
        check(
            "missing reports: script exits 0",
            result2.returncode == 0,
            f"rc={result2.returncode}",
        )


# ---------------------------------------------------------------------------
# 6. Bundle script includes continuity summary
# ---------------------------------------------------------------------------
def check_bundle_includes_continuity() -> None:
    print("[6/7] Bundle script includes continuity summary")
    bundle = REPO_ROOT / "scripts" / "build_demo_bundle.sh"
    check("build_demo_bundle.sh exists", bundle.exists(), "file missing")
    if bundle.exists():
        text = bundle.read_text(encoding="utf-8")
        check(
            "bundle script copies maintenance_continuity_summary",
            "maintenance_continuity_summary" in text,
            "continuity summary not included in bundle",
        )
        check(
            "bundle heredoc references OPERATIONAL_MEMORY_DURABILITY",
            "OPERATIONAL_MEMORY_DURABILITY" in text,
            "durability reference missing from OPERATIONAL_ARTIFACTS.md heredoc",
        )
        check(
            "bundle heredoc references STABLE_DEGRADED_CONTINUITY",
            "STABLE_DEGRADED_CONTINUITY" in text,
            "stable degraded continuity reference missing",
        )
        check(
            "bundle heredoc references MAINTENANCE_CONTINUITY_MODEL",
            "MAINTENANCE_CONTINUITY_MODEL" in text,
            "continuity model reference missing",
        )


# ---------------------------------------------------------------------------
# 7. Root README references Phase 7 docs
# ---------------------------------------------------------------------------
def check_readme_phase7_references() -> None:
    print("[7/7] README Phase 7 references")
    readme = REPO_ROOT / "README.md"
    check("README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        check(
            "README references OPERATIONAL_CONTINUITY_REVIEW",
            "OPERATIONAL_CONTINUITY_REVIEW" in text,
            "continuity review doc not listed",
        )
        check(
            "README references MAINTENANCE_CONTINUITY_MODEL",
            "MAINTENANCE_CONTINUITY_MODEL" in text,
            "continuity model doc not listed",
        )
        check(
            "README references STABLE_DEGRADED_CONTINUITY",
            "STABLE_DEGRADED_CONTINUITY" in text,
            "stable degraded continuity doc not listed",
        )
        check(
            "README references build_maintenance_continuity_summary",
            "build_maintenance_continuity_summary" in text,
            "continuity summary script not listed",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("Phase 7 Validation")
    print("==================")

    check_phase7_docs()
    check_continuity_script()
    check_continuity_output()
    check_overview_step_count()
    check_malformed_inputs()
    check_bundle_includes_continuity()
    check_readme_phase7_references()

    print("")
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s) did not pass:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("All Phase 7 checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
