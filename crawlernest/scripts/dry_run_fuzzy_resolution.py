#!/usr/bin/env python3
from __future__ import annotations

"""
Read-only dry run: how close did the unresolved backlog actually come to
matching, and how much of it is recoverable?

The multi-source pipeline already runs the core EntityResolver, but every miss
is logged to analytics.missing_entity_log with details_json reduced to
{"matching_method": "unresolved"} - no score, no candidate, no candidate count.
That leaves no way to tell a name that missed by 0.005 from one with no
candidate at all. This script replays the resolver over the backlog and reports
the top candidates and scores that the pipeline discarded.

It writes nothing. The session is opened READ ONLY, so a stray write would be
refused by PostgreSQL rather than silently applied. Not wired into
run_pipeline, not registered in crawlernest-tests/run_tests.py, not in CI.

Defaults target analytics.missing_entity_log. Columns and the status filter are
detected from information_schema rather than hardcoded, so any table carrying an
unresolved-name backlog can be pointed at:

    --schema warehouse --table <table>

warehouse.ranking_records_preview used to be the second supported layout. It was
dropped once its readers moved to warehouse.ranking_record; see
docs/migrations/RANKING_SCHEMA_CONVERGENCE.md.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution import EntityRecord, EntityResolver  # noqa: E402
from entity_resolution.normalizer import (  # noqa: E402
    normalize_university_name,
    tokenize_for_blocking,
)
from entity_resolution.repository import EntityResolutionRepository  # noqa: E402
from entity_resolution.resolver import ResolverThresholds  # noqa: E402

# Stages that need no fuzzy scoring at all: the core normalizer / curated alias
# catalogue alone would have matched these. Recovering them carries no
# similarity risk, which is why they are reported separately.
FREE_WIN_METHODS = frozenset(
    {
        "exact",
        "normalized",
        "exact_display",
        "normalized_display",
        "normalized_transliterated",
        "normalized_display_transliterated",
    }
)

# Column names differ between the two backlog layouts; probed in this order.
RAW_NAME_COLUMNS = ("raw_name", "university_name")
NORMALIZED_NAME_COLUMNS = ("normalized_name", "normalized_university_name")
SOURCE_COLUMNS = ("source_code", "source")
COUNTRY_COLUMNS = ("country_hint", "country", "country_name")
TIMESTAMP_COLUMNS = ("created_at", "extracted_at")

# Present only on the preview layout, where a row is a miss just when the
# status says so. missing_entity_log is a miss log, so every row counts.
STATUS_COLUMN = "entity_resolution_status"
STATUS_UNRESOLVED_VALUE = "unresolved"

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

BUCKET_ORDER = ("free_win", "fuzzy_accept", "fuzzy_review", "embedding", "unresolved")

BUCKET_LABELS = {
    "free_win": "free win     (normalizer/alias only, no fuzzy)",
    "fuzzy_accept": "fuzzy        (>= fuzzy_accept, auto-acceptable)",
    "fuzzy_review": "fuzzy_review (>= fuzzy_review, needs a human)",
    "embedding": "embedding    (optional matcher)",
    "unresolved": "unresolved   (< fuzzy_review, no usable candidate)",
}

# Sub-buckets for the unresolved tail, so "missed by a hair" is separable from
# "nothing remotely close". Reported as (label, inclusive lower bound).
NEAR_MISS_BANDS = (
    ("within 0.04 of fuzzy_review", 0.04),
    ("within 0.10 of fuzzy_review", 0.10),
)


@dataclass(frozen=True)
class TableProfile:
    schema: str
    table: str
    raw_name_column: str
    normalized_name_column: Optional[str]
    source_column: Optional[str]
    country_column: Optional[str]
    timestamp_column: Optional[str]
    has_status_filter: bool
    since_days: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def where_clause(self) -> str:
        conditions: list[str] = []
        if self.has_status_filter:
            conditions.append(f"{STATUS_COLUMN} = '{STATUS_UNRESOLVED_VALUE}'")
        # missing_entity_log is append-only: a name matched by a later run still
        # has its old miss rows sitting there. Without a window the backlog
        # looks progressively worse than it is.
        if self.since_days > 0 and self.timestamp_column:
            conditions.append(
                f"{self.timestamp_column} > CURRENT_TIMESTAMP - INTERVAL '{int(self.since_days)} days'"
            )
        return f"WHERE {' AND '.join(conditions)}" if conditions else ""


@dataclass(frozen=True)
class UnresolvedName:
    university_name: str
    normalized_university_name: str
    country_hint: Optional[str]
    row_count: int
    sources: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    canonical_university_id: int
    display_name: str
    matched_alias: str
    score: float
    country_hint: Optional[str]


@dataclass
class Assessment:
    name: UnresolvedName
    bucket: str
    matching_method: str
    confidence_score: float
    canonical_university_id: Optional[int]
    matched_alias: Optional[str]
    candidate_pool_size: int
    candidates: list[Candidate]
    country_mismatch: Optional[bool]
    suspicious_merge: Optional[bool]
    metadata: dict[str, Any] = field(default_factory=dict)


def _require_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.match(value or ""):
        raise SystemExit(f"invalid {label}: {value!r}")
    return value


def connect_readonly(args: argparse.Namespace) -> Any:
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - environment problem
        raise SystemExit(
            "psycopg2 is required. Activate the venv first: source .venv/bin/activate"
        ) from exc

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    # Hard guarantee rather than a promise: PostgreSQL refuses writes on this
    # session even if a future edit to this file tries one.
    conn.set_session(readonly=True, autocommit=True)
    return conn


def build_table_profile(conn: Any, schema: str, table: str, since_days: int = 0) -> TableProfile:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        columns = {str(row[0]) for row in cur.fetchall()}
    if not columns:
        raise SystemExit(f"table not found: {schema}.{table}")

    def first_present(candidates: tuple[str, ...]) -> Optional[str]:
        return next((name for name in candidates if name in columns), None)

    raw_name_column = first_present(RAW_NAME_COLUMNS)
    if not raw_name_column:
        raise SystemExit(
            f"{schema}.{table} has no recognised name column "
            f"(looked for {', '.join(RAW_NAME_COLUMNS)})"
        )

    return TableProfile(
        schema=schema,
        table=table,
        raw_name_column=raw_name_column,
        normalized_name_column=first_present(NORMALIZED_NAME_COLUMNS),
        source_column=first_present(SOURCE_COLUMNS),
        country_column=first_present(COUNTRY_COLUMNS),
        timestamp_column=first_present(TIMESTAMP_COLUMNS),
        has_status_filter=STATUS_COLUMN in columns,
        since_days=max(0, int(since_days)),
    )


def load_unresolved_names(conn: Any, profile: TableProfile, limit: int) -> list[UnresolvedName]:
    normalized_expr = profile.normalized_name_column or f"{profile.raw_name_column}"
    country_expr = profile.country_column or "NULL::text"
    source_expr = profile.source_column or "NULL::text"
    limit_clause = f"LIMIT {int(limit)}" if limit and limit > 0 else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                {profile.raw_name_column} AS raw_name,
                {normalized_expr} AS normalized_name,
                {country_expr} AS country_hint,
                COUNT(*) AS row_count,
                ARRAY_AGG(DISTINCT {source_expr}) AS sources
            FROM {profile.qualified_name}
            {profile.where_clause}
            GROUP BY {profile.raw_name_column}, {normalized_expr}, {country_expr}
            ORDER BY row_count DESC, raw_name ASC
            {limit_clause}
            """
        )
        rows = cur.fetchall()

    return [
        UnresolvedName(
            university_name=str(raw_name),
            normalized_university_name=str(norm_name or ""),
            country_hint=str(country).strip().lower() if country else None,
            row_count=int(row_count),
            sources=tuple(sorted(str(s) for s in (sources or []) if s)),
        )
        for raw_name, norm_name, country, row_count, sources in rows
    ]


