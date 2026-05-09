#!/usr/bin/env python3
"""Build a human-readable failure summary from the latest system snapshot.

Reads: snapshots/latest_status.json
Optionally runs regression and drift scripts for live data.
Writes: reports/latest_failure_summary.md

Usage
-----
  python scripts/build_failure_summary.py [--pg-password test] [--run-live-checks]
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AUTOEVAL_ROOT = REPO_ROOT / "crawlernest" / "crawlernest-autoeval"
DEFAULT_SNAPSHOT_FILE = REPO_ROOT / "snapshots" / "latest_status.json"
REPORTS_DIR = REPO_ROOT / "reports"


def load_snapshot(snapshot_path: Path) -> dict:
    if not snapshot_path.exists():
        print(f"[summary] snapshot not found at {snapshot_path}")
        print("[summary] run: python scripts/export_system_snapshot.py --pg-password test")
        return {}
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def run_json_script(script_path: Path, extra_args: list[str]) -> dict:
    """Run a Python script with --json and return parsed output; empty dict on failure."""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--json"] + extra_args,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode not in (0, 1):
            return {}
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except Exception as exc:
        print(f"[summary] warning: {script_path.name} failed: {exc}")
        return {}


def format_trend(pct: float | None) -> str:
    if pct is None:
        return "N/A"
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "→")
    return f"{arrow} {abs(pct):.1f}%"


def build_markdown(
    snapshot: dict,
    regression: dict,
    drift: dict,
    pg_args: list[str],
) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    snap_ts = snapshot.get("snapshot_timestamp", "unknown")

    lines: list[str] = []
    lines.append("# CrawlerNest Failure Summary")
    lines.append(f"\nGenerated: {now.isoformat()}")
    lines.append(f"Snapshot: {snap_ts}")
    lines.append("")

    # ── Overall health ──
    overall_stale = snapshot.get("overall_stale", False)
    drift_count = snapshot.get("drift_warning_count", 0)
    reg_result = regression.get("result", "NOT RUN")
    reg_failed = regression.get("failed", 0)

    health_icon = "✅" if (not overall_stale and drift_count == 0 and reg_result != "FAIL") else "⚠️"
    lines.append(f"## {health_icon} Overall Status")
    lines.append("")
    lines.append(f"| Check | Result |")
    lines.append(f"|-------|--------|")
    lines.append(f"| Data freshness | {'STALE' if overall_stale else 'FRESH'} |")
    lines.append(f"| Drift warnings | {drift_count} |")
    lines.append(f"| Ranking regression | {reg_result} ({reg_failed} failed) |")
    lines.append("")

    # ── Regression failures ──
    if regression:
        lines.append("## Ranking Regression")
        lines.append("")
        lines.append(f"- **Result**: {regression.get('result', 'UNKNOWN')}")
        lines.append(f"- **Total assertions**: {regression.get('total_assertions', 0)}")
        lines.append(f"- **Passed**: {regression.get('passed', 0)}")
        lines.append(f"- **Failed**: {regression.get('failed', 0)}")
        missing = regression.get("missing_universities", [])
        if missing:
            lines.append(f"- **Missing universities**: {', '.join(missing)}")
        mismatches = regression.get("mismatches", [])
        if mismatches:
            lines.append("")
            lines.append("### Failed Assertions")
            lines.append("")
            for m in mismatches:
                lines.append(f"**{m['id']} — {m['university']}**")
                for a in m.get("failed_assertions", []):
                    lines.append(f"- `{a['assertion']}`: {a['detail']}")
                lines.append("")
    else:
        lines.append("## Ranking Regression")
        lines.append("")
        lines.append("_Not run. Use `--run-live-checks` or run `run_ranking_regression.py` manually._")
        lines.append("")

    # ── Drift warnings ──
    lines.append("## Source Drift Warnings")
    lines.append("")
    drift_warns = snapshot.get("drift_warnings", [])
    if not drift_warns and drift:
        drift_warns = (
            drift.get("count_drops", []) +
            drift.get("rank_range_gaps", []) +
            drift.get("score_distribution_shifts", []) +
            drift.get("country_disappearances", [])
        )
    if drift_warns:
        lines.append(f"{len(drift_warns)} warning(s) detected:")
        lines.append("")
        for w in drift_warns:
            lines.append(f"- **{w.get('source_code', '?')}** `{w.get('warning_type', '?')}`: "
                         f"{w.get('message', '')}")
    else:
        lines.append("_No drift warnings detected._")
    lines.append("")

    # ── Source coverage ──
    source_counts = snapshot.get("source_counts", {})
    if source_counts:
        lines.append("## Source Coverage")
        lines.append("")
        if isinstance(source_counts, dict):
            iterable = sorted(source_counts.items())
        else:
            iterable = [
                (item.get("source_code", "?"), item.get("count", item.get("records_in", 0)))
                for item in source_counts
                if isinstance(item, dict)
            ]
        for source, count in iterable:
            lines.append(f"- `{source}`: {count}")
        expected = snapshot.get("expected_sources", ["QS", "THE", "ARWU"])
        counts_map = {str(source): int(count or 0) for source, count in iterable}
        missing_sources = [source for source in expected if counts_map.get(source, 0) == 0]
        if missing_sources:
            lines.append(f"- **Missing sources**: {', '.join(missing_sources)}")
        lines.append("")

    # ── Unresolved universities ──
    unresolved = snapshot.get("unresolved_total", 0) or snapshot.get("unresolved", {}).get("total", 0)
    last_7d = snapshot.get("unresolved_last_7d", 0)
    trend_pct = snapshot.get("unresolved_trend_pct")
    lines.append("## Unresolved Universities")
    lines.append("")
    lines.append(f"- **Total**: {unresolved}")
    lines.append(f"- **Added in last 7 days**: {last_7d} ({format_trend(trend_pct)})")
    lines.append("")

    # ── Stale sources ──
    freshness = snapshot  # top-level keys OR nested; we handle both
    global_rankings = freshness.get("freshness", {}).get("global_rankings", []) if "freshness" in freshness else []
    subject_rankings = freshness.get("freshness", {}).get("subject_rankings", []) if "freshness" in freshness else []

    stale_sources = [s for s in global_rankings if s.get("stale") or s.get("missing")]
    stale_subjects = [s for s in subject_rankings if s.get("stale") or s.get("missing")]

    lines.append("## Data Staleness")
    lines.append("")
    if not stale_sources and not stale_subjects:
        lines.append("_All sources and subjects are fresh._")
    else:
        if stale_sources:
            lines.append(f"**Stale global sources** ({len(stale_sources)}):")
            for s in stale_sources:
                age = f"{s.get('age_hours', '?')}h" if not s.get("missing") else "MISSING"
                lines.append(f"- `{s['source_code']}`: {age}")
        if stale_subjects:
            lines.append(f"**Stale subject rankings** ({len(stale_subjects)}):")
            for s in stale_subjects:
                age = f"{s.get('age_hours', '?')}h" if not s.get("missing") else "MISSING"
                lines.append(f"- `{s['subject_key']}`: {age}")
    lines.append("")

    # ── Regression summary ──
    reg_summary = snapshot.get("regression_summary", {})
    if reg_summary:
        lines.append("## Regression Coverage")
        lines.append("")
        lines.append(f"- Aggregated universities: {reg_summary.get('aggregated_count', 0)}")
        if reg_summary.get("score_avg") is not None:
            lines.append(f"- Score range: {reg_summary.get('score_min', '?'):.2f} – "
                         f"{reg_summary.get('score_max', '?'):.2f} "
                         f"(avg {reg_summary.get('score_avg', '?'):.2f})")
        lines.append(f"- Low coverage (< 0.5): {reg_summary.get('low_coverage_count', 0)}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated by `scripts/build_failure_summary.py` at {now.isoformat()}_")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build failure summary from snapshot")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--run-live-checks", action="store_true",
                        help="Run regression and drift scripts for fresh data")
    parser.add_argument("--output", default=str(REPORTS_DIR / "latest_failure_summary.md"))
    parser.add_argument(
        "--snapshot-file",
        metavar="PATH",
        default=str(DEFAULT_SNAPSHOT_FILE),
        help="Path to snapshot JSON file (default: snapshots/latest_status.json). "
             "Use a fixture path for CI / no-database mode.",
    )
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = load_snapshot(Path(args.snapshot_file))
    pg_args = [
        "--pg-host", args.pg_host,
        "--pg-port", str(args.pg_port),
        "--pg-database", args.pg_database,
        "--pg-user", args.pg_user,
        "--pg-password", args.pg_password,
    ]

    regression: dict = {}
    drift: dict = {}
    if args.run_live_checks:
        print("[summary] running ranking regression...")
        regression = run_json_script(
            AUTOEVAL_ROOT / "runners" / "run_ranking_regression.py", pg_args)
        print("[summary] running source drift detection...")
        drift = run_json_script(
            AUTOEVAL_ROOT / "runners" / "run_source_drift.py", pg_args)

    md = build_markdown(snapshot, regression, drift, pg_args)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    print(f"[summary] written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
