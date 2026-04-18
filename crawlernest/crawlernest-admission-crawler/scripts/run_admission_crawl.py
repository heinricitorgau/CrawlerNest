#!/usr/bin/env python3
"""Run the admission crawl pipeline for a set of universities.

Usage
-----
# Use snapshot HTML (offline / CI):
python scripts/run_admission_crawl.py --snapshot-dir crawl_snapshots --output-dir crawl_outputs

# Live HTTP crawl (requires outbound network):
python scripts/run_admission_crawl.py --output-dir crawl_outputs

# Single university:
python scripts/run_admission_crawl.py --snapshot-dir crawl_snapshots --only ucl oxford

Output
------
For each university, writes:
  crawl_outputs/<key>.json       — full CrawlReport (JSON)
  crawl_outputs/summary.json     — aggregate table of all runs
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_CRAWLER_DIR = _SCRIPT_DIR.parent
_REPO_ROOT = _CRAWLER_DIR.parent
_CORE_DIR = _REPO_ROOT / "crawlernest-crawler-core"

for _p in (
    _CRAWLER_DIR,
    _CORE_DIR,
    _CRAWLER_DIR / "crawlers",
    _CRAWLER_DIR / "extractors",
    _CRAWLER_DIR / "site_profiles",
    _CRAWLER_DIR / "scripts",
):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from crawlers.university_site import UniversityAdmissionCrawler
from models import AdmissionRecord
from observability import CrawlReport, ExtractionSummary, build_crawl_report
from site_profiles.universities import UNIVERSITY_PROFILES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CrawlerNest admission crawl pipeline.")
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=None,
        help="Path to snapshot HTML directory. If set, uses files instead of live HTTP.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_CRAWLER_DIR / "crawl_outputs",
        help="Directory to write JSON outputs.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="KEY",
        help="Only run specified university keys (e.g. --only ucl oxford).",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.0,
        help="Seconds to wait between requests (live HTTP only).",
    )
    return parser.parse_args()


def _build_report(
    university_name: str,
    base_url: str,
    records: list[AdmissionRecord],
) -> CrawlReport:
    """Collect ExtractionSummaries from records and build a CrawlReport."""
    summaries: list[ExtractionSummary] = []
    warnings: list[str] = []
    for rec in records:
        if rec.extraction_summary is not None:
            summaries.append(rec.extraction_summary)
        else:
            warnings.append(
                f"Record for {rec.source_url!r} is missing extraction_summary"
            )
    return build_crawl_report(
        university_name=university_name,
        base_url=base_url,
        summaries=summaries,
        warnings=warnings,
    )


def run_university(
    *,
    key: str,
    crawler: UniversityAdmissionCrawler,
    output_dir: Path,
) -> dict:
    """Crawl one university, write JSON, return summary row."""
    profile = UNIVERSITY_PROFILES[key]
    t0 = time.perf_counter()

    records = crawler.crawl(
        university_name=profile.name,
        base_url=profile.base_url,
        candidate_urls=profile.candidate_urls,
    )
    report = _build_report(profile.name, profile.base_url, records)

    elapsed = time.perf_counter() - t0
    output_path = output_dir / f"{key}.json"
    report.write_json(output_path)

    # Print per-URL detail
    print(f"\n{'='*60}")
    print(f"  {profile.name}")
    print(f"  urls_attempted={report.total_urls}  success={report.success_count}  usable={report.extraction_success_count}")
    if report.failure_breakdown:
        print(f"  failures: {report.failure_breakdown}")
    if report.anomaly_breakdown:
        print(f"  anomalies: {report.anomaly_breakdown}")
    if report.warnings:
        for w in report.warnings:
            print(f"  WARNING: {w}")

    for s in report.url_results:
        icon = "✓" if s.is_usable else "✗"
        fields = ", ".join(f"{k}={v}" for k, v in [
            ("IELTS", s.confidence_flags.get("IELTS")),
            ("TOEFL", s.confidence_flags.get("TOEFL")),
            ("degree_level", s.confidence_flags.get("degree_level")),
            ("deadline", s.confidence_flags.get("deadline")),
        ] if v is not None) or "no fields"
        print(f"  {icon} {s.url}")
        print(f"    status={s.crawl_status}  missing={s.missing_required_fields}  conf={fields}")

    print(f"  → {output_path}  ({elapsed:.2f}s)")

    return {
        "key": key,
        "university": profile.name,
        "urls_attempted": report.total_urls,
        "success_count": report.success_count,
        "usable_count": report.extraction_success_count,
        "failure_breakdown": report.failure_breakdown,
        "anomaly_breakdown": report.anomaly_breakdown,
        "elapsed_s": round(elapsed, 3),
        "output": str(output_path),
    }


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = args.snapshot_dir.resolve() if args.snapshot_dir else None
    if snapshot_dir and not snapshot_dir.exists():
        print(f"ERROR: --snapshot-dir {snapshot_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    mode = "snapshot" if snapshot_dir else "live HTTP"
    print(f"CrawlerNest Admission Crawl — mode={mode}")
    if snapshot_dir:
        print(f"  snapshot_dir: {snapshot_dir}")
    print(f"  output_dir:   {args.output_dir}")

    keys = list(UNIVERSITY_PROFILES.keys())
    if args.only:
        unknown = set(args.only) - set(keys)
        if unknown:
            print(f"ERROR: Unknown university keys: {unknown}", file=sys.stderr)
            print(f"  Available: {keys}", file=sys.stderr)
            sys.exit(1)
        keys = [k for k in keys if k in args.only]

    print(f"  universities: {keys}\n")

    crawler = UniversityAdmissionCrawler(snapshot_dir=snapshot_dir)
    summary_rows: list[dict] = []

    for key in keys:
        row = run_university(key=key, crawler=crawler, output_dir=args.output_dir)
        summary_rows.append(row)
        if snapshot_dir is None and args.rate_limit > 0:
            time.sleep(args.rate_limit)

    # Write aggregate summary
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Print aggregate table
    total_usable = sum(r["usable_count"] for r in summary_rows)
    total_urls = sum(r["urls_attempted"] for r in summary_rows)
    print(f"\n{'='*60}")
    print(f"AGGREGATE: {len(summary_rows)} universities | {total_urls} URLs | {total_usable} usable records")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
