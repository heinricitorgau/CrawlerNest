#!/usr/bin/env python3
"""Read-only survey of the admission crawler's raw output and its name gap.

Answers two questions before any admission write path is built:

1. What does the admission crawler actually produce today?  Runs
   ``UniversityAdmissionCrawler`` over the checked-in HTML snapshots (offline,
   no outbound request is ever made) and prints the extracted field values --
   the values ``crawl_outputs/*.json`` throws away, keeping only diagnostics.

2. How far are the admission-side university names from
   ``warehouse.canonical_university``?  Each name is resolved twice:

   * ``exact_only`` -- what the admission pipeline used to do: lowercase the
     name, look for a literal hit in
     ``canonical_university.display_name_normalized`` then
     ``university_alias.alias_normalized``.  No fuzzy stage, no country
     blocking, no review path.  Kept as the baseline this survey was written
     to measure.
   * ``EntityResolver`` -- the shared multi-stage resolver (exact / normalized
     / transliterated / fuzzy, with ``suspicious_merge`` and
     ``country_mismatch`` flags), which
     ``crawlernest_admission_crawler.entity_resolver`` now uses.

   The gap between the two columns is what the migration closed. Re-run it
   after adding universities to ``site_profiles`` to see whether the new names
   resolve before writing anything.

Nothing is written to the database.  The Postgres session is opened read-only
so an accidental INSERT would fail rather than land.

Usage
-----
    ./.venv/bin/python crawlernest/scripts/explore_admission_raw_data.py \
        --pg-user test --pg-password test --pg-database clawer

    # crawler output only, no database needed
    ./.venv/bin/python crawlernest/scripts/explore_admission_raw_data.py --skip-db

    # keep the full report for later diffing
    ./.venv/bin/python crawlernest/scripts/explore_admission_raw_data.py \
        --pg-password test --output-json reports/admission_raw_survey.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_CRAWLERNEST_DIR = _SCRIPT_DIR.parent

_ADMISSION_CRAWLER_DIR = _CRAWLERNEST_DIR / "crawlernest-admission-crawler"
_CORE_DIR = _CRAWLERNEST_DIR / "crawlernest-core"
_CRAWLER_CORE_DIR = _CRAWLERNEST_DIR / "crawlernest-crawler-core"

# The admission crawler package imports its own modules by flat name
# (``from models import ...``), and the repository root also has a models.py.
# Its directories therefore go in front of everything else, exactly as
# crawlernest-admission-crawler/scripts/run_admission_crawl.py does it.
for _path in (
    _CORE_DIR,
    _CRAWLER_CORE_DIR,
    _ADMISSION_CRAWLER_DIR / "site_profiles",
    _ADMISSION_CRAWLER_DIR / "extractors",
    _ADMISSION_CRAWLER_DIR / "crawlers",
    _ADMISSION_CRAWLER_DIR,
):
    _entry = str(_path)
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

from crawlers.university_site import UniversityAdmissionCrawler, _url_to_slug  # noqa: E402
from site_profiles.universities import UNIVERSITY_PROFILES  # noqa: E402

from entity_resolution.repository import EntityResolutionRepository  # noqa: E402
from entity_resolution.resolver import EntityResolver  # noqa: E402
from entity_resolution.types import EntityRecord  # noqa: E402

#: Countries are not in the crawl profiles, so the resolver gets no country
#: hint unless we supply one. Hand-maintained here only to show what country
#: blocking would do; a real pipeline would carry it on the record.
COUNTRY_HINT_BY_KEY = {
    "ucl": "United Kingdom",
    "melbourne": "Australia",
    "toronto": "Canada",
    "nus": "Singapore",
    "manchester": "United Kingdom",
    "oxford": "United Kingdom",
    "imperial": "United Kingdom",
    "mit": "United States",
}

#: Keys as UniversityAdmissionCrawler._display_field_name writes them into
#: AdmissionRecord.requirements. degree_level is not in that dict -- the
#: crawler pops it onto its own field -- so it is reported separately.
_FIELD_ORDER = ("IELTS", "TOEFL", "Duolingo", "GPA", "deadline")


@dataclass(slots=True)
class CrawlFinding:
    key: str
    university_name: str
    source_url: str
    crawl_status: str
    is_usable: bool
    degree_level: str
    requirements: dict[str, str]
    flagged_fields: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only survey of raw admission data and its canonical-name gap.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=_ADMISSION_CRAWLER_DIR / "crawl_snapshots",
        help="Directory of checked-in HTML snapshots (default: the crawler's own).",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        metavar="KEY",
        help="Restrict to these university keys (e.g. --only oxford mit).",
    )
    parser.add_argument("--skip-db", action="store_true", help="Skip the entity-resolution comparison.")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write the full survey as JSON.",
    )
    return parser.parse_args()


# -- Part 1: what the crawler produces ----------------------------------------

def survey_crawl_output(snapshot_dir: Path, keys: list[str]) -> list[CrawlFinding]:
    """Run the real crawler against snapshots only. Never touches the network."""
    crawler = UniversityAdmissionCrawler(snapshot_dir=snapshot_dir)
    findings: list[CrawlFinding] = []

    for key in keys:
        profile = UNIVERSITY_PROFILES[key]
        # Only URLs with a snapshot on disk are attempted, so a missing file
        # degrades to "no data" instead of silently going out to the site.
        offline_urls = [
            url
            for url in profile.candidate_urls
            if (snapshot_dir / f"{_url_to_slug(url)}.html").is_file()
        ]
        if not offline_urls:
            findings.append(
                CrawlFinding(
                    key=key,
                    university_name=profile.name,
                    source_url="",
                    crawl_status="no_snapshot",
                    is_usable=False,
                    degree_level="",
                    requirements={},
                    flagged_fields=[],
                )
            )
            continue

        for record in crawler.crawl(
            university_name=profile.name,
            base_url=profile.base_url,
            candidate_urls=offline_urls,
        ):
            summary = record.extraction_summary
            findings.append(
                CrawlFinding(
                    key=key,
                    university_name=record.university_name,
                    source_url=record.source_url,
                    crawl_status=record.crawl_status,
                    is_usable=bool(summary.is_usable) if summary else False,
                    degree_level=record.degree_level,
                    requirements=dict(record.requirements),
                    flagged_fields=list(summary.flagged_fields) if summary else [],
                )
            )
    return findings


def print_crawl_output(findings: list[CrawlFinding]) -> None:
    print("=" * 100)
    print("PART 1  raw admission data, extracted from checked-in snapshots (offline)")
    print("=" * 100)
    header = (
        f"{'key':<11} {'status':<12} {'use':<4} "
        + " ".join(f"{f:<12}" for f in _FIELD_ORDER)
        + f" {'degree_level':<14}"
    )
    print(header)
    print("-" * len(header))
    for finding in findings:
        cells = " ".join(f"{str(finding.requirements.get(f, '-'))[:12]:<12}" for f in _FIELD_ORDER)
        print(
            f"{finding.key:<11} {finding.crawl_status:<12} {'yes' if finding.is_usable else 'no':<4} "
            f"{cells} {(finding.degree_level or '-'):<14}"
        )

    field_fill = {
        field: sum(1 for f in findings if f.requirements.get(field) not in (None, ""))
        for field in _FIELD_ORDER
    }
    field_fill["degree_level"] = sum(1 for f in findings if f.degree_level)
    print()
    print(f"records={len(findings)}  usable={sum(1 for f in findings if f.is_usable)}")
    print("field fill: " + ", ".join(f"{field}={count}" for field, count in field_fill.items()))
    print()
    print("Field structure of one record (AdmissionRecord as the crawler emits it):")
    example = next((f for f in findings if f.requirements), None)
    if example is None:
        print("  (no snapshot produced any extracted field)")
    else:
        print(
            json.dumps(
                {
                    "university_name": example.university_name,
                    "source_url": example.source_url,
                    "degree_level": example.degree_level,
                    "requirements": example.requirements,
                    "crawl_status": example.crawl_status,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    print()
    print("NOTE: every field above now has a column in warehouse.admission_record:")
    print("      ielts_requirement / toefl_requirement / duolingo_requirement /")
    print("      gpa_requirement / application_deadline / degree_level. raw_payload")
    print("      keeps only what is genuinely one-to-many, such as")
    print("      deadline_candidates.")
    print()


# -- Part 2: the name gap -----------------------------------------------------

def _normalize_like_admission_pipeline(name: str) -> str:
    """Reproduce crawlernest_admission_crawler.normalize.normalize_university_name."""
    collapsed = re.sub(r"\s+", " ", name.strip())
    if not collapsed:
        return ""
    tokens = []
    for token in collapsed.split(" "):
        if token.isupper() and len(token) <= 5:
            tokens.append(token)
        elif token.islower() or token.isupper():
            tokens.append(token.capitalize())
        else:
            tokens.append(token)
    return " ".join(tokens)


def _exact_only_match(cur: Any, normalized_name: str) -> tuple[int | None, str]:
    """Reproduce the admission entity_resolver's only matching strategy."""
    lowered = normalized_name.lower().strip() if normalized_name else ""
    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.canonical_university
        WHERE display_name_normalized = %s
        ORDER BY canonical_university_id ASC LIMIT 1
        """,
        (lowered,),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0]), "resolved_canonical_exact"

    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.university_alias
        WHERE alias_normalized = %s
        ORDER BY canonical_university_id ASC, alias_id ASC LIMIT 1
        """,
        (lowered,),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0]), "resolved_alias_exact"
    return None, "unresolved"


