#!/usr/bin/env python3
"""Validate Competition Track Phase 4 artifacts."""

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
# 1. Phase 4 demo docs exist
# ---------------------------------------------------------------------------
def check_phase4_docs() -> None:
    print("[1/7] Phase 4 demo docs")
    docs = [
        "docs/DEMO_FLOW_ARCHITECTURE.md",
        "docs/JUDGE_ATTENTION_STRATEGY.md",
        "docs/DEMO_ROUTE.md",
        "docs/DEMO_SCREENSHOT_PLAN.md",
        "docs/DEMO_EVIDENCE_SEQUENCING.md",
        "docs/DEMO_HONESTY_STRATEGY.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")

    flow = REPO_ROOT / "docs/DEMO_FLOW_ARCHITECTURE.md"
    if flow.exists():
        text = flow.read_text()
        check("flow has 4-minute timing", "4:00" in text or "4-minute" in text.lower())
        check("flow has 90-second condensed version", "90-Second" in text or "90-second" in text.lower())
        check("flow has 'what NOT to over-explain'", "NOT" in text)
        check("flow references /analytics", "/analytics" in text)
        check("flow references /recommendations", "/recommendations" in text)

    route = REPO_ROOT / "docs/DEMO_ROUTE.md"
    if route.exists():
        text = route.read_text()
        check("route has pre-demo checklist", "Pre-Demo Checklist" in text or "checklist" in text.lower())
        check("route has stop-by-stop sequence", "Stop 1" in text or "Stop 2" in text)
        check("route has timing estimates", "0:30" in text or "0:45" in text)
        check("route references Evidence Chain", "Evidence Chain" in text)

    judge = REPO_ROOT / "docs/JUDGE_ATTENTION_STRATEGY.md"
    if judge.exists():
        text = judge.read_text()
        check("judge strategy has high-impact screens", "High-Impact" in text or "High-impact" in text)
        check("judge strategy has misunderstanding table", "misunderstand" in text.lower())
        check("judge strategy has framing guidance", "framing" in text.lower() or "Framing" in text)

    honesty = REPO_ROOT / "docs/DEMO_HONESTY_STRATEGY.md"
    if honesty.exists():
        text = honesty.read_text()
        check("honesty strategy has verbal caveats section", "aloud" in text.lower() or "Aloud" in text)
        check("honesty strategy has framing examples", "framing" in text.lower())
        check("honesty strategy has alarm inflation reference", "alarm" in text.lower())

    evidence = REPO_ROOT / "docs/DEMO_EVIDENCE_SEQUENCING.md"
    if evidence.exists():
        text = evidence.read_text()
        check("evidence sequencing has level progression", "Level 0" in text and "Level 1" in text)
        check("evidence sequencing has anti-patterns", "Anti-Pattern" in text or "anti-pattern" in text.lower())

    screenshot = REPO_ROOT / "docs/DEMO_SCREENSHOT_PLAN.md"
    if screenshot.exists():
        text = screenshot.read_text()
        check("screenshot plan has priority 1 section", "Priority 1" in text)
        check("screenshot plan has 'what must be visible'", "must be visible" in text.lower())


# ---------------------------------------------------------------------------
# 2. Competition demo summary script
# ---------------------------------------------------------------------------
def check_demo_summary_script() -> None:
    print("[2/7] Competition demo summary script")
    script = REPO_ROOT / "scripts/build_competition_demo_summary.py"
    check("build_competition_demo_summary.py exists", script.exists(), "file missing")
    if script.exists():
        try:
            py_compile.compile(str(script), doraise=True)
            check("script compiles cleanly", True)
        except py_compile.PyCompileError as e:
            check("script compiles cleanly", False, str(e)[:100])

        text = script.read_text()
        check("script defines DIFFERENTIATORS", "DIFFERENTIATORS" in text)
        check("script defines DEMO_CAVEATS", "DEMO_CAVEATS" in text)
        check("script defines WHAT_NOT_TO_CLAIM", "WHAT_NOT_TO_CLAIM" in text)
        check("script has _validate() self-test", "_validate" in text)
        check("script outputs to reports/competition_demo_summary.md", "competition_demo_summary" in text)