def count_backlog_rows(conn: Any, profile: TableProfile) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {profile.qualified_name} {profile.where_clause}")
        row = cur.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def rank_candidates(
    resolver: EntityResolver,
    record: EntityRecord,
    top_n: int,
) -> tuple[list[Candidate], int]:
    """
    Mirror of EntityResolver._fuzzy_best_match, kept as a ranked list instead of
    a single winner. The formula (0.75 * SequenceMatcher + 0.25 * token Jaccard)
    is duplicated deliberately; check_scoring_drift() below fails loudly if the
    two ever disagree.
    """
    normalized_name = normalize_university_name(record.university_name)
    candidate_ids = resolver._candidate_ids(record, normalized_name)
    record_tokens = set(tokenize_for_blocking(record.university_name))

    scored: list[Candidate] = []
    for cid in candidate_ids:
        profile = resolver._profiles_by_id[cid]
        best_alias: Optional[str] = None
        best_score: Optional[float] = None

        for alias in (profile.display_name, *profile.aliases):
            alias_variants = [alias]
            stripped_alias = resolver._strip_parenthetical_suffix(alias)
            if stripped_alias and stripped_alias != alias:
                alias_variants.append(stripped_alias)

            alias_best: Optional[float] = None
            for alias_variant in alias_variants:
                alias_norm = normalize_university_name(alias_variant)
                if not alias_norm:
                    continue
                seq = SequenceMatcher(None, normalized_name, alias_norm).ratio()
                alias_tokens = set(tokenize_for_blocking(alias_variant))
                if record_tokens or alias_tokens:
                    jaccard = len(record_tokens & alias_tokens) / len(record_tokens | alias_tokens)
                else:
                    jaccard = 0.0
                score = 0.75 * seq + 0.25 * jaccard
                if alias_best is None or score > alias_best:
                    alias_best = score

            if alias_best is None:
                continue
            if best_score is None or alias_best > best_score:
                best_score = alias_best
                best_alias = alias

        if best_score is None or best_alias is None:
            continue
        scored.append(
            Candidate(
                canonical_university_id=cid,
                display_name=profile.display_name,
                matched_alias=best_alias,
                score=best_score,
                country_hint=profile.country_hint,
            )
        )

    # Stable sort over the candidate_ids iteration order reproduces the
    # resolver's strictly-greater tie-break.
    scored.sort(key=lambda candidate: -candidate.score)
    return scored[:top_n], len(candidate_ids)


