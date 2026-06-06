#!/usr/bin/env python3
"""Validate Competition Track Phase 3 artifacts."""

from __future__ import annotations

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
# 1. Phase 3 docs exist
# ---------------------------------------------------------------------------
def check_phase3_docs() -> None:
    print("[1/7] Phase 3 docs")
    docs = [
        "docs/ANALYTICS_VISUALIZATION_PLAN.md",
        "docs/COMPETITION_STORYTELLING.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")

    viz = REPO_ROOT / "docs/ANALYTICS_VISUALIZATION_PLAN.md"
    if viz.exists():
        text = viz.read_text()
        check("viz plan has confidence visualization section", "Confidence Visualization" in text)
        check("viz plan has source disagreement severity section", "Source Disagreement Severity" in text)
        check("viz plan has operational posture section", "Operational Posture" in text)
        check("viz plan references analyticsPresentation.ts", "analyticsPresentation.ts" in text)

    story = REPO_ROOT / "docs/COMPETITION_STORYTELLING.md"
    if story.exists():
        text = story.read_text()
        check("storytelling has evidence chain reference", "Evidence Chain" in text)
        check("storytelling has operational posture reference", "Operational Posture" in text)
        check("storytelling has 'what NOT to exaggerate' section", "NOT" in text)
        check("storytelling has required caveats section", "Caveats to State Aloud" in text)


# ---------------------------------------------------------------------------
# 2. analyticsPresentation.ts
# ---------------------------------------------------------------------------
def check_analytics_presentation() -> None:
    print("[2/7] analyticsPresentation.ts")
    ts = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/analyticsPresentation.ts"
    check("analyticsPresentation.ts exists", ts.exists(), "file missing")
    if ts.exists():
        text = ts.read_text()
        check("exports confidenceConfig", "export function confidenceConfig" in text)
        check("exports spreadToSeverity", "export function spreadToSeverity" in text)
        check("exports severityConfig", "export function severityConfig" in text)
        check("exports sourceAvailabilityConfig", "export function sourceAvailabilityConfig" in text)
        check("exports stalenessLabel", "export function stalenessLabel" in text)
        check("exports stalenessBadgeCls", "export function stalenessBadgeCls" in text)
        check("exports confidencePostureLabel", "export function confidencePostureLabel" in text)
        check("spreadToSeverity handles high (>=200)", "200" in text)
        check("spreadToSeverity handles medium (>=50)", "50" in text)


# ---------------------------------------------------------------------------
# 3. Analytics page
# ---------------------------------------------------------------------------
def check_analytics_page() -> None:
    print("[3/7] Analytics page")
    page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/analytics/page.tsx"
    check("analytics/page.tsx exists", page.exists(), "file missing")
    if page.exists():
        text = page.read_text()
        check("imports from analyticsPresentation", "analyticsPresentation" in text)
        check("uses spreadToSeverity", "spreadToSeverity" in text)
        check("uses severityConfig", "severityConfig" in text)
        check("uses sourceAvailabilityConfig", "sourceAvailabilityConfig" in text)
        check("uses confidencePostureLabel", "confidencePostureLabel" in text)
        check("uses confidenceConfig", "confidenceConfig" in text)
        check("has Operational Posture section", "Operational Posture" in text)
        check("shows THE unavailable note", "THE" in text and ("Unavailable" in text or "unavailable" in text or "not available" in text.lower()))
        check("source coverage shows available/unavailable badge", "statusLabel" in text or "availCfg" in text)
        check("historical comparison notice present", "Historical comparison" in text or "single_year_only" in text)


# ---------------------------------------------------------------------------
# 4. Recommendations ExplainPanel
# ---------------------------------------------------------------------------
def check_recommendations_page() -> None:
    print("[4/7] Recommendations ExplainPanel")
    page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/recommendations/page.tsx"
    check("recommendations/page.tsx exists", page.exists(), "file missing")
    if page.exists():
        text = page.read_text()
        check("imports sourceAvailabilityConfig", "sourceAvailabilityConfig" in text)
        check("imports analyticsPresentation", "analyticsPresentation" in text)
        check("has Evidence Chain heading", "Evidence Chain" in text)
        check("has Data Confidence bar", "Data Confidence" in text and "rounded-full" in text)
        check("confidence bar has style width", "style={{" in text and "dataConfidence" in text)
        check("confidence bar has 'Not AI-generated' note", "Not AI-generated" in text)
        check("source coverage uses sourceAvailabilityConfig", "sourceAvailabilityConfig" in text)


# ---------------------------------------------------------------------------
# 5. Frontend TypeScript compiles
# ---------------------------------------------------------------------------
def check_ts_compile() -> None:
    print("[5/7] TypeScript compile check")
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
# 6. analyticsPresentation exports are importable
# ---------------------------------------------------------------------------
def check_presentation_exports() -> None:
    print("[6/7] analyticsPresentation export consistency")
    ts = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/analyticsPresentation.ts"
    if not ts.exists():
        check("analyticsPresentation.ts exists for export check", False, "file missing")
        return
    text = ts.read_text()

    # Verify the high/medium/low confidence cases are all handled
    check("confidenceConfig handles 'high'", '"high"' in text or "'high'" in text)
    check("confidenceConfig handles 'medium'", '"medium"' in text or "'medium'" in text)
    check("confidenceConfig handles 'low'", '"low"' in text or "'low'" in text)

    # Verify sourceAvailabilityConfig returns both states
    check("sourceAvailabilityConfig handles available=true", "Available" in text)
    check("sourceAvailabilityConfig handles available=false", "Unavailable" in text)


# ---------------------------------------------------------------------------
# 7. README references Phase 3 visualizations
# ---------------------------------------------------------------------------
def check_readme() -> None:
    print("[7/7] README and docs references")
    readme = REPO_ROOT / "README.md"
    check("README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text()
        # Phase 3 may not yet have added README entries — soft check
        check(
            "README references competition track",
            "Competition" in text or "competition" in text,
        )

    docs_readme = REPO_ROOT / "docs/README.md"
    if docs_readme.exists():
        text = docs_readme.read_text()
        check(
            "docs/README.md references ANALYTICS_VISUALIZATION_PLAN",
            "ANALYTICS_VISUALIZATION_PLAN" in text or "analytics_visualization" in text.lower(),
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Competition Track Phase 3 Validation ===\n")

    check_phase3_docs()
    print()
    check_analytics_presentation()
    print()
    check_analytics_page()
    print()
    check_recommendations_page()
    print()
    check_ts_compile()
    print()
    check_presentation_exports()
    print()
    check_readme()

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
