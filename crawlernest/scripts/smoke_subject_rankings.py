#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT.parent))

from crawlernest_ranking_crawler.postgres_driver import get_psycopg2  # noqa: E402
from crawlernest_ranking_crawler.subjects.qs_subject import (  # noqa: E402
    fetch_qs_subject_rows,
    normalize_qs_subject_rows,
    resolve_subject_rows,
)
from crawlernest_ranking_crawler.subjects.writer import write_subject_ranking_rows  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test QS subject ranking Phase 1 writer")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--snapshot-dir",
        default=str(MODULE_ROOT / "crawlernest-kb" / "qs_subject_rankings"),
        help="QS subject snapshot root used as deterministic fallback.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Keep smoke rows. By default the script rolls back all writes.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    try:
        before_global = _global_counts(conn)
        canonical_ids = _ensure_smoke_canonical_universities(conn)
        first_rows, first_unresolved, sample = _load_resolved_rows(
            conn,
            year=args.year,
            snapshot_root=Path(args.snapshot_dir),
        )
        first = write_subject_ranking_rows(conn, first_rows, run_id="subject-smoke")
        second_rows, second_unresolved, _ = _load_resolved_rows(
            conn,
            year=args.year,
            snapshot_root=Path(args.snapshot_dir),
        )
        second = write_subject_ranking_rows(conn, second_rows, run_id="subject-smoke")
        subject_count = _subject_count(conn, args.year)
        after_global = _global_counts(conn)

        if canonical_ids <= 0:
            raise RuntimeError("expected smoke canonical fixtures to be available")
        if first.inserted_row_count != 2:
            raise RuntimeError(f"expected 2 inserted subject rows, got {first.inserted_row_count}")
        if second.inserted_row_count != 0 or second.updated_row_count != 2:
            raise RuntimeError(
                "expected idempotent rerun to update two rows without inserting: "
                f"inserted={second.inserted_row_count}, updated={second.updated_row_count}"
            )
        if subject_count != 2:
            raise RuntimeError(f"expected 2 visible subject rows for smoke year, got {subject_count}")
        if first_unresolved or second_unresolved:
            raise RuntimeError(
                f"expected no unresolved smoke rows, got first={len(first_unresolved)} second={len(second_unresolved)}"
            )
        if before_global != after_global:
            raise RuntimeError(f"global ranking counts changed unexpectedly: before={before_global}, after={after_global}")

        if args.commit:
            conn.commit()
            mode = "committed"
        else:
            conn.rollback()
            mode = "rolled back"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("[smoke] QS subject ranking writer: ok")
    print("[smoke] subjects: computer-science, electrical-engineering")
    print(f"[smoke] rows: 2 ({mode})")
    print(f"[smoke] sample_normalized_row={sample}")
    return 0


def _ensure_smoke_canonical_universities(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO warehouse.canonical_university (
                canonical_slug,
                display_name,
                display_name_normalized,
                status,
                metadata
            ) VALUES
                (
                    'subject-smoke-mit',
                    'Massachusetts Institute of Technology',
                    'massachusetts institute of technology',
                    'active',
                    '{"smoke": true}'::jsonb
                ),
                (
                    'subject-smoke-stanford',
                    'Stanford University',
                    'stanford university',
                    'active',
                    '{"smoke": true}'::jsonb
                )
            ON CONFLICT (canonical_slug) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                display_name_normalized = EXCLUDED.display_name_normalized,
                metadata = EXCLUDED.metadata
            RETURNING canonical_slug, canonical_university_id
            """
        )
        rows = cur.fetchall()
    return len(rows)


def _load_resolved_rows(conn, *, year: int, snapshot_root: Path):
    normalized = []
    for subject_key in ("computer-science", "electrical-engineering"):
        raw_rows = fetch_qs_subject_rows(subject_key, year, snapshot_root=snapshot_root)
        normalized.extend(normalize_qs_subject_rows(raw_rows, subject_key=subject_key, year=year))
    resolved, unresolved = resolve_subject_rows(conn, normalized)
    sample = normalized[0] if normalized else None
    return resolved, unresolved, sample


def _subject_count(conn, year: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM warehouse.subject_ranking_record srr
            JOIN warehouse.ranking_source rs
              ON rs.ranking_source_id = srr.ranking_source_id
            JOIN warehouse.ranking_subject subj
              ON subj.subject_id = srr.subject_id
            WHERE srr.ranking_year = %s
              AND rs.source_code = 'QS'
              AND subj.subject_key IN ('computer-science', 'electrical-engineering')
              AND srr.source_entity_id IN (
                  %s,
                  %s
              )
            """,
            (
                year,
                f"qs:subject:computer-science:{year}:massachusetts-institute-of-technology",
                f"qs:subject:electrical-engineering:{year}:stanford-university",
            ),
        )
        row = cur.fetchone()
    return 0 if row is None else int(row[0])


def _global_counts(conn) -> tuple[int | None, int | None, int | None]:
    return (
        _relation_count(conn, "warehouse.rankings"),
        _relation_count(conn, "warehouse.ranking_record"),
        _relation_count(conn, "analytics.v_aggregated_rankings_latest"),
    )


def _relation_count(conn, relation_name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (relation_name,))
        exists = cur.fetchone()
        if not exists or exists[0] is None:
            return None
        cur.execute(f"SELECT COUNT(*) FROM {relation_name}")
        row = cur.fetchone()
    return 0 if row is None else int(row[0])


if __name__ == "__main__":
    raise SystemExit(main())