# ---------------------------------------------------------------------------
# 3. Competition demo summary generates correctly
# ---------------------------------------------------------------------------
def check_demo_summary_output() -> None:
    print("[3/7] Competition demo summary output")
    result = subprocess.run(
        ["python3", "scripts/build_competition_demo_summary.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("script runs without error", result.returncode == 0, result.stderr[:200])

    output = REPO_ROOT / "reports/competition_demo_summary.md"
    check("competition_demo_summary.md generated", output.exists(), "file not created")

    if output.exists():
        text = output.read_text()
        check("summary has elevator pitch", "30-Second Elevator Pitch" in text)
        check("summary has demo route table", "Recommended Demo Route" in text)
        check("summary has differentiators", "Strongest Competition Differentiators" in text)
        check("summary has operational honesty posture", "Operational Honesty Posture" in text)
        check("summary has what NOT to claim", "What NOT to Claim" in text)
        check("summary has required verbal caveats", "Required Verbal Statements" in text)
        check("summary has high-impact screens table", "High-Impact Demo Screens" in text)

    # Also run self-test
    validate_result = subprocess.run(
        ["python3", "scripts/build_competition_demo_summary.py", "--validate"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("script --validate passes", validate_result.returncode == 0, validate_result.stdout[:100])


# ---------------------------------------------------------------------------
# 4. Phase 3 artifacts still intact
# ---------------------------------------------------------------------------
def check_phase3_artifacts() -> None:
    print("[4/7] Phase 3 artifacts still intact")
    analytics_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/analytics/page.tsx"
    if analytics_page.exists():
        text = analytics_page.read_text()
        check("analytics page has Operational Posture section", "Operational Posture" in text)
        check("analytics page uses spreadToSeverity", "spreadToSeverity" in text)
        check("analytics page imports analyticsPresentation", "analyticsPresentation" in text)

    presentation = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/analyticsPresentation.ts"
    check("analyticsPresentation.ts exists", presentation.exists(), "file missing")

    rec_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/recommendations/page.tsx"
    if rec_page.exists():
        text = rec_page.read_text()
        check("recommendations page has Evidence Chain", "Evidence Chain" in text)
        check("recommendations page has confidence bar", "Not AI-generated" in text)


# ---------------------------------------------------------------------------
# 5. Caveat visibility preserved
# ---------------------------------------------------------------------------
def check_caveat_visibility() -> None:
    print("[5/7] Caveat visibility preserved")
    caveat_file = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/caveatMessages.ts"
    check("caveatMessages.ts exists", caveat_file.exists(), "file missing")
    if caveat_file.exists():
        text = caveat_file.read_text()
        check("RC1_STANDARD_CAVEATS exported", "RC1_STANDARD_CAVEATS" in text)
        check("CAVEAT_THE_UNAVAILABLE exported", "CAVEAT_THE_UNAVAILABLE" in text)
        check("CAVEAT_ARWU_UNAVAILABLE exported", "CAVEAT_ARWU_UNAVAILABLE" in text)

    rec_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/recommendations/page.tsx"
    if rec_page.exists():
        text = rec_page.read_text()
        check("recommendations imports RC1_STANDARD_CAVEATS", "RC1_STANDARD_CAVEATS" in text)
        check("recommendations has Data Caveats section", "Data Caveats" in text)


# ---------------------------------------------------------------------------
# 6. docs/README.md references Phase 4 docs
# ---------------------------------------------------------------------------
def check_docs_readme() -> None:
    print("[6/7] docs/README.md references")
    readme = REPO_ROOT / "docs/README.md"
    check("docs/README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text()
        check("README references DEMO_FLOW_ARCHITECTURE", "DEMO_FLOW_ARCHITECTURE" in text)
        check("README references JUDGE_ATTENTION_STRATEGY", "JUDGE_ATTENTION_STRATEGY" in text)
        check("README references DEMO_ROUTE", "DEMO_ROUTE" in text)
        check("README references DEMO_HONESTY_STRATEGY", "DEMO_HONESTY_STRATEGY" in text)


# ---------------------------------------------------------------------------
# 7. Frontend still builds
# ---------------------------------------------------------------------------
def check_frontend_build() -> None:
    print("[7/7] Frontend TypeScript compile")
    web_dir = REPO_ROOT / "crawlernest" / "crawlernest-web"
    result = subprocess.run(
        ["npx", "tsc", "--noEmit", "--skipLibCheck"],
        cwd=str(web_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    check(
        "npx tsc --noEmit",
        result.returncode == 0,
        result.stdout[:300] if result.returncode != 0 else "",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Competition Track Phase 4 Validation ===\n")

    check_phase4_docs()
    print()
    check_demo_summary_script()
    print()
    check_demo_summary_output()
    print()
    check_phase3_artifacts()
    print()
    check_caveat_visibility()
    print()
    check_docs_readme()
    print()
    check_frontend_build()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