def classify(matching_method: str) -> str:
    if matching_method in FREE_WIN_METHODS:
        return "free_win"
    if matching_method == "fuzzy":
        return "fuzzy_accept"
    if matching_method == "fuzzy_review":
        return "fuzzy_review"
    if matching_method in {"embedding", "embedding_review"}:
        return "embedding"
    return "unresolved"


def check_scoring_drift(assessment: Assessment) -> Optional[str]:
    """Fail loudly if this script's mirrored formula diverges from the resolver."""
    if assessment.matching_method not in {"fuzzy", "fuzzy_review", "unresolved"}:
        return None
    if not assessment.candidates or assessment.confidence_score <= 0.0:
        return None
    mirrored = round(assessment.candidates[0].score, 4)
    if abs(mirrored - assessment.confidence_score) > 1e-6:
        return (
            f"{assessment.name.university_name!r}: resolver reported "
            f"{assessment.confidence_score:.4f}, this script computed {mirrored:.4f}"
        )
    return None


def assess(
    resolver: EntityResolver,
    names: list[UnresolvedName],
    *,
    top_n: int,
    country_available: bool,
    progress_every: int,
) -> tuple[list[Assessment], list[str]]:
    assessments: list[Assessment] = []
    drift: list[str] = []

    for index, name in enumerate(names, start=1):
        record = EntityRecord(
            source_name=",".join(name.sources) or "UNKNOWN",
            # Dry run only: the backlog has no stable per-source entity id here,
            # so the normalized name stands in as the echo key.
            source_entity_id=name.normalized_university_name or name.university_name,
            university_name=name.university_name,
            country_hint=name.country_hint,
        )
        result = resolver.resolve_one(record)
        candidates, pool_size = rank_candidates(resolver, record, top_n)
        metadata = result.metadata if isinstance(result.metadata, dict) else {}

        assessment = Assessment(
            name=name,
            bucket=classify(result.matching_method),
            matching_method=result.matching_method,
            confidence_score=float(result.confidence_score),
            canonical_university_id=result.canonical_university_id,
            matched_alias=result.matched_alias,
            candidate_pool_size=pool_size,
            candidates=candidates,
            country_mismatch=bool(metadata.get("country_mismatch")) if country_available else None,
            suspicious_merge=bool(metadata.get("suspicious_merge")) if country_available else None,
            metadata=metadata,
        )
        assessments.append(assessment)

        message = check_scoring_drift(assessment)
        if message:
            drift.append(message)

        if progress_every and index % progress_every == 0:
            print(f"  ... assessed {index}/{len(names)} names", file=sys.stderr)

    return assessments, drift


