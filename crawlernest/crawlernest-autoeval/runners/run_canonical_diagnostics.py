#!/usr/bin/env python3
"""Canonical matching diagnostics — read-only.

Reports:
  - Low-confidence entity matches (confidence_score < threshold)
  - Unresolved universities per source
  - Duplicate canonical collisions (multiple sources map to the same slug)
  - Same normalized display_name across different countries

Does NOT modify any data.

Usage
-----
  python run_canonical_diagnostics.py [--pg-password test] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def connect(host: str, port: int, database: str, user: str, password: str):
    try:
        import psycopg2  # type: ignore
        return psycopg2.connect(host=host, port=port, database=database,
                                user=user, password=password)
    except ImportError:
        print("ERROR psycopg2 not installed — run: pip install psycopg2-binary")
        sys.exit(2)
    except Exception as exc:
        print(f"ERROR cannot connect to PostgreSQL: {exc}")
        sys.exit(2)


def _rows(conn, sql: str, params=None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def get_low_confidence_matches(conn, threshold: float = 0.80) -> list[dict[str, Any]]:
    rows = _rows(conn, """
        SELECT sm.source_name, sm.confidence_score, sm.match_method,
               cu.canonical_slug, cu.display_name
        FROM warehouse.source_mapping sm
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = sm.canonical_university_id
        WHERE sm.confidence_score < %s
          AND sm.is_active = TRUE
        ORDER BY sm.confidence_score ASC
        LIMIT 20
    """, (threshold,))
    return [{"source_name": r[0], "confidence_score": float(r[1]),
             "match_method": r[2], "canonical_slug": r[3], "display_name": r[4]}
            for r in rows]


def get_unresolved_by_source(conn) -> list[dict[str, Any]]:
    rows = _rows(conn, """
        SELECT source_code,
               COUNT(*) AS total,
               MAX(created_at) AS latest_at
        FROM analytics.missing_entity_log
        GROUP BY source_code
        ORDER BY total DESC
    """)
    return [{"source_code": r[0], "total": int(r[1]),
             "latest_at": str(r[2]) if r[2] else None}
            for r in rows]


def get_unresolved_examples(conn, limit: int = 10) -> list[dict[str, Any]]:
    rows = _rows(conn, """
        SELECT source_code, raw_name, country_hint, ranking_year, created_at
        FROM analytics.missing_entity_log
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    return [{"source_code": r[0], "raw_name": r[1], "country_hint": r[2],
             "ranking_year": r[3], "created_at": str(r[4]) if r[4] else None}
            for r in rows]


def get_canonical_collisions(conn) -> list[dict[str, Any]]:
    """Find canonical slugs that are mapped from multiple distinct source entities."""
    rows = _rows(conn, """
        SELECT cu.canonical_slug, cu.display_name,
               COUNT(DISTINCT sm.source_name || ':' || sm.source_entity_id) AS source_entity_count,
               STRING_AGG(DISTINCT sm.source_name, ', ' ORDER BY sm.source_name) AS sources
        FROM warehouse.source_mapping sm
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = sm.canonical_university_id
        WHERE sm.is_active = TRUE
        GROUP BY cu.canonical_slug, cu.display_name
        HAVING COUNT(DISTINCT sm.source_name || ':' || sm.source_entity_id) > 3
        ORDER BY source_entity_count DESC
        LIMIT 20
    """)
    return [{"canonical_slug": r[0], "display_name": r[1],
             "source_entity_count": int(r[2]), "sources": r[3]}
            for r in rows]


def get_same_name_across_countries(conn) -> list[dict[str, Any]]:
    """Find display_name_normalized values that appear in more than one country."""
    rows = _rows(conn, """
        SELECT cu.display_name_normalized,
               COUNT(DISTINCT c.country_id) AS country_count,
               STRING_AGG(DISTINCT c.country_name, ', ' ORDER BY c.country_name) AS countries
        FROM warehouse.canonical_university cu
        LEFT JOIN warehouse.countries c ON c.country_id = cu.country_id
        WHERE cu.status = 'active'
        GROUP BY cu.display_name_normalized
        HAVING COUNT(DISTINCT c.country_id) > 1
        ORDER BY country_count DESC
        LIMIT 15
    """)
    return [{"display_name_normalized": r[0], "country_count": int(r[1]),
             "countries": r[2]}
            for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical matching diagnostics")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--confidence-threshold", type=float, default=0.80,
                        help="Flag matches below this confidence score")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    conn = connect(args.pg_host, args.pg_port, args.pg_database,
                   args.pg_user, args.pg_password)
    try:
        low_conf = get_low_confidence_matches(conn, args.confidence_threshold)
        unresolved_by_src = get_unresolved_by_source(conn)
        unresolved_examples = get_unresolved_examples(conn)
        collisions = get_canonical_collisions(conn)
        name_conflicts = get_same_name_across_countries(conn)
    finally:
        conn.close()

    report = {
        "low_confidence_matches": {
            "threshold": args.confidence_threshold,
            "count": len(low_conf),
            "examples": low_conf,
        },
        "unresolved_by_source": unresolved_by_src,
        "unresolved_examples": unresolved_examples,
        "canonical_collisions": {
            "description": "Canonical entities mapped from >3 distinct source entities",
            "count": len(collisions),
            "examples": collisions,
        },
        "same_name_across_countries": {
            "description": "Normalized display names shared across multiple countries",
            "count": len(name_conflicts),
            "examples": name_conflicts,
        },
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=== Canonical Matching Diagnostics ===")
    print()
    print(f"Low-confidence matches (< {args.confidence_threshold}): {len(low_conf)}")
    for m in low_conf[:5]:
        print(f"  {m['source_name']} | score={m['confidence_score']:.3f} | {m['display_name']}")

    print()
    print("Unresolved universities by source:")
    if unresolved_by_src:
        for u in unresolved_by_src:
            print(f"  {u['source_code']}: {u['total']} unresolved")
    else:
        print("  (none)")

    print()
    print(f"Canonical collisions (slug mapped from >3 source entities): {len(collisions)}")
    for c in collisions[:5]:
        print(f"  {c['canonical_slug']}: {c['source_entity_count']} mappings from [{c['sources']}]")

    print()
    print(f"Same normalized name across countries: {len(name_conflicts)}")
    for n in name_conflicts[:5]:
        print(f"  '{n['display_name_normalized']}' in {n['country_count']} countries: {n['countries']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
