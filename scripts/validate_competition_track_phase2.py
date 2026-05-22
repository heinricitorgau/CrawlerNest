#!/usr/bin/env python3
"""Validate Competition Track Phase 2 artifacts."""

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
# 1. Phase 2 docs exist
# ---------------------------------------------------------------------------
def check_phase2_docs() -> None:
    print("[1/7] Phase 2 docs")
    docs = [
        "docs/RECOMMENDATION_EVIDENCE_MODEL.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")

    narrative = REPO_ROOT / "docs/COMPETITION_DEMO_NARRATIVE.md"
    check("COMPETITION_DEMO_NARRATIVE.md exists", narrative.exists(), "file missing")
    if narrative.exists():
        text = narrative.read_text()
        check("narrative has evidence section", "Evidence-Backed Recommendations" in text)
        check("narrative references evidence model", "RECOMMENDATION_EVIDENCE_MODEL" in text)
        check("narrative states no black-box AI", "not black-box" in text.lower() or "not a black-box" in text.lower() or "not black-box" in text.lower())


# ---------------------------------------------------------------------------
# 2. Caveat messages helper
# ---------------------------------------------------------------------------
def check_caveat_messages() -> None:
    print("[2/7] Caveat messages helper")
    ts_file = REPO_ROOT / "crawlernest/crawlernest-web/src/lib/caveatMessages.ts"
    check("caveatMessages.ts exists", ts_file.exists(), "file missing")
    if ts_file.exists():
        text = ts_file.read_text()
        check("defines CAVEAT_QS_STALE", "CAVEAT_QS_STALE" in text)
        check("defines CAVEAT_THE_UNAVAILABLE", "CAVEAT_THE_UNAVAILABLE" in text)
        check("defines CAVEAT_ARWU_UNAVAILABLE", "CAVEAT_ARWU_UNAVAILABLE" in text)
        check("defines RC1_STANDARD_CAVEATS", "RC1_STANDARD_CAVEATS" in text)


# ---------------------------------------------------------------------------
# 3. Java evidence service and endpoint
# ---------------------------------------------------------------------------
def check_java_evidence() -> None:
    print("[3/7] Java evidence service and endpoint")
    service = REPO_ROOT / "crawlernest/servise_for_java/src/main/java/clawer/service/RecommendationEvidenceService.java"
    check("RecommendationEvidenceService.java exists", service.exists(), "file missing")
    if service.exists():
        text = service.read_text()
        check("service uses JdbcTemplate", "JdbcTemplate" in text)
        check("service has getEvidence method", "getEvidence" in text)
        check("service returns caveats", "caveats" in text)
        check("service returns source_coverage", "source_coverage" in text)
        check("service returns confidence_evidence", "confidence_evidence" in text)
        check("service returns 404 for unknown university", "NOT_FOUND" in text or "HttpStatus.NOT_FOUND" in text)
        check("service is readonly (no INSERT/UPDATE/DELETE)", "INSERT" not in text and "UPDATE" not in text and "DELETE" not in text)

    controller = REPO_ROOT / "crawlernest/servise_for_java/src/main/java/clawer/api/RecommendationController.java"
    if controller.exists():
        text = controller.read_text()
        check("controller has /explain endpoint", '"/explain"' in text or "explain" in text)
        check("controller injects RecommendationEvidenceService", "RecommendationEvidenceService" in text)
        check("controller marks explain readonly", '"readonly"' in text)


# ---------------------------------------------------------------------------
# 4. Java compiles cleanly
# ---------------------------------------------------------------------------
def check_java_compile() -> None:
    print("[4/7] Java compile")
    java_dir = REPO_ROOT / "crawlernest" / "servise_for_java"
    mvnw = java_dir / "mvnw"
    if not mvnw.exists():
        check("mvnw exists", False, "not found")
        return
    result = subprocess.run(
        ["./mvnw", "compile", "-q"],
        cwd=str(java_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    check("./mvnw compile -q", result.returncode == 0, result.stderr[:200] if result.returncode != 0 else "")


# ---------------------------------------------------------------------------
# 5. Frontend explain route
# ---------------------------------------------------------------------------
def check_frontend_explain() -> None:
    print("[5/7] Frontend explain route")
    route = REPO_ROOT / "crawlernest/crawlernest-web/src/app/api/recommendations/explain/route.ts"
    check("explain route.ts exists", route.exists(), "file missing")
    if route.exists():
        text = route.read_text()
        check("explain route proxies to backend", "/api/v1/recommendations/explain" in text)
        check("explain route uses LOCAL_BACKEND_CANDIDATES", "LOCAL_BACKEND_CANDIDATES" in text)


# ---------------------------------------------------------------------------
# 6. Frontend recommendations page
# ---------------------------------------------------------------------------
def check_frontend_recommendations() -> None:
    print("[6/7] Frontend recommendations page")
    page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/recommendations/page.tsx"
    check("recommendations/page.tsx exists", page.exists(), "file missing")
    if page.exists():
        text = page.read_text()
        check("page imports RC1_STANDARD_CAVEATS", "RC1_STANDARD_CAVEATS" in text)
        check("page has ExplainPanel component", "ExplainPanel" in text)
        check("page has collapsible Why this recommendation", "Why this recommendation" in text)
        check("page has Source Coverage section", "Source Coverage" in text)
        check("page has Data Caveats section", "Data Caveats" in text)
        check("page fetches from explain endpoint", "/api/recommendations/explain" in text)
        check("page has fallback for unavailable backend", "error" in text.lower())

    saved_page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/saved-recommendations/page.tsx"
    check("saved-recommendations/page.tsx exists", saved_page.exists(), "file missing")
    if saved_page.exists():
        text = saved_page.read_text()
        check("saved page imports RC1_STANDARD_CAVEATS", "RC1_STANDARD_CAVEATS" in text)
        check("saved page has Evidence Details section", "Evidence Details" in text)
        check("saved page handles missing evidence", "Evidence details were not stored" in text)


# ---------------------------------------------------------------------------
# 7. README references Phase 2
# ---------------------------------------------------------------------------
def check_readme() -> None:
    print("[7/7] README phase 2 references")
    readme = REPO_ROOT / "README.md"
    check("README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text()
        check("README references RECOMMENDATION_EVIDENCE_MODEL", "RECOMMENDATION_EVIDENCE_MODEL" in text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Competition Track Phase 2 Validation ===\n")

    check_phase2_docs()
    print()
    check_caveat_messages()
    print()
    check_java_evidence()
    print()
    check_java_compile()
    print()
    check_frontend_explain()
    print()
    check_frontend_recommendations()
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
