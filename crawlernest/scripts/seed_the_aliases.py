#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from typing import Optional

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg2 is required to run this script.") from exc


THE_ALIAS_MAP = {
    "University of California, Berkeley": "university-of-california,-berkeley-ucb",
    "National University of Singapore": "national-university-of-singapore-nus",
    "University of Hong Kong": "the-university-of-hong-kong",
    "LMU Munich": "ludwig-maximilians-universität-münchen",
    "École Polytechnique Fédérale de Lausanne": "epfl-–-école-polytechnique-fédérale-de-lausanne",
    "Paris Sciences et Lettres – PSL Research University Paris": "université-psl",
    "Universität Heidelberg": "universität-heidelberg",
    "Nanyang Technological University, Singapore": "nanyang-technological-university,-singapore-ntu-singapore",
    "The Chinese University of Hong Kong": "the-chinese-university-of-hong-kong-cuhk",
    "University of Illinois at Urbana-Champaign": "university-of-illinois-urbana-champaign",
    "University of California, Los Angeles": "university-of-california,-los-angeles-ucla",
    "University of California, San Diego": "university-of-california,-san-diego-ucsd",
    "University of Michigan-Ann Arbor": "university-of-michigan-ann-arbor",
    "Shanghai Jiao Tong University": "shanghai-jiao-tong-university",
    "Georgia Institute of Technology": "georgia-institute-of-technology",
    "The University of Tokyo": "the-university-of-tokyo",
    "Technical University of Munich": "technical-university-of-munich",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed manual THE aliases into warehouse.university_alias."
    )
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    return parser.parse_args()


def connect_postgres(
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
):
    return psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )


def normalize_alias(alias_text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(alias_text or "").strip().lower())
    return " ".join(normalized.split())


def main() -> int:
    args = parse_args()
    conn = connect_postgres(
        args.pg_host,
        args.pg_port,
        args.pg_database,
        args.pg_user,
        args.pg_password,
    )

    inserted = 0
    skipped = 0
    not_found = 0

    try:
        with conn.cursor() as cur:
            for the_name, canonical_slug in THE_ALIAS_MAP.items():
                cur.execute(
                    """
                    SELECT canonical_university_id
                    FROM warehouse.canonical_university
                    WHERE canonical_slug = %s
                    """,
                    (canonical_slug,),
                )
                row = cur.fetchone()
                if row is None:
                    not_found += 1
                    print(
                        f"[warn] canonical slug not found for THE alias: "
                        f"{the_name} -> {canonical_slug}"
                    )
                    continue

                canonical_university_id = int(row[0])
                cur.execute(
                    """
                    INSERT INTO warehouse.university_alias (
                        canonical_university_id,
                        alias_text,
                        alias_normalized,
                        source_name,
                        created_at
                    )
                    VALUES (%s, %s, %s, 'THE_MANUAL', NOW())
                    ON CONFLICT DO NOTHING
                    RETURNING alias_id
                    """,
                    (
                        canonical_university_id,
                        the_name,
                        normalize_alias(the_name),
                    ),
                )
                inserted_row = cur.fetchone()
                if inserted_row is not None:
                    inserted += 1
                else:
                    skipped += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"[seed-the-aliases] inserted={inserted} skipped={skipped} not_found={not_found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
