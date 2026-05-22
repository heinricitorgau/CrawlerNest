#!/usr/bin/env python3
"""Build a single-entry readonly operational index summary."""

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
SNAPSHOTS_DIR = REPO_ROOT / "snapshots"
RELEASE_DIR = REPO_ROOT / "releases" / "v0.1-demo"
VALIDATION_DOC = REPO_ROOT / "docs" / "RC1_VALIDATION_RESULTS.md"


def read_text(path: Path, warnings: list[str], require_heading: bool = True) -> str:
    if not path.exists():
        warnings.append(f"missing: {path}")
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"unreadable: {path} ({exc})")
        return ""
    if not text.strip():
        warnings.append(f"empty report: {path}")
    elif require_heading and not text.lstrip().startswith("#"):
        warnings.append(f"malformed report: {path} (missing markdown heading)")
    return text


def read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"missing: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"malformed JSON: {path} ({exc})")
        return {}
    if not isinstance(data, dict):
        warnings.append(f"malformed JSON: {path} (root is not an object)")
        return {}
    return data


def first_match(text: str, patterns: list[str], default: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return default


def latest_smoke_result(text: str) -> str:
    if "Release smoke passed." in text:
        match = re.search(r"Results:\s+([0-9]+ passed,\s+[0-9]+ failed)", text)
        return f"pass ({match.group(1)})" if match else "pass"
    if "Release smoke FAILED." in text:
        return "failed"
    return "unknown"


def validation_summary(text: str) -> str:
    rows = re.findall(r"\| `([^`]+)` \| ([^|]+) \|", text)
    if not rows:
        return "unknown"
    failures = [name for name, result in rows if "fail" in result.lower()]
    if failures:
        return "failed: " + ", ".join(failures)
    passes = [name for name, result in rows if "pass" in result.lower()]
    return f"pass ({len(passes)} pass rows)"


def latest_release_bundle(manifest_text: str) -> str:
    built = first_match(manifest_text, [r"^Built:\s*(.+)$"], "unknown")
    return f"v0.1-demo built {built}"


def build_summary(
    reports_dir: Path,
    snapshots_dir: Path,
    release_dir: Path,
    validation_doc: Path,
) -> str:
    warnings: list[str] = []
    generated_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()

    operational = read_text(reports_dir / "operational_summary.md", warnings)
    freshness = read_text(reports_dir / "freshness_escalation.md", warnings)
    drift = read_text(reports_dir / "drift_timeline.md", warnings)
    validation = read_text(validation_doc, warnings)
    manifest = read_text(release_dir / "MANIFEST.txt", warnings, require_heading=False)
    smoke = read_text(release_dir / "smoke_release_output.txt", warnings, require_heading=False)
    snapshot = read_json(snapshots_dir / "latest_status.json", warnings)

    latest_snapshot = str(snapshot.get("snapshot_timestamp") or "unknown")
    freshness_state = first_match(
        freshness,
        [r"^Escalation state:\s*\*\*([^*]+)\*\*", r"^Escalation state:\s*(.+)$"],
        "unknown",
    )
    drift_severity = first_match(
        drift,
        [r"^Overall severity:\s*(.+)$"],
        "unknown",
    )
    summary_state = first_match(
        operational,
        [r"^- Freshness state:\s*\*\*([^*]+)\*\*", r"^- Freshness state:\s*(.+)$"],
        freshness_state,
    )
    smoke_result = latest_smoke_result(smoke)
    validation_result = validation_summary(validation)
    release_bundle = latest_release_bundle(manifest)

    lines = [
        "# Operational Index Summary",
        "",
        f"Generated: {generated_at}",
        "",
        "## Single-Entry Status",
        "",
        f"- Latest snapshot timestamp: `{latest_snapshot}`",
        f"- Operational freshness state: **{summary_state}**",
        f"- Freshness escalation: **{freshness_state}**",
        f"- Drift severity: **{drift_severity}**",
        f"- Validation status: {validation_result}",
        f"- Latest release bundle: {release_bundle}",
        f"- Latest smoke result: {smoke_result}",
        "",
        "## Source Evidence",
        "",
        "| Evidence | Path | Role |",
        "| --- | --- | --- |",
        "| Operational summary | `reports/operational_summary.md` | Demo-friendly current state. |",
        "| Freshness escalation | `reports/freshness_escalation.md` | Staleness and source-gap classification. |",
        "| Drift timeline | `reports/drift_timeline.md` | Historical drift event classification. |",
        "| Latest snapshot | `snapshots/latest_status.json` | Latest compact snapshot pointer. |",
        "| Validation results | `docs/RC1_VALIDATION_RESULTS.md` | Latest recorded validation table. |",
        "| Release bundle manifest | `releases/v0.1-demo/MANIFEST.txt` | Latest bundle contents and timestamp. |",
        "| Smoke output | `releases/v0.1-demo/smoke_release_output.txt` | Latest bundle-captured smoke run. |",
        "",
        "## Readonly Boundary",
        "",
        "This summary only reads existing reports, docs, snapshots, and release bundle files. "
        "It does not run the pipeline, connect to PostgreSQL, change scoring, mutate runtime "
        "state, modify diagnostics semantics, or make autonomous decisions.",
    ]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build consolidated operational index summary")
    parser.add_argument("--reports-dir", default=str(REPORTS_DIR))
    parser.add_argument("--snapshots-dir", default=str(SNAPSHOTS_DIR))
    parser.add_argument("--release-dir", default=str(RELEASE_DIR))
    parser.add_argument("--validation-doc", default=str(VALIDATION_DOC))
    parser.add_argument("--output", default=str(REPORTS_DIR / "operational_index_summary.md"))
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_summary(
            Path(args.reports_dir),
            Path(args.snapshots_dir),
            Path(args.release_dir),
            Path(args.validation_doc),
        ),
        encoding="utf-8",
    )
    print(f"[operational-index-summary] written: {output}")
    return 0


def validate_missing_empty_malformed() -> None:
    with tempfile.TemporaryDirectory(prefix="crawlernest-op-index-") as tmp:
        root = Path(tmp)
        reports = root / "reports"
        snapshots = root / "snapshots"
        release = root / "release"
        docs = root / "docs"
        for directory in (reports, snapshots, release, docs):
            directory.mkdir(parents=True)
        (reports / "operational_summary.md").write_text("", encoding="utf-8")
        (reports / "freshness_escalation.md").write_text("not markdown", encoding="utf-8")
        (reports / "drift_timeline.md").write_text("# Drift Timeline\nOverall severity: info\n", encoding="utf-8")
        (snapshots / "latest_status.json").write_text("{broken", encoding="utf-8")
        (release / "MANIFEST.txt").write_text("CrawlerNest bundle\nBuilt: fixture\n", encoding="utf-8")
        (release / "smoke_release_output.txt").write_text("Release smoke passed.\n", encoding="utf-8")
        (docs / "RC1_VALIDATION_RESULTS.md").write_text("# Validation\n", encoding="utf-8")

        summary = build_summary(
            reports,
            snapshots,
            release,
            docs / "RC1_VALIDATION_RESULTS.md",
        )
        assert "empty report" in summary
        assert "malformed report" in summary
        assert "malformed JSON" in summary


if __name__ == "__main__":
    raise SystemExit(main())
