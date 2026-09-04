#!/usr/bin/env python3
"""Validate Competition Demo Production Phase 1 artifacts."""

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
# 1. Production docs exist and contain required content
# ---------------------------------------------------------------------------
def check_production_docs() -> None:
    print("[1/7] Production docs exist")
    docs = [
        "docs/DEMO_PRODUCTION_RUNBOOK.md",
        "docs/DEMO_BROWSER_STATE.md",
        "docs/SCREENSHOT_CAPTURE_WORKFLOW.md",
        "docs/DEMO_RECORDING_PREP.md",
        "docs/DEMO_DATA_FREEZE.md",
        "docs/DEMO_FAILURE_RECOVERY.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")

    runbook = REPO_ROOT / "docs/DEMO_PRODUCTION_RUNBOOK.md"
    if runbook.exists():
        text = runbook.read_text()
        check("runbook has environment startup section", "Environment Startup" in text or "environment startup" in text.lower())
        check("runbook has pre-demo checks", "Pre-Demo" in text or "pre-demo" in text.lower())
        check("runbook has preparation timeline", "Preparation" in text or "preparation" in text.lower())
        check("runbook has failure recovery reference", "DEMO_FAILURE_RECOVERY" in text)
        check("runbook references backend startup command", "spring-boot:run" in text)
        check("runbook references frontend startup command", "npm run dev" in text)

    browser = REPO_ROOT / "docs/DEMO_BROWSER_STATE.md"
    if browser.exists():
        text = browser.read_text()
        check("browser state has tabs to open", "Tabs to Open" in text or "tabs to open" in text.lower())
        check("browser state has tabs not to open", "Tabs NOT to Open" in text or "not to open" in text.lower())
        check("browser state has zoom guidance", "zoom" in text.lower())
        check("browser state has avoid-during-demo section", "Avoid During Demo" in text or "avoid during demo" in text.lower())
        check("browser state references light mode", "light mode" in text.lower() or "Light mode" in text)

    screenshot = REPO_ROOT / "docs/SCREENSHOT_CAPTURE_WORKFLOW.md"
    if screenshot.exists():
        text = screenshot.read_text()
        check("screenshot workflow has Priority 1 section", "Priority 1" in text)
        check("screenshot workflow has capture purpose entries", "Capture purpose" in text or "capture purpose" in text.lower())
        check("screenshot workflow has must-be-visible entries", "Must be visible" in text or "must be visible" in text.lower())
        check("screenshot workflow references Evidence Chain", "Evidence Chain" in text)
        check("screenshot workflow has fallback use section", "Fallback" in text or "fallback" in text.lower())

    recording = REPO_ROOT / "docs/DEMO_RECORDING_PREP.md"
    if recording.exists():
        text = recording.read_text()
        check("recording prep has screen resolution", "resolution" in text.lower() or "1080" in text)
        check("recording prep has narration pacing", "narration" in text.lower() or "Narration" in text)
        check("recording prep has offline-safe section", "offline" in text.lower() or "Offline" in text)
        check("recording prep has if-demo-breaks guidance", "breaks" in text.lower() or "recovery" in text.lower())

    freeze = REPO_ROOT / "docs/DEMO_DATA_FREEZE.md"
    if freeze.exists():
        text = freeze.read_text()
        check("data freeze has stable degraded section", "Stable Degraded" in text or "stable degraded" in text.lower())
        check("data freeze explains why stable > unstable", "preferable" in text.lower() or "stable degraded" in text.lower())
        check("data freeze references QS freeze", "QS" in text and ("Freeze" in text or "freeze" in text.lower() or "Frozen" in text))
        check("data freeze references THE/ARWU freeze", "THE" in text and "ARWU" in text)

    recovery = REPO_ROOT / "docs/DEMO_FAILURE_RECOVERY.md"
    if recovery.exists():
        text = recovery.read_text()
        check("recovery guide has backend down section", "backend" in text.lower() and "down" in text.lower())
        check("recovery guide has stale session section", "session" in text.lower())
        check("recovery guide has fallback priority order", "Fallback Priority" in text or "fallback priority" in text.lower())
        check("recovery guide has calm recovery principle", "calm" in text.lower() or "Calm" in text)
        check("recovery guide has no panic remediation", "panic" not in text.lower())


