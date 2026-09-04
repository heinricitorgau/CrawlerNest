#!/usr/bin/env python3
"""Build a concise, presenter-friendly demo readiness summary from existing reports.

Readonly: reads existing report, snapshot, and release files.
No database access. No external API calls.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
RELEASES_DIR = REPO_ROOT / "releases"
SNAPSHOT_FILE = REPO_ROOT / "snapshots" / "latest_status.json"
OUTPUT_FILE = REPORTS_DIR / "demo_readiness_summary.md"

# Shared release posture; see scripts/_release_posture.py for why the RC-1 copies
# of these lists were removed rather than reworded.
from _release_posture import SPOKEN_CAVEATS, WHAT_NOT_TO_CLAIM

# Surfaces that must be present and functioning for the demo to run.
DEMO_SURFACES = [
    ("/analytics — Source Disagreement table", "severity chips, spread values, confidence badges"),
    ("/analytics — Source Coverage cards", "QS ✓ Available, THE — Unavailable, ARWU — Unavailable"),
    ("/analytics — Operational Posture section", "source availability chips, confidence posture label"),
    ("/recommendations — Evidence Chain panel", "Evidence Chain heading, ✓ reasons, confidence bar"),
    ("/recommendations — Data Caveats section", "unconditional caveats, always present"),
]



# Preparation steps verified before a demo.
DEMO_PREP_CHECKLIST = [
    "Backend running: `cd crawlernest/servise_for_java && ./mvnw -Dmaven.test.skip=true spring-boot:run`",
    "Frontend running: `cd crawlernest/crawlernest-web && npm run dev`",
    "Analytics page loads with Source Disagreement table visible",
    "At least one row has a High severity chip (spread ≥ 200)",
    "Source Coverage: QS ✓ Available, THE — Unavailable, ARWU — Unavailable",
    "Operational Posture section is visible with confidence posture label",
    "Recommendations page loads and Evidence Chain panel opens correctly",
    "Data Caveats section visible in explain panel — QS stale, THE, ARWU noted",
    "Browser zoom at 100%, unrelated tabs closed",
    "Priority 1 screenshots captured and accessible as fallback",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"missing: {path.name}")
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"unreadable: {path.name} ({exc})")
        return ""


def read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing: {path.name}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        warnings.append(f"malformed json: {path.name} ({exc})")
        return {}


def match(text: str, pattern: str, default: str = "unknown") -> str:
    found = re.search(pattern, text, re.MULTILINE)
    return found.group(1).strip() if found else default


def source_states(snapshot: dict[str, Any]) -> dict[str, int]:
    raw = snapshot.get("source_counts", [])
    if isinstance(raw, dict):
        return {str(k): int(v or 0) for k, v in raw.items()}
    result: dict[str, int] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("source_code"):
                result[str(item["source_code"])] = int(item.get("count") or 0)
    return result


def smoke_status(releases_dir: Path) -> str:
    smoke = releases_dir / "v0.1-demo" / "smoke_release_output.txt"
    if not smoke.exists():
        return "missing"
    text = smoke.read_text(encoding="utf-8", errors="replace")
    if "0 failed" in text and "passed" in text:
        return "passed"
    return "failed"


def doc_exists(filename: str) -> bool:
    return (REPO_ROOT / "docs" / filename).exists()


def check_production_docs() -> dict[str, bool]:
    return {
        "DEMO_PRODUCTION_RUNBOOK.md": doc_exists("DEMO_PRODUCTION_RUNBOOK.md"),
        "DEMO_BROWSER_STATE.md": doc_exists("DEMO_BROWSER_STATE.md"),
        "SCREENSHOT_CAPTURE_WORKFLOW.md": doc_exists("SCREENSHOT_CAPTURE_WORKFLOW.md"),
        "DEMO_RECORDING_PREP.md": doc_exists("DEMO_RECORDING_PREP.md"),
        "DEMO_DATA_FREEZE.md": doc_exists("DEMO_DATA_FREEZE.md"),
        "DEMO_FAILURE_RECOVERY.md": doc_exists("DEMO_FAILURE_RECOVERY.md"),
        "DEMO_FLOW_ARCHITECTURE.md": doc_exists("DEMO_FLOW_ARCHITECTURE.md"),
        "DEMO_ROUTE.md": doc_exists("DEMO_ROUTE.md"),
        "DEMO_HONESTY_STRATEGY.md": doc_exists("DEMO_HONESTY_STRATEGY.md"),
        "DEMO_EVIDENCE_SEQUENCING.md": doc_exists("DEMO_EVIDENCE_SEQUENCING.md"),
    }


# ── Report builder ─────────────────────────────────────────────────────────────

def build(reports_dir: Path, snapshot_file: Path, releases_dir: Path) -> str:
    warnings: list[str] = []

    maintenance = read_text(reports_dir / "maintenance_readiness_summary.md", warnings)
    trust = read_text(reports_dir / "operational_trust_summary.md", warnings)
    demo_caveats_raw = read_text(reports_dir / "demo_caveats.md", warnings)
    snapshot = read_json(snapshot_file, warnings)

    freshness_state = match(maintenance, r"^Freshness state:\s*\*\*([^*]+)\*\*", "unknown")
    agg_count = match(maintenance, r"^- Aggregated count:\s*(\d+)", "unknown")
    trust_level = match(trust, r"^\| Operational trust level \| ([^|]+) \|", "unknown").strip()
    snap_ts = str(snapshot.get("snapshot_timestamp") or "[missing]")
    counts = source_states(snapshot)
    smoke = smoke_status(releases_dir)
    doc_status = check_production_docs()
    all_docs_present = all(doc_status.values())

    available_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) > 0]
    missing_sources = [s for s in ("QS", "THE", "ARWU") if counts.get(s, 0) == 0]

    # Determine blockers vs. acceptable conditions.
    blockers: list[str] = []
    if smoke == "failed":
        blockers.append("Smoke check failed — verify before demo.")
    if "QS" in missing_sources:
        blockers.append("QS source has zero records — demo analytics will be empty.")
    qs_count = counts.get("QS", 0)
    if 0 < qs_count < 100:
        blockers.append(f"QS record count anomalously low ({qs_count}) — expected ~1,499.")

    now = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    lines: list[str] = [
        "# Demo Readiness Summary",
        "",
        f"Generated: {now}",
        f"Snapshot: `{snap_ts}`",
        "",
        "This summary is for presenter use before a competition demo.",
        "Readonly. No database access. No external API calls.",
        "",
        "---",
        "",
    ]

    # ── Readiness posture ─────────────────────────────────────────────────
    if blockers:
        readiness_label = "NOT READY — blockers present"
    elif smoke == "missing":
        readiness_label = "CAUTION — smoke result missing"
    else:
        readiness_label = "READY — no blockers detected"

    lines += [
        "## Demo Readiness Posture",
        "",
        f"**{readiness_label}**",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Aggregated universities | {agg_count} |",
        f"| Available sources | {', '.join(available_sources) if available_sources else '[none]'} |",
        f"| Freshness state | {freshness_state} |",
        f"| Operational trust level | {trust_level} |",
        f"| Smoke | {smoke} |",
        f"| Demo caveats file | {'present' if demo_caveats_raw else 'MISSING'} |",
        f"| Production docs | {'all present' if all_docs_present else 'INCOMPLETE'} |",
        "",
        "---",
        "",
    ]

    if blockers:
        lines += ["## Blockers — Resolve Before Demo", ""]
        for b in blockers:
            lines.append(f"- {b}")
        lines += [
            "",
            "See [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) for recovery steps.",
            "",
            "---",
            "",
        ]

    # ── Strongest demo surfaces ───────────────────────────────────────────
    lines += [
        "## Strongest Demo Surfaces",
        "",
        "| Surface | URL | What to Show |",
        "| --- | --- | --- |",
    ]
    for surface, elements in DEMO_SURFACES:
        lines.append(f"| {surface} | — | {elements} |")
    lines += ["", "---", ""]

    # ── Demo-safe preparation checklist ──────────────────────────────────
    lines += [
        "## Demo-Safe Preparation Checklist",
        "",
        "Complete before the demo begins. See [DEMO_PRODUCTION_RUNBOOK.md](DEMO_PRODUCTION_RUNBOOK.md) for detail.",
        "",
    ]
    for item in DEMO_PREP_CHECKLIST:
        lines.append(f"- [ ] {item}")
    lines += ["", "---", ""]

    # ── Operational posture summary ───────────────────────────────────────
    lines += [
        "## Operational Posture Summary",
        "",
        "These are the stable degraded conditions. They are expected, documented,",
        "and caveat-covered. They do not block the demo. Source availability is not",
        "among them: all three sources are ingested, so a source reading zero is an",
        "incident rather than expected posture.",
        "",
        "- Ranking data is a 2026 snapshot — disclosed in Data Caveats",
        "- Source coverage is partial for each source — shown per source on /analytics",
        "- Subject rankings are QS-only — not on primary demo route",
        "- Confidence is derived from source count, so single-source rows read low — correct, not inflated",
        "- Some values are model estimates, labelled and support-flagged — disclosed where shown",
        "- Localhost deployment — stated once during demo opening or if asked",
        "",
        "---",
        "",
    ]

    # ── Required verbal caveats ───────────────────────────────────────────
    lines += [
        "## Required Verbal Statements (State Aloud — Once)",
        "",
        "These must be spoken during the demo, not just shown on screen.",
        "",
    ]
    for caveat in SPOKEN_CAVEATS:
        lines.append(f'- "{caveat}"')
    lines += ["", "---", ""]

    # ── What NOT to claim ─────────────────────────────────────────────────
    lines += [
        "## What NOT to Claim",
        "",
        "These claims are false or unverifiable. Do not make them.",
        "",
    ]
    for claim in WHAT_NOT_TO_CLAIM:
        lines.append(f"- {claim}")
    lines += ["", "---", ""]

    # ── Fallback readiness ────────────────────────────────────────────────
    lines += [
        "## Fallback Readiness",
        "",
        "If the live demo fails, have these ready:",
        "",
        "1. **Priority 1 screenshots** — Source Disagreement, Operational Posture, Evidence Chain, Caveats",
        "   See [SCREENSHOT_CAPTURE_WORKFLOW.md](SCREENSHOT_CAPTURE_WORKFLOW.md) for what must be visible.",
        "",
        "2. **This file** — printable posture summary, verbal caveats, and what NOT to claim.",
        "",
        "3. **reports/competition_demo_summary.md** — elevator pitch, differentiators, demo route.",
        "",
        "See [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) for per-failure recovery steps.",
        "",
        "---",
        "",
    ]

    # ── Production docs status ────────────────────────────────────────────
    lines += [
        "## Production Doc Status",
        "",
        "| Document | Present |",
        "| --- | --- |",
    ]
    for doc, present in doc_status.items():
        status = "✓" if present else "MISSING"
        lines.append(f"| {doc} | {status} |")
    if not all_docs_present:
        missing = [d for d, p in doc_status.items() if not p]
        lines += ["", f"Warning: {len(missing)} doc(s) missing: {', '.join(missing)}"]
    lines += ["", "---", ""]

    # ── Readonly guarantee ────────────────────────────────────────────────
    lines += [
        "## Readonly Guarantee",
        "",
        "This script reads existing report and snapshot files only.",
        "It does not connect to PostgreSQL, mutate application state,",
        "rerun crawlers, or change any operational artifact other than",
        "`reports/demo_readiness_summary.md`.",
    ]

    if warnings:
        lines += ["", "---", "", "## Input Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


def _validate() -> None:
    """Self-test: ensure report contains expected sections under various inputs."""
    with tempfile.TemporaryDirectory(prefix="crawlernest-readiness-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        reports.mkdir()
        releases = root / "releases"
        (releases / "v0.1-demo").mkdir(parents=True)

        # Empty inputs — all missing
        result_empty = build(reports, root / "latest_status.json", releases)
        assert "Demo Readiness Summary" in result_empty, "missing title"
        assert "missing" in result_empty.lower(), "missing warning not present"

        # Good inputs — no blockers
        (reports / "maintenance_readiness_summary.md").write_text(
            "# Maintenance\nFreshness state: **critical**\n"
            "- Aggregated count: 1499\n"
            "- Latest aggregation age hours: 354.0\n",
            encoding="utf-8",
        )
        (reports / "operational_trust_summary.md").write_text(
            "# Trust\n| Operational trust level | critical |\n",
            encoding="utf-8",
        )
        (reports / "demo_caveats.md").write_text("# Demo Caveats\n- QS stale\n", encoding="utf-8")
        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-24T10:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 1499}]}',
            encoding="utf-8",
        )
        smoke_dir = releases / "v0.1-demo"
        (smoke_dir / "smoke_release_output.txt").write_text(
            "Results: 5 passed, 0 failed\nRelease smoke OK\n", encoding="utf-8"
        )
        result_ok = build(reports, root / "latest_status.json", releases)
        assert "READY" in result_ok, "readiness label missing"
        assert "Required Verbal Statements" in result_ok, "caveats section missing"
        assert "What NOT to Claim" in result_ok, "what not to claim section missing"
        assert "Fallback Readiness" in result_ok, "fallback section missing"

        # Low QS count — should produce a blocker
        (root / "latest_status.json").write_text(
            '{"snapshot_timestamp": "2026-05-24T10:00:00+00:00", '
            '"source_counts": [{"source_code": "QS", "count": 5}]}',
            encoding="utf-8",
        )
        result_blocker = build(reports, root / "latest_status.json", releases)
        assert "Blockers" in result_blocker, "blocker section missing for low QS count"

    print("_validate: OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build demo readiness summary")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshot-file", default=str(SNAPSHOT_FILE))
    parser.add_argument("--releases-dir", default=str(RELEASES_DIR))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    parser.add_argument("--validate", action="store_true", help="Run self-test and exit")
    args = parser.parse_args()

    if args.validate:
        _validate()
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    content = build(Path(args.reports_dir), Path(args.snapshot_file), Path(args.releases_dir))
    output.write_text(content, encoding="utf-8")
    print(f"[demo-readiness-summary] written: {output}")
    print(f"  {len(content.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
