"""Populate warehouse.canonical_university from the committed crawl snapshot.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.serving.seed_canonical_from_snapshot \\
        --pg-user test --pg-password test --pg-database clawer

The serving jobs resolve university names to canonical ids, so they need a
populated warehouse. Normally that comes from the pipeline: crawl, stage,
resolve entities, write. This does the minimum needed to give the serving path
something to resolve against, from the snapshot that is already in the
repository -- no crawl, no network.

Two places that is worth having:

- CI, where the serving write path would otherwise be untestable and so has
  never been run automatically.
- A local database you want to point the models at without waiting on a crawl.

**It is not entity resolution.** The real pipeline merges aliases and variant
spellings, so its canonical universities and the snapshot's rows are not
one-to-one. This inserts one row per distinct snapshot name and makes no
attempt to merge anything, so a database seeded this way is fine for exercising
the serving path and wrong for anything that depends on canonical identity.
Idempotent: re-running inserts nothing new.

**It refuses a warehouse that already has canonical universities** unless given
``--allow-populated-warehouse``. Its only dedupe is the slug, so against a real
warehouse it adds a second canonical for every university the pipeline stored
under another spelling. That happened on the live database on 2026-09-04: 2,310
canonicals in one statement, which the resolver then matched by name. QS's MBA
table spells İstanbul Bilgi "Istanbul Bilgi Üniversitesi" and its world table
"İstanbul Bilgi University", so one QS entity ended up ranked on two
universities.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_snapshot


def normalise_display_name(name: str) -> str:
    """Lowercase, punctuation to spaces -- the shape the warehouse column holds."""
    return re.sub(r"[^0-9a-z]+", " ", str(name).lower()).strip()


def slugify(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", str(name).lower()).strip("-")


def refusal_reason(existing_canonicals: int, allow_populated: bool) -> str | None:
    """Why seeding must not run, or None when it may."""
    if existing_canonicals == 0 or allow_populated:
        return None
    return (
        f"warehouse.canonical_university already holds {existing_canonicals} rows. This script "
        "dedupes by slug only, so against a populated warehouse it creates a duplicate canonical "
        "for every university stored under another spelling, and the resolver then splits "
        "sources between them. It is for an empty CI or scratch database. Pass "
        "--allow-populated-warehouse only if you know every snapshot name is already canonical."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed canonical universities from the snapshot.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument(
        "--allow-populated-warehouse",
        action="store_true",
        help="seed even though canonical_university already has rows (creates duplicates; see module docstring)",
    )
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument("--pg-database", default="clawer")
    args = parser.parse_args()

    records = load_snapshot(Path(args.snapshot))

    # The snapshot carries a few rows whose name is a missing-data marker rather
    # than an institution. Seeding a canonical university for those invents an
    # entity, and every such row then resolves onto it.
    placeholders = {"n-a", "na", "none", "unknown", "null"}

    seen: dict[str, str] = {}
    countries: set[str] = set()
    skipped_placeholders = 0
    for record in records:
        name = str(record.get("name") or "").strip()
        if not name:
            continue
        slug = slugify(name)
        if slug in placeholders:
            skipped_placeholders += 1
            continue
        if not slug or slug in seen:
            continue
        country = str(record.get("country") or "").strip()
        seen[slug] = name
        if country and country != "N A":
            countries.add(country)

    print(f"snapshot rows: {len(records)}")
    print(f"distinct slugs: {len(seen)}   distinct countries: {len(countries)}")
    if skipped_placeholders:
        print(f"skipped {skipped_placeholders} rows whose name is a missing-data marker")

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        print("ERROR psycopg2 is required", file=sys.stderr)
        return 2

    connection = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, dbname=args.pg_database,
        user=args.pg_user, password=args.pg_password,
    )
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM warehouse.canonical_university")
                reason = refusal_reason(int(cursor.fetchone()[0]), args.allow_populated_warehouse)
                if reason:
                    print(f"ERROR refusing to seed: {reason}", file=sys.stderr)
                    return 3

                execute_values(
                    cursor,
                    """
                    INSERT INTO warehouse.countries (country_name)
                    VALUES %s
                    ON CONFLICT (country_name) DO NOTHING
                    """,
                    [(c,) for c in sorted(countries)],
                )

                country_ids: dict[str, int] = {}
                cursor.execute("SELECT country_name, country_id FROM warehouse.countries")
                for country_name, country_id in cursor.fetchall():
                    country_ids[country_name] = country_id

                rows = []
                for record in records:
                    name = str(record.get("name") or "").strip()
                    slug = slugify(name)
                    if not slug or slug in placeholders or seen.get(slug) != name:
                        continue
                    country = str(record.get("country") or "").strip()
                    rows.append((
                        slug,
                        name,
                        normalise_display_name(name),
                        country_ids.get(country),
                    ))

                execute_values(
                    cursor,
                    """
                    INSERT INTO warehouse.canonical_university
                        (canonical_slug, display_name, display_name_normalized, country_id)
                    VALUES %s
                    ON CONFLICT (canonical_slug) DO NOTHING
                    """,
                    rows,
                )

                cursor.execute("SELECT count(*) FROM warehouse.canonical_university")
                total = cursor.fetchone()[0]

        print(f"warehouse.canonical_university now holds {total} rows")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
