#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution.normalizer import normalize_university_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed canonical_university / university_alias / canonical_university_link from warehouse.universities"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    parser.add_argument("--source-name", default="legacy_universities")
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
                SELECT
                    u.university_id,
                    u.school_slug,
                    u.display_name,
                    u.canonical_name,
                    u.country_id,
                    u.city_name,
                    u.website_url,
                    ua.source_name,
                    ua.source_school_name
                FROM warehouse.universities u
                LEFT JOIN warehouse.university_aliases ua
                  ON ua.university_id = u.university_id
                ORDER BY u.university_id, ua.alias_id NULLS LAST
                """
            )
            rows = cur.fetchall()

            grouped: dict[int, dict[str, object]] = {}
            for (
                university_id,
                school_slug,
                display_name,
                canonical_name,
                country_id,
                city_name,
                website_url,
                alias_source_name,
                alias_text,
            ) in rows:
                bucket = grouped.setdefault(
                    int(university_id),
                    {
                        "school_slug": school_slug,
                        "display_name": display_name,
                        "canonical_name": canonical_name,
                        "country_id": country_id,
                        "city_name": city_name,
                        "website_url": website_url,
                        "aliases": [],
                    },
                )
                if alias_text:
                    bucket["aliases"].append((alias_source_name or args.source_name, alias_text))

            seeded = 0
            alias_inserted = 0
            linked = 0
            source_mapped = 0

            for university_id, payload in grouped.items():
                school_slug = str(payload["school_slug"] or "").strip()
                display_name = str(payload["display_name"] or payload["canonical_name"] or school_slug).strip()
                canonical_name = str(payload["canonical_name"] or "").strip() or display_name
                normalized = normalize_university_name(display_name)
                metadata = {
                    "seed_origin": "warehouse.universities",
                    "university_id": university_id,
                    "school_slug": school_slug,
                }

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university (
                        canonical_slug,
                        display_name,
                        display_name_normalized,
                        native_name,
                        country_id,
                        city_name,
                        website_url,
                        status,
                        metadata
                    ) VALUES (%s, %s, %s, NULL, %s, %s, %s, 'active', %s::jsonb)
                    ON CONFLICT (canonical_slug)
                    DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        display_name_normalized = EXCLUDED.display_name_normalized,
                        country_id = COALESCE(warehouse.canonical_university.country_id, EXCLUDED.country_id),
                        city_name = COALESCE(warehouse.canonical_university.city_name, EXCLUDED.city_name),
                        website_url = COALESCE(warehouse.canonical_university.website_url, EXCLUDED.website_url),
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING canonical_university_id
                    """,
                    (
                        school_slug,
                        canonical_name,
                        normalized,
                        payload["country_id"],
                        payload["city_name"],
                        payload["website_url"],
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
                canonical_university_id = int(cur.fetchone()[0])
                seeded += 1

                cur.execute(
                    """
                    INSERT INTO warehouse.canonical_university_link (
                        canonical_university_id,
                        university_id,
                        link_method,
                        confidence_score,
                        is_primary,
                        metadata
                    ) VALUES (%s, %s, 'seed_from_university', 1.0000, TRUE, %s::jsonb)
                    ON CONFLICT (university_id)
                    DO UPDATE SET
                        canonical_university_id = EXCLUDED.canonical_university_id,
                        link_method = EXCLUDED.link_method,
                        confidence_score = EXCLUDED.confidence_score,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        canonical_university_id,
                        university_id,
                        json.dumps({"school_slug": school_slug}, ensure_ascii=False),
                    ),
                )
                linked += 1

                alias_rows = [(None, canonical_name), (args.source_name, display_name)]
                alias_rows.extend(payload["aliases"])
                seen_aliases: set[tuple[str, str]] = set()
                for source_name, alias_text in alias_rows:
                    alias_clean = str(alias_text or "").strip()
                    if not alias_clean:
                        continue
                    alias_normalized = normalize_university_name(alias_clean)
                    dedup_key = (source_name or "", alias_normalized)
                    if not alias_normalized or dedup_key in seen_aliases:
                        continue
                    seen_aliases.add(dedup_key)
                    cur.execute(
                        """
                        INSERT INTO warehouse.university_alias (
                            canonical_university_id,
                            alias_text,
                            alias_normalized,
                            language_code,
                            script_code,
                            source_name,
                            is_primary,
                            is_abbreviation,
                            metadata
                        ) VALUES (%s, %s, %s, NULL, NULL, %s, %s, FALSE, %s::jsonb)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            canonical_university_id,
                            alias_clean,
                            alias_normalized,
                            source_name,
                            alias_clean == canonical_name,
                            json.dumps({"seeded_from": "seed_canonical_from_universities"}, ensure_ascii=False),
                        ),
                    )
                    alias_inserted += cur.rowcount

                cur.execute(
                    """
                    INSERT INTO warehouse.source_mapping (
                        source_name,
                        source_entity_id,
                        canonical_university_id,
                        matched_alias_id,
                        match_method,
                        confidence_score,
                        threshold_used,
                        review_status,
                        metadata
                    ) VALUES (%s, %s, %s, NULL, 'seed', 1.0000, 1.0000, 'auto_accepted', %s::jsonb)
                    ON CONFLICT (source_name, source_entity_id)
                    DO UPDATE SET
                        canonical_university_id = EXCLUDED.canonical_university_id,
                        match_method = EXCLUDED.match_method,
                        confidence_score = EXCLUDED.confidence_score,
                        threshold_used = EXCLUDED.threshold_used,
                        review_status = EXCLUDED.review_status,
                        last_seen_at = CURRENT_TIMESTAMP,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        args.source_name,
                        school_slug,
                        canonical_university_id,
                        json.dumps({"school_slug": school_slug, "seeded": True}, ensure_ascii=False),
                    ),
                )
                source_mapped += 1

        conn.commit()
        print(f"[ok] seeded canonical_university rows: {seeded}")
        print(f"[ok] inserted canonical aliases: {alias_inserted}")
        print(f"[ok] linked universities: {linked}")
        print(f"[ok] upserted source mappings: {source_mapped}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