def compare_resolution(args: argparse.Namespace, keys: list[str]) -> list[dict[str, Any]]:
    import psycopg2  # imported here so --skip-db needs no driver

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        dbname=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    # Belt and braces: this script must never mutate the warehouse.
    conn.set_session(readonly=True, autocommit=True)
    try:
        profiles = EntityResolutionRepository(conn).load_canonical_profiles()
        resolver = EntityResolver(profiles)
        display_name_by_id = {p.canonical_university_id: p.display_name for p in profiles}
        print(f"canonical profiles loaded: {len(profiles)}")

        rows: list[dict[str, Any]] = []
        with conn.cursor() as cur:
            for key in keys:
                profile = UNIVERSITY_PROFILES[key]
                admission_normalized = _normalize_like_admission_pipeline(profile.name)
                exact_id, exact_status = _exact_only_match(cur, admission_normalized)

                result = resolver.resolve_one(
                    EntityRecord(
                        source_name="university_site",
                        source_entity_id=key,
                        university_name=profile.name,
                        country_hint=COUNTRY_HINT_BY_KEY.get(key),
                    )
                )
                metadata = result.metadata or {}
                rows.append(
                    {
                        "key": key,
                        "crawler_name": profile.name,
                        "admission_normalized_name": admission_normalized,
                        "exact_only_canonical_id": exact_id,
                        "exact_only_status": exact_status,
                        "exact_only_display_name": display_name_by_id.get(exact_id) if exact_id else None,
                        "resolver_canonical_id": result.canonical_university_id,
                        "resolver_method": result.matching_method,
                        "resolver_confidence": result.confidence_score,
                        "resolver_display_name": (
                            display_name_by_id.get(result.canonical_university_id)
                            if result.canonical_university_id
                            else None
                        ),
                        "resolver_matched_alias": result.matched_alias,
                        "candidate_count": result.candidate_count,
                        "suspicious_merge": bool(metadata.get("suspicious_merge")),
                        "country_mismatch": bool(metadata.get("country_mismatch")),
                        "needs_human_review": result.matching_method in ("fuzzy", "fuzzy_review"),
                    }
                )
        return rows
    finally:
        conn.close()