def _bucket_totals(assessments: list[Assessment]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {
        bucket: {"names": 0, "rows": 0} for bucket in BUCKET_ORDER
    }
    for assessment in assessments:
        totals[assessment.bucket]["names"] += 1
        totals[assessment.bucket]["rows"] += assessment.name.row_count
    return totals


def _near_miss_totals(
    assessments: list[Assessment], thresholds: ResolverThresholds
) -> list[tuple[str, int, int]]:
    """How much of the unresolved tail sits just below the review threshold."""
    out: list[tuple[str, int, int]] = []
    tail = [a for a in assessments if a.bucket == "unresolved"]
    for label, margin in NEAR_MISS_BANDS:
        floor = thresholds.fuzzy_review - margin
        band = [
            a
            for a in tail
            if a.candidates and floor <= a.candidates[0].score < thresholds.fuzzy_review
        ]
        out.append((label, len(band), sum(a.name.row_count for a in band)))
    no_candidate = [a for a in tail if not a.candidates]
    out.append(("no candidate at all", len(no_candidate), sum(a.name.row_count for a in no_candidate)))
    return out


def _format_country(value: Optional[str]) -> str:
    return value if value else "-"


def print_report(
    assessments: list[Assessment],
    *,
    profile: TableProfile,
    canonical_profile_count: int,
    alias_count: int,
    total_backlog_rows: int,
    thresholds: ResolverThresholds,
    detail_limit: int,
    drift: list[str],
) -> None:
    covered_rows = sum(a.name.row_count for a in assessments)
    totals = _bucket_totals(assessments)
    recoverable_rows = totals["free_win"]["rows"] + totals["fuzzy_accept"]["rows"]
    recoverable_names = totals["free_win"]["names"] + totals["fuzzy_accept"]["names"]
    review_rows = totals["fuzzy_review"]["rows"]

    line = "=" * 78
    print(line)
    print("CrawlerNest - entity resolution backlog dry run (READ ONLY, nothing written)")
    print(line)
    print(f"target          : {profile.qualified_name}")
    if profile.since_days > 0 and profile.timestamp_column:
        print(f"window          : last {profile.since_days} days by {profile.timestamp_column}")
    elif profile.since_days > 0:
        print("window          : requested but this table has no timestamp column; using all rows")
    else:
        print("window          : all rows (append-only log may include already-fixed names)")
    print(f"canonical       : {canonical_profile_count} profiles, {alias_count} aliases")
    print(f"backlog         : {len(assessments)} distinct names / {covered_rows} rows assessed")
    if covered_rows != total_backlog_rows:
        print(f"                  ({total_backlog_rows} backlog rows in table; --limit applied)")
    print(
        f"thresholds      : fuzzy_accept={thresholds.fuzzy_accept} "
        f"fuzzy_review={thresholds.fuzzy_review}"
    )
    if profile.country_column:
        print(f"country column  : {profile.country_column} (country blocking + mismatch active)")
    else:
        print("country column  : ABSENT from this table")
        print("                  -> country_mismatch could NOT be evaluated for any row.")
    print()

    print("-" * 78)
    print("VERDICT SUMMARY - replaying the core EntityResolver over the backlog")
    print("-" * 78)
    for bucket in BUCKET_ORDER:
        counts = totals[bucket]
        if bucket == "embedding" and counts["names"] == 0:
            continue
        share = (counts["names"] / len(assessments) * 100.0) if assessments else 0.0
        print(
            f"  {BUCKET_LABELS[bucket]:<50} "
            f"{counts['names']:>5} names {counts['rows']:>6} rows  {share:5.1f}%"
        )
    print()
    if assessments:
        print(
            f"  recoverable without human review : {recoverable_names} names "
            f"({recoverable_names / len(assessments) * 100.0:.1f}% of distinct backlog names, "
            f"{recoverable_rows} rows)"
        )
        print(
            f"  would need human review          : {totals['fuzzy_review']['names']} names "
            f"({totals['fuzzy_review']['names'] / len(assessments) * 100.0:.1f}%, {review_rows} rows)"
        )
    print()

    print("-" * 78)
    print("UNRESOLVED TAIL - how close did the rest get?")
    print("-" * 78)
    for label, name_count, row_count in _near_miss_totals(assessments, thresholds):
        print(f"  {label:<34} {name_count:>5} names {row_count:>6} rows")
    print()

    for bucket in BUCKET_ORDER:
        rows = [a for a in assessments if a.bucket == bucket]
        if not rows:
            continue
        rows.sort(key=lambda a: (-a.name.row_count, a.name.university_name))
        shown = rows[:detail_limit] if detail_limit and detail_limit > 0 else rows
        print("-" * 78)
        print(f"{BUCKET_LABELS[bucket]}  ({len(rows)} names, showing {len(shown)})")
        print("-" * 78)
        for assessment in shown:
            name = assessment.name
            print(
                f"* {name.university_name}"
                f"   [rows={name.row_count} sources={','.join(name.sources) or '-'}"
                f" country={_format_country(name.country_hint)}]"
            )
            print(
                f"    resolver method   : {assessment.matching_method}"
                f"   |  candidate pool: {assessment.candidate_pool_size}"
            )
            if assessment.country_mismatch is not None:
                print(
                    f"    country_mismatch  : {assessment.country_mismatch}"
                    f"   |  suspicious_merge: {assessment.suspicious_merge}"
                )
            if not assessment.candidates:
                print("    candidates        : none (token blocking produced no candidate)")
            for position, candidate in enumerate(assessment.candidates, start=1):
                print(
                    f"      {position}. {candidate.score:.4f}  "
                    f"id={candidate.canonical_university_id}  "
                    f"country={_format_country(candidate.country_hint)}  "
                    f"{candidate.display_name}"
                )
                if candidate.matched_alias != candidate.display_name:
                    print(f"          via alias: {candidate.matched_alias}")
            print()

    print("-" * 78)
    print("CAVEATS")
    print("-" * 78)
    print("  - This is a similarity estimate, not proof of correctness. Every fuzzy")
    print("    match in the buckets above is a hypothesis until a human confirms it.")
    if not profile.country_column:
        print("  - country_mismatch is unevaluated, so the resolver's own suspicious_merge")
        print("    guard ran without its country signal. Treat scores as optimistic.")
    print("  - The canonical set these names are scored against was itself seeded from")
    print("    one source. A name absent from that set cannot be matched at any")
    print("    threshold, however good the scoring gets.")
    print("  - Nothing here changes confidence levels. Confidence stays derived from")
    print("    source count; resolution only decides whether a source rank counts.")
    print()

    if drift:
        print("!" * 78)
        print(f"SCORING DRIFT DETECTED ({len(drift)} names)")
        print("This script's mirrored fuzzy formula no longer matches EntityResolver.")
        print("The candidate scores above are NOT trustworthy until this is fixed.")
        print("!" * 78)
        for message in drift[:20]:
            print(f"  - {message}")
        print()


def build_json_payload(
    assessments: list[Assessment],
    *,
    profile: TableProfile,
    canonical_profile_count: int,
    alias_count: int,
    total_backlog_rows: int,
    thresholds: ResolverThresholds,
    drift: list[str],
) -> dict[str, Any]:
    return {
        "target": profile.qualified_name,
        "read_only": True,
        "canonical_profile_count": canonical_profile_count,
        "canonical_alias_count": alias_count,
        "total_backlog_rows": total_backlog_rows,
        "assessed_name_count": len(assessments),
        "assessed_row_count": sum(a.name.row_count for a in assessments),
        "thresholds": {
            "fuzzy_accept": thresholds.fuzzy_accept,
            "fuzzy_review": thresholds.fuzzy_review,
        },
        "country_column": profile.country_column,
        "country_mismatch_evaluable": bool(profile.country_column),
        "bucket_totals": _bucket_totals(assessments),
        "near_miss_totals": [
            {"band": label, "names": name_count, "rows": row_count}
            for label, name_count, row_count in _near_miss_totals(assessments, thresholds)
        ],
        "scoring_drift": drift,
        "names": [
            {
                "university_name": a.name.university_name,
                "normalized_university_name": a.name.normalized_university_name,
                "country_hint": a.name.country_hint,
                "row_count": a.name.row_count,
                "sources": list(a.name.sources),
                "bucket": a.bucket,
                "matching_method": a.matching_method,
                "confidence_score": a.confidence_score,
                "canonical_university_id": a.canonical_university_id,
                "matched_alias": a.matched_alias,
                "candidate_pool_size": a.candidate_pool_size,
                "country_mismatch": a.country_mismatch,
                "suspicious_merge": a.suspicious_merge,
                "candidates": [
                    {
                        "rank": position,
                        "canonical_university_id": c.canonical_university_id,
                        "display_name": c.display_name,
                        "matched_alias": c.matched_alias,
                        "score": round(c.score, 6),
                        "country_hint": c.country_hint,
                    }
                    for position, c in enumerate(a.candidates, start=1)
                ],
            }
            for a in assessments
        ],
    }


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only dry run of the core EntityResolver against the unresolved "
            "entity backlog."
        ),
    )
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument(
        "--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432"))
    )
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    parser.add_argument("--schema", default="analytics")
    parser.add_argument("--table", default="missing_entity_log")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="assess at most N distinct backlog names (0 = all, ordered by row count)",
    )
    parser.add_argument(
        "--top-n", type=int, default=3, help="candidates to show per name (default 3)"
    )
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=25,
        help="names to print per bucket in the text report (0 = all)",
    )
    parser.add_argument(
        "--fuzzy-accept", type=float, default=None, help="override ResolverThresholds.fuzzy_accept"
    )
    parser.add_argument(
        "--fuzzy-review", type=float, default=None, help="override ResolverThresholds.fuzzy_review"
    )
    parser.add_argument(
        "--json-out", default=None, help="also write the full report as JSON to this path"
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=0,
        help=(
            "only assess rows logged in the last N days (0 = all). "
            "missing_entity_log is append-only, so without a window a name "
            "matched by a later run still counts against the backlog."
        ),
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress the progress counter on stderr"
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    schema = _require_identifier(args.schema, "--schema")
    table = _require_identifier(args.table, "--table")

    defaults = ResolverThresholds()
    thresholds = ResolverThresholds(
        fuzzy_accept=args.fuzzy_accept if args.fuzzy_accept is not None else defaults.fuzzy_accept,
        fuzzy_review=args.fuzzy_review if args.fuzzy_review is not None else defaults.fuzzy_review,
    )
    if thresholds.fuzzy_review > thresholds.fuzzy_accept:
        raise SystemExit("--fuzzy-review must not exceed --fuzzy-accept")

    conn = connect_readonly(args)
    try:
        profile = build_table_profile(conn, schema, table, since_days=args.since_days)
        total_backlog_rows = count_backlog_rows(conn, profile)
        names = load_unresolved_names(conn, profile, args.limit)
        if not args.quiet:
            print("loading canonical profiles ...", file=sys.stderr)
        canonical_profiles = EntityResolutionRepository(conn).load_canonical_profiles()
    finally:
        conn.close()

    if not canonical_profiles:
        raise SystemExit(
            "No canonical university profiles found. Seed entity resolution tables first."
        )
    if not names:
        print(f"No backlog rows in {profile.qualified_name}. Nothing to assess.")
        return 0

    alias_count = sum(len(cp.aliases) for cp in canonical_profiles)
    if not args.quiet:
        print(f"building resolver over {len(canonical_profiles)} profiles ...", file=sys.stderr)
    resolver = EntityResolver(canonical_profiles, thresholds=thresholds)

    assessments, drift = assess(
        resolver,
        names,
        top_n=max(1, args.top_n),
        country_available=bool(profile.country_column),
        progress_every=0 if args.quiet else 100,
    )

    print_report(
        assessments,
        profile=profile,
        canonical_profile_count=len(canonical_profiles),
        alias_count=alias_count,
        total_backlog_rows=total_backlog_rows,
        thresholds=thresholds,
        detail_limit=args.detail_limit,
        drift=drift,
    )

    if args.json_out:
        payload = build_json_payload(
            assessments,
            profile=profile,
            canonical_profile_count=len(canonical_profiles),
            alias_count=alias_count,
            total_backlog_rows=total_backlog_rows,
            thresholds=thresholds,
            drift=drift,
        )
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote JSON report: {out_path}")

    return 2 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
