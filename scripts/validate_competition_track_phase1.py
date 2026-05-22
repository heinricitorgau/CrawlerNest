#!/usr/bin/env python3
"""Validate Competition Track Phase 1 artifacts."""

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
# 1. Competition Track docs exist
# ---------------------------------------------------------------------------
def check_competition_docs() -> None:
    print("[1/7] Competition Track docs")
    docs = [
        "docs/COMPETITION_TRACK.md",
        "docs/ANALYTICS_SURFACE_PLAN.md",
        "docs/ANALYTICS_EXPLAINABILITY.md",
        "docs/COMPETITION_DEMO_NARRATIVE.md",
    ]
    for doc in docs:
        path = REPO_ROOT / doc
        check(doc, path.exists(), "file missing")


# ---------------------------------------------------------------------------
# 2. Java analytics backend files exist
# ---------------------------------------------------------------------------
def check_java_backend() -> None:
    print("[2/7] Java analytics backend")
    java_files = [
        "crawlernest/servise_for_java/src/main/java/clawer/api/AnalyticsController.java",
        "crawlernest/servise_for_java/src/main/java/clawer/service/AnalyticsService.java",
    ]
    for f in java_files:
        path = REPO_ROOT / f
        check(f.split("/")[-1], path.exists(), "file missing")

    # AnalyticsController must reference both endpoints
    controller = REPO_ROOT / "crawlernest/servise_for_java/src/main/java/clawer/api/AnalyticsController.java"
    if controller.exists():
        text = controller.read_text()
        check("controller has /ranking-trends endpoint", "/ranking-trends" in text)
        check("controller has /source-disagreement endpoint", "/source-disagreement" in text)
        check("controller uses readonly metadata", '"readonly"' in text)
        check("controller discloses caveats", "caveats" in text)

    # AnalyticsService must have real JdbcTemplate implementation
    service = REPO_ROOT / "crawlernest/servise_for_java/src/main/java/clawer/service/AnalyticsService.java"
    if service.exists():
        text = service.read_text()
        check("service uses JdbcTemplate", "JdbcTemplate" in text)
        check("service queries aggregated_rankings", "aggregated_rankings" in text)
        check("service handles single_year_only", "singleYearOnly" in text or "single_year_only" in text)
        check("service computes rank_delta", "rank_delta" in text or "rankDelta" in text or "delta" in text.lower())


# ---------------------------------------------------------------------------
# 3. Java compiles cleanly
# ---------------------------------------------------------------------------
def check_java_compile() -> None:
    print("[3/7] Java compile")
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
# 4. Next.js proxy routes exist
# ---------------------------------------------------------------------------
def check_frontend_routes() -> None:
    print("[4/7] Frontend API proxy routes")
    routes = [
        "crawlernest/crawlernest-web/src/app/api/analytics/ranking-trends/route.ts",
        "crawlernest/crawlernest-web/src/app/api/analytics/source-disagreement/route.ts",
    ]
    for r in routes:
        path = REPO_ROOT / r
        check(r.split("/")[-2] + "/route.ts", path.exists(), "file missing")
        if path.exists():
            text = path.read_text()
            check(f"{r.split('/')[-2]} proxies to backend", "/api/v1/analytics/" in text)
            check(f"{r.split('/')[-2]} uses LOCAL_BACKEND_CANDIDATES", "LOCAL_BACKEND_CANDIDATES" in text)


# ---------------------------------------------------------------------------
# 5. Analytics frontend page exists
# ---------------------------------------------------------------------------
def check_analytics_page() -> None:
    print("[5/7] Analytics frontend page")
    page = REPO_ROOT / "crawlernest/crawlernest-web/src/app/analytics/page.tsx"
    check("analytics/page.tsx exists", page.exists(), "file missing")
    if page.exists():
        text = page.read_text()
        check("page is client component", '"use client"' in text)
        check("page fetches ranking-trends", "/api/analytics/ranking-trends" in text)
        check("page fetches source-disagreement", "/api/analytics/source-disagreement" in text)
        check("page has Ranking Trends section", "Ranking Trends" in text)
        check("page has Source Disagreement section", "Source Disagreement" in text)
        check("page has Source Coverage section", "Source Coverage" in text)
        check("page has Analytics Caveats section", "Analytics Caveats" in text)
        check("page handles single_year_only", "single_year_only" in text)
        check("page surfaces caveats from API", "allCaveats" in text or "caveats" in text)


# ---------------------------------------------------------------------------
# 6. NavBar has Analytics link
# ---------------------------------------------------------------------------
def check_navbar() -> None:
    print("[6/7] NavBar Analytics link")
    navbar = REPO_ROOT / "crawlernest/crawlernest-web/src/components/NavBar.tsx"
    check("NavBar.tsx exists", navbar.exists(), "file missing")
    if navbar.exists():
        text = navbar.read_text()
        check("NavBar has Analytics nav link", '"Analytics"' in text or "'Analytics'" in text)
        check("NavBar links to /analytics", '"/analytics"' in text or "'/analytics'" in text)


# ---------------------------------------------------------------------------
# 7. README references competition track
# ---------------------------------------------------------------------------
def check_readme() -> None:
    print("[7/7] README competition track references")
    readme = REPO_ROOT / "README.md"
    check("README.md exists", readme.exists(), "file missing")
    if readme.exists():
        text = readme.read_text()
        check("README references COMPETITION_TRACK", "COMPETITION_TRACK" in text)
        check("README references ANALYTICS_SURFACE_PLAN", "ANALYTICS_SURFACE_PLAN" in text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Competition Track Phase 1 Validation ===\n")

    check_competition_docs()
    print()
    check_java_backend()
    print()
    check_java_compile()
    print()
    check_frontend_routes()
    print()
    check_analytics_page()
    print()
    check_navbar()
    print()
    check_readme()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        total = sum([
            4,   # docs
            9,   # java backend
            1,   # compile
            6,   # frontend routes
            10,  # analytics page
            2,   # navbar
            2,   # readme
        ])
        print(f"All checks passed ({total} assertions).")
        sys.exit(0)


if __name__ == "__main__":
    main()
