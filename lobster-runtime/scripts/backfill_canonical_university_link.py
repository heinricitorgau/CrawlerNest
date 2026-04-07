#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution.normalizer import normalize_university_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill canonical_university_link using safe deterministic heuristics")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT canonical_university_id, canonical_slug, display_name, country_id
                FROM warehouse.canonical_university
                """
            )
            canonical_rows = cur.fetchall()
            cur.execute(
                """
                SELECT university_id, school_slug, display_name, country_id
                FROM warehouse.universities
                """
            )
            university_rows = cur.fetchall()

            canonical_by_slug: dict[str, tuple[int, int | None]] = {}
            canonical_by_norm: dict[tuple[str, int | None], int] = {}
            for cid, canonical_slug, display_name, country_id in canonical_rows:
                if canonical_slug:
                    canonical_by_slug[str(canonical_slug).strip().lower()] = (int(cid), country_id)
                norm = normalize_university_name(display_name or "")
                if norm:
                    canonical_by_norm[(norm, country_id)] = int(cid)

            inserted = 0
            for university_id, school_slug, display_name, country_id in university_rows:
                matched_canonical_id = None
                link_method = None
                confidence_score = None

                slug_key = (school_slug or "").strip().lower()
                slug_match = canonical_by_slug.get(slug_key)
                if slug_match is not None:
                    candidate_id, candidate_country_id = slug_match
                    if candidate_country_id is None or country_id is None or candidate_country_id == country_id:
                        matched_canonical_id = candidate_id
                        link_method = "slug_exact"
                        confidence_score = 1.0

                if matched_canonical_id is None:
                    norm_key = (normalize_university_name(display_name or ""), country_id)
                    candidate_id = canonical_by_norm.get(norm_key)
                    if candidate_id is not None:
                        matched_canonical_id = candidate_id
                        link_method = "normalized_name"
                        confidence_score = 0.98

                if matched_canonical_id is None:
                    continue

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university_link (
                        canonical_university_id,
                        university_id,
                        link_method,
                        confidence_score,
                        is_primary
                    ) VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (university_id)
                    DO UPDATE SET
                        canonical_university_id = EXCLUDED.canonical_university_id,
                        link_method = EXCLUDED.link_method,
                        confidence_score = EXCLUDED.confidence_score,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (matched_canonical_id, university_id, link_method, confidence_score),
                )
                inserted += 1

        conn.commit()
        print(f"[ok] linked {inserted} universities to canonical entities")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
