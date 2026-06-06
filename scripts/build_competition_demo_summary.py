#!/usr/bin/env python3
"""Build competition demo summary for presenter use.

Readonly: reads existing docs and generates a concise presenter-friendly report.
No database access. No external API calls.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_FILE = REPORTS_DIR / "competition_demo_summary.md"

# ── Static presenter content ──────────────────────────────────────────────────

DIFFERENTIATORS = [
    (
        "Explainable recommendations",
        "Evidence Chain shows stored algorithm outputs — not AI-generated text. "
        "Formula documented in docs/RECOMMENDATION_EVIDENCE_MODEL.md.",
    ),
    (
        "Source disagreement visibility",
        "Rank spread classified as High / Medium / Low severity (≥200 / ≥50 / <50). "
        "Disagreement is surfaced, not suppressed.",
    ),
    (
        "Source availability honesty",
        "THE and ARWU shown as Unavailable on the main analytics page, in source "
        "coverage, and in every recommendation evidence panel.",
    ),
    (
        "Derived confidence scoring",
        "Confidence = completeness (65%) + source agreement (35%). "
        "Formula is version-tracked and reproducible.",
    ),
    (
        "Unconditional caveats",
        "Data caveats appear on every recommendation result. "
        "They cannot be dismissed or suppressed by a cleaner result.",
    ),
    (
        "Operational posture surface",
        "System self-discloses data state on the main analytics page. "
        "No hidden confidence inflation.",
    ),
]

DEMO_CAVEATS = [
    ("Data freshness", "QS data ingested at RC-1 packaging (~354 hours ago)."),
    ("Source coverage", "THE and ARWU data not available at RC-1. Single-source only."),
    ("Subject rankings", "Subject ranking data incomplete at RC-1."),
    ("Trend analysis", "Single year of aggregated data; year-over-year deltas not available."),
    ("Deployment", "Localhost demonstration; not production-scale."),
]

WHAT_NOT_TO_CLAIM = [
    "AI-powered recommendations (scoring is deterministic, no ML model used)",
    "Real-time data (batch ingestion only)",
    "Multi-source agreement analysis (only QS available at RC-1)",
    "Comprehensive subject rankings (data incomplete at RC-1)",
    "Predictive rank forecasting (no historical depth)",
    "AI-generated confidence scores (formula-derived only)",
    "Production-scale deployment (localhost demo, RC-1 scope)",
]

REQUIRED_VERBAL_CAVEATS = [
    "The ranking data was ingested at RC-1 packaging — approximately 354 hours ago.",
    "THE and ARWU data are not available at RC-1. All rankings reflect QS source only.",
    "Subject ranking coverage is incomplete at RC-1.",
    "This is a localhost demonstration. Architecture is production-ready; RC-1 scope is intentional.",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return default


def doc_exists(filename: str) -> bool:
    return (REPO_ROOT / "docs" / filename).exists()


def check_doc_status() -> dict[str, bool]:
    return {
        "DEMO_FLOW_ARCHITECTURE.md": doc_exists("DEMO_FLOW_ARCHITECTURE.md"),
        "DEMO_ROUTE.md": doc_exists("DEMO_ROUTE.md"),
        "JUDGE_ATTENTION_STRATEGY.md": doc_exists("JUDGE_ATTENTION_STRATEGY.md"),
        "DEMO_EVIDENCE_SEQUENCING.md": doc_exists("DEMO_EVIDENCE_SEQUENCING.md"),
        "DEMO_HONESTY_STRATEGY.md": doc_exists("DEMO_HONESTY_STRATEGY.md"),
        "DEMO_SCREENSHOT_PLAN.md": doc_exists("DEMO_SCREENSHOT_PLAN.md"),
        "COMPETITION_DEMO_NARRATIVE.md": doc_exists("COMPETITION_DEMO_NARRATIVE.md"),
        "RECOMMENDATION_EVIDENCE_MODEL.md": doc_exists("RECOMMENDATION_EVIDENCE_MODEL.md"),
        "COMPETITION_STORYTELLING.md": doc_exists("COMPETITION_STORYTELLING.md"),
        "ANALYTICS_VISUALIZATION_PLAN.md": doc_exists("ANALYTICS_VISUALIZATION_PLAN.md"),
    }


# ── Report builder ─────────────────────────────────────────────────────────────

def build_report() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc_status = check_doc_status()
    all_docs_present = all(doc_status.values())

    lines: list[str] = []

    lines += [
        "# Competition Demo Summary",
        "",
        f"Generated: {now}",
        "",
        "> This summary is generated from static competition docs.",
        "> Readonly. No database access. No external API calls.",
        "",
        "---",
        "",
    ]

    # ── 30-second elevator pitch ──────────────────────────────────────────
    lines += [
        "## 30-Second Elevator Pitch",
        "",
        '> "University rankings are opaque — students see a number, not the evidence behind it.',
        "> CrawlerNest makes every rank explainable: you can see which sources contributed,",
        "> how much they agree, and why confidence is high or low.",
        '> When data is missing or stale, the platform says so — on the main analytics page."',
        "",
        "---",
        "",
    ]

    # ── Recommended demo route ────────────────────────────────────────────
    lines += [
        "## Recommended Demo Route (3–4 minutes)",
        "",
        "| # | Stop | URL | Duration | Core Message |",
        "|---|---|---|---|---|",
        "| 1 | Source Disagreement | /analytics | 0:30 | Sources disagree; we classify it |",
        "| 2 | Source Coverage | /analytics | 0:20 | THE/ARWU unavailable; shown, not hidden |",
        "| 3 | Operational Posture | /analytics | 0:15 | System knows its own limits |",
        "| 4 | Generate Recommendations | /recommendations | 0:25 | Profile → explainable results |",
        "| 5 | Evidence Chain | /recommendations | 0:45 | Stored data, not generated text |",
        "| 6 | Confidence Bar | /recommendations | 0:20 | Formula-derived, not AI-asserted |",
        "| 7 | Data Caveats | /recommendations | 0:15 | Unconditional, always present |",
        "| 8 | Closing | — | 0:15 | Most honest, not most confident |",
        "",
        "See docs/DEMO_ROUTE.md for full step-by-step instructions.",
        "",
        "---",
        "",
    ]

    # ── Strongest differentiators ─────────────────────────────────────────
    lines += [
        "## Strongest Competition Differentiators",
        "",
    ]
    for i, (title, desc) in enumerate(DIFFERENTIATORS, 1):
        lines += [
            f"### {i}. {title}",
            "",
            desc,
            "",
        ]
    lines += ["---", ""]

    # ── Operational honesty posture ───────────────────────────────────────
    lines += [
        "## Operational Honesty Posture",
        "",
        "CrawlerNest discloses data limitations at three levels:",
        "",
        "1. **Page-level** — Operational Posture section on `/analytics` shows source availability",
        "   (`QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`) and confidence posture.",
        "",
        "2. **Result-level** — Every recommendation explain panel shows Source Coverage and",
        "   Data Caveats unconditionally, regardless of how clean the result looks.",
        "",
        "3. **Section-level** — Analytics Caveats section lists all known limitations from",
        "   the API response envelope — not hardcoded.",
        "",
        "None of these disclosures can be suppressed by a user action. They are structural.",
        "",
        "---",
        "",
    ]

    # ── Evidence-backed recommendation strengths ──────────────────────────
    lines += [
        "## Evidence-Backed Recommendation Strengths",
        "",
        "- Evidence Chain label makes provenance explicit — reasons are stored algorithm outputs",
        "- Confidence bar is derived from `completeness (65%) + source agreement (35%)`",
        "- Source coverage chips show QS/THE/ARWU availability per recommendation",
        "- Formula documented and version-tracked in `docs/RECOMMENDATION_EVIDENCE_MODEL.md`",
        "- No LLM, no generative text, no synthetic confidence scores",
        "- Explain endpoint is readonly — it reads stored values, does not recalculate",
        "",
        "---",
        "",
    ]

    # ── Known demo caveats ────────────────────────────────────────────────
    lines += [
        "## Known Demo Caveats (State Aloud — Once)",
        "",
    ]
    for title, desc in DEMO_CAVEATS:
        lines.append(f"- **{title}:** {desc}")
    lines += [
        "",
        "### Required Verbal Statements",
        "",
    ]
    for caveat in REQUIRED_VERBAL_CAVEATS:
        lines.append(f'- "{caveat}"')
    lines += ["", "---", ""]

    # ── What NOT to claim ─────────────────────────────────────────────────
    lines += [
        "## What NOT to Claim",
        "",
        "These claims are false or unverifiable at RC-1. Do not make them.",
        "",
    ]
    for claim in WHAT_NOT_TO_CLAIM:
        lines.append(f"- {claim}")
    lines += ["", "---", ""]

    # ── High-impact screens ───────────────────────────────────────────────
    lines += [
        "## High-Impact Demo Screens",
        "",
        "| Screen | URL | Why High-Impact |",
        "|---|---|---|",
        "| Source Disagreement Severity | /analytics | Severity chips classify spread; rare in ranking systems |",
        "| Operational Posture | /analytics | THE/ARWU Unavailable shown on main page |",
        "| Evidence Chain | /recommendations | Stored data, not chatbot output |",
        "| Confidence Bar + 'Not AI-generated' | /recommendations | Direct, verifiable claim |",
        "| Data Caveats (unconditional) | /recommendations | Caveats cannot be dismissed |",
        "",
        "---",
        "",
    ]

    # ── Phase docs status ─────────────────────────────────────────────────
    lines += [
        "## Competition Doc Status",
        "",
        "| Document | Present |",
        "|---|---|",
    ]
    for doc, present in doc_status.items():
        status = "✓" if present else "MISSING"
        lines.append(f"| {doc} | {status} |")
    lines += [""]

    if not all_docs_present:
        missing = [d for d, p in doc_status.items() if not p]
        lines += [
            f"Warning: {len(missing)} doc(s) missing: {', '.join(missing)}",
            "",
        ]

    lines += [
        "---",
        "",
        "## References",
        "",
        "- docs/DEMO_FLOW_ARCHITECTURE.md — timing and script per section",
        "- docs/DEMO_ROUTE.md — step-by-step click sequence",
        "- docs/JUDGE_ATTENTION_STRATEGY.md — high-impact screens, misunderstanding risks",
        "- docs/DEMO_EVIDENCE_SEQUENCING.md — revelation order strategy",
        "- docs/DEMO_HONESTY_STRATEGY.md — caveat framing and alarm calibration",
        "- docs/DEMO_SCREENSHOT_PLAN.md — which screens to capture and why",
        "- docs/COMPETITION_STORYTELLING.md — three-act narrative framework",
        "- docs/RECOMMENDATION_EVIDENCE_MODEL.md — evidence API contract and formula",
        "",
        "---",
        "",
        "This summary is readonly. To regenerate: `python3 scripts/build_competition_demo_summary.py`",
    ]

    return "\n".join(lines)


def _validate() -> None:
    """Self-test: ensure report contains expected sections."""
    import tempfile

    report = build_report()
    assert "Competition Demo Summary" in report, "missing title"
    assert "30-Second Elevator Pitch" in report, "missing elevator pitch"
    assert "Recommended Demo Route" in report, "missing demo route"
    assert "Strongest Competition Differentiators" in report, "missing differentiators"
    assert "Operational Honesty Posture" in report, "missing honesty posture"
    assert "What NOT to Claim" in report, "missing what not to claim"
    assert "Evidence-Backed Recommendation Strengths" in report, "missing evidence strengths"
    print("_validate: OK")


def main() -> None:
    if "--validate" in sys.argv:
        _validate()
        return

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    OUTPUT_FILE.write_text(report, encoding="utf-8")
    print(f"Written: {OUTPUT_FILE}")
    print(f"  {len(report.splitlines())} lines")


if __name__ == "__main__":
    main()