def print_resolution(rows: list[dict[str, Any]]) -> None:
    print("=" * 100)
    print("PART 2  name gap: admission source names vs warehouse.canonical_university")
    print("=" * 100)
    for row in rows:
        print(f"\n[{row['key']}] {row['crawler_name']!r}")
        print(f"  admission-pipeline normalized form : {row['admission_normalized_name']!r}")
        exact_tail = (
            f" -> #{row['exact_only_canonical_id']} {row['exact_only_display_name']!r}"
            if row["exact_only_canonical_id"]
            else ""
        )
        print(f"  exact-only (today's admission ER)  : {row['exact_only_status']}{exact_tail}")
        resolver_tail = (
            f" -> #{row['resolver_canonical_id']} {row['resolver_display_name']!r}"
            if row["resolver_canonical_id"]
            else ""
        )
        print(
            f"  EntityResolver (ranking side)      : {row['resolver_method']}"
            f" conf={row['resolver_confidence']} candidates={row['candidate_count']}{resolver_tail}"
        )
        flags = [name for name in ("suspicious_merge", "country_mismatch", "needs_human_review") if row[name]]
        if flags:
            print(f"  flags                              : {', '.join(flags)}")

    total = len(rows)
    exact_hits = sum(1 for r in rows if r["exact_only_canonical_id"] is not None)
    resolver_hits = sum(1 for r in rows if r["resolver_canonical_id"] is not None)
    review_needed = sum(1 for r in rows if r["needs_human_review"])
    print()
    print("-" * 100)
    print(f"names={total}")
    print(f"  resolved by exact-only (current admission ER) : {exact_hits}/{total}")
    print(f"  resolved by EntityResolver (ranking ER)       : {resolver_hits}/{total}")
    print(f"  of those, landing in the fuzzy review band    : {review_needed}")
    print(f"  gap closed by reusing the ranking resolver    : {resolver_hits - exact_hits}")
    print()


def main() -> int:
    args = parse_args()

    keys = list(UNIVERSITY_PROFILES.keys())
    if args.only:
        unknown = sorted(set(args.only) - set(keys))
        if unknown:
            print(f"ERROR: unknown university keys: {unknown}", file=sys.stderr)
            print(f"  available: {keys}", file=sys.stderr)
            return 1
        keys = [key for key in keys if key in args.only]

    if not args.snapshot_dir.is_dir():
        print(f"ERROR: --snapshot-dir {args.snapshot_dir} does not exist", file=sys.stderr)
        return 1

    findings = survey_crawl_output(args.snapshot_dir, keys)
    print_crawl_output(findings)

    resolution_rows: list[dict[str, Any]] = []
    if args.skip_db:
        print("PART 2 skipped (--skip-db)\n")
    else:
        try:
            resolution_rows = compare_resolution(args, keys)
        except Exception as exc:  # noqa: BLE001 - surface the cause, keep part 1
            print(f"PART 2 unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("  (is PostgreSQL running? try --skip-db to survey the crawler only)", file=sys.stderr)
        else:
            print_resolution(resolution_rows)

    if args.output_json:
        payload = {
            "crawl_findings": [
                {
                    "key": f.key,
                    "university_name": f.university_name,
                    "source_url": f.source_url,
                    "crawl_status": f.crawl_status,
                    "is_usable": f.is_usable,
                    "degree_level": f.degree_level,
                    "requirements": f.requirements,
                    "flagged_fields": f.flagged_fields,
                }
                for f in findings
            ],
            "resolution_comparison": resolution_rows,
        }
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report written to {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