# ---------------------------------------------------------------------------
# 2. Demo readiness summary script exists and compiles
# ---------------------------------------------------------------------------
def check_readiness_script() -> None:
    print("[2/7] Demo readiness summary script")
    script = REPO_ROOT / "scripts" / "build_demo_readiness_summary.py"
    check("build_demo_readiness_summary.py exists", script.exists(), "file missing")
    if script.exists():
        try:
            py_compile.compile(str(script), doraise=True)
            check("script compiles cleanly", True)
        except py_compile.PyCompileError as exc:
            check("script compiles cleanly", False, str(exc)[:100])

        text = script.read_text()
        check("script defines REQUIRED_VERBAL_CAVEATS", "REQUIRED_VERBAL_CAVEATS" in text)
        check("script defines WHAT_NOT_TO_CLAIM", "WHAT_NOT_TO_CLAIM" in text)
        check("script defines DEMO_PREP_CHECKLIST", "DEMO_PREP_CHECKLIST" in text)
        check("script defines DEMO_SURFACES", "DEMO_SURFACES" in text)
        check("script has _validate() self-test", "_validate" in text)
        check("script has readonly guarantee section", "Readonly Guarantee" in text or "readonly" in text.lower())


# ---------------------------------------------------------------------------
# 3. Demo readiness summary generates correctly
# ---------------------------------------------------------------------------
def check_readiness_output() -> None:
    print("[3/7] Demo readiness summary output")
    result = subprocess.run(
        ["python3", "scripts/build_demo_readiness_summary.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("script runs without error", result.returncode == 0, result.stderr[:200])

    output = REPO_ROOT / "reports" / "demo_readiness_summary.md"
    check("demo_readiness_summary.md generated", output.exists(), "file not created")

    if output.exists():
        text = output.read_text()
        check("summary has readiness posture section", "Demo Readiness Posture" in text)
        check("summary has demo surfaces table", "Strongest Demo Surfaces" in text)
        check("summary has prep checklist", "Preparation Checklist" in text or "preparation checklist" in text.lower())
        check("summary has operational posture section", "Operational Posture" in text)
        check("summary has required verbal caveats", "Required Verbal Statements" in text)
        check("summary has what NOT to claim", "What NOT to Claim" in text)
        check("summary has fallback readiness", "Fallback Readiness" in text)
        check("summary has readonly guarantee", "Readonly Guarantee" in text)

    # Self-test
    validate_result = subprocess.run(
        ["python3", "scripts/build_demo_readiness_summary.py", "--validate"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("script --validate passes", validate_result.returncode == 0, validate_result.stdout[:100])


# ---------------------------------------------------------------------------
# 4. Caveat wording preserved (no regression from Phase 3/4)
# ---------------------------------------------------------------------------
def check_caveat_preservation() -> None:
    print("[4/7] Caveat wording preserved")
    caveat_file = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/caveatMessages.ts"
    check("caveatMessages.ts exists", caveat_file.exists(), "file missing")
    if caveat_file.exists():
        text = caveat_file.read_text()
        check("RC1_STANDARD_CAVEATS exported", "RC1_STANDARD_CAVEATS" in text)
        check("CAVEAT_THE_UNAVAILABLE present", "CAVEAT_THE_UNAVAILABLE" in text)
        check("CAVEAT_ARWU_UNAVAILABLE present", "CAVEAT_ARWU_UNAVAILABLE" in text)

    rec_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/recommendations/page.tsx"
    if rec_page.exists():
        text = rec_page.read_text()
        check("recommendations imports RC1_STANDARD_CAVEATS", "RC1_STANDARD_CAVEATS" in text)
        check("recommendations has Evidence Chain heading", "Evidence Chain" in text)
        check("recommendations has Data Caveats section", "Data Caveats" in text)
        check("recommendations has Not AI-generated text", "Not AI-generated" in text)

    analytics_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/analytics/page.tsx"
    if analytics_page.exists():
        text = analytics_page.read_text()
        check("analytics has Operational Posture section", "Operational Posture" in text)
        check("analytics uses spreadToSeverity", "spreadToSeverity" in text)


# ---------------------------------------------------------------------------
# 5. No fake AI wording introduced
# ---------------------------------------------------------------------------
def check_no_fake_ai() -> None:
    print("[5/7] No fake AI wording")
    pages_to_check = [
        "crawlernest/crawlernest-web/src/app/analytics/page.tsx",
        "crawlernest/crawlernest-web/src/app/recommendations/page.tsx",
    ]
    forbidden_phrases = [
        "AI-powered",
        "AI powered",
        "powered by AI",
        "AI-generated recommendation",
        "real-time intelligence",
        "predictive AI",
        "machine learning model",
        "neural network",
    ]
    for page_path in pages_to_check:
        path = REPO_ROOT / page_path
        if path.exists():
            text = path.read_text().lower()
            for phrase in forbidden_phrases:
                check(
                    f"{page_path.split('/')[-1]} does not contain '{phrase}'",
                    phrase.lower() not in text,
                    f"forbidden phrase found: {phrase}",
                )

    # The disclaimer moved out of the readiness script into the shared posture
    # module when all five generators stopped keeping private copies of it.
    # Checked for intent rather than for one phrase: the old assertion passed on
    # the words "no ML model", which stopped being true once the platform shipped
    # two of them.
    posture = REPO_ROOT / "scripts" / "_release_posture.py"
    if posture.exists():
        text = posture.read_text()
        check(
            "posture module tells the presenter recommendation scoring is deterministic",
            "AI-powered" in text and "deterministic" in text,
            "WHAT_NOT_TO_CLAIM no longer carries the deterministic-scoring disclaimer",
        )
        check(
            "posture module does not deny the modelling layer",
            "no ML model" not in text.lower(),
            "the platform ships two models; a demo script must not say otherwise",
        )


# ---------------------------------------------------------------------------
# 6. Frontend TypeScript compiles
# ---------------------------------------------------------------------------
def check_frontend_build() -> None:
    print("[6/7] Frontend TypeScript compile")
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
# 7. docs/README.md references Phase 1 production docs
# ---------------------------------------------------------------------------
def check_readme_references() -> None:
    print("[7/7] docs/README.md references Phase 1 docs")
    readme = REPO_ROOT / "docs" / "README.md"
    check("docs/README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text()
        check("README references DEMO_PRODUCTION_RUNBOOK", "DEMO_PRODUCTION_RUNBOOK" in text)
        check("README references DEMO_BROWSER_STATE", "DEMO_BROWSER_STATE" in text)
        check("README references SCREENSHOT_CAPTURE_WORKFLOW", "SCREENSHOT_CAPTURE_WORKFLOW" in text)
        check("README references DEMO_RECORDING_PREP", "DEMO_RECORDING_PREP" in text)
        check("README references DEMO_DATA_FREEZE", "DEMO_DATA_FREEZE" in text)
        check("README references DEMO_FAILURE_RECOVERY", "DEMO_FAILURE_RECOVERY" in text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Competition Demo Production Phase 1 Validation ===\n")

    check_production_docs()
    print()
    check_readiness_script()
    print()
    check_readiness_output()
    print()
    check_caveat_preservation()
    print()
    check_no_fake_ai()
    print()
    check_frontend_build()
    print()
    check_readme_references()

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
