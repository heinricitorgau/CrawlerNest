#!/usr/bin/env python3
from __future__ import annotations

"""
Repair the normalized names that lost their letters, and the join that reads them.

``warehouse.canonical_university.display_name_normalized`` was written over
several years by more than one rule. Most of the disagreement with today's
``normalize_university_name`` is a word-level difference -- the older rule kept
"of" and "and" where the current one drops them -- and that is a style choice,
not damage, so this leaves it alone.

381 rows are different: every accented letter became a space.

    'Boğaziçi University'      -> 'bo azi i university'
    'Abdullah Gül University'  -> 'abdullah g l university'
    'Arts et Métiers ParisTech'-> 'arts et m tiers paristech'

Those are wrong under any rule. A normalized name exists to be compared, and
one with holes in it matches nothing -- including the canonical it was derived
from.

The reason this is a script and not an UPDATE is the second half.
``clawer.repository.JdbcScopedRankingReadAdapter`` joins

    ON cu.display_name_normalized = dp.normalized_university_name

against ``warehouse.ranking_decision_preview``, whose copy of the string was
taken from this column when the preview was built. Correcting one side alone
silently drops every affected row out of that read path -- measured at 1,777
preview rows for a full recompute, 348 for this narrower repair. So both sides
move together, in one transaction, and the run refuses if the corrected name
already exists in the preview under another row.

    # what would change; writes nothing
    ./.venv/bin/python crawlernest/scripts/fix_canonical_normalized_names.py

    # write it
    ./.venv/bin/python crawlernest/scripts/fix_canonical_normalized_names.py --commit
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "crawlernest"
for _path in (MODULE_ROOT / "crawlernest-core", REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from entity_resolution.normalizer import normalize_university_name  # noqa: E402

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]

_LETTERS = re.compile(r"[^a-z0-9]")


def letters_only(value: str | None) -> str:
    return _LETTERS.sub("", value or "")


@dataclass(frozen=True)
class Repair:
    canonical_university_id: int
    display_name: str
    stored: str
    corrected: str
    preview_rows: int


def find_repairs(conn) -> tuple[list[Repair], int]:
    """The rows whose stored form lost characters, and how many only differ by rule.

    Damage is narrower than difference: the stored value has to hold *fewer*
    letters than the current rule produces. A rule that removed a whole word
    leaves the remaining letters intact, so it fails that test and is skipped.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT canonical_university_id, display_name, display_name_normalized
              FROM warehouse.canonical_university
             ORDER BY canonical_university_id
            """
        )
        canonical = cur.fetchall()
        cur.execute(
            """
            SELECT normalized_university_name, count(*)
              FROM warehouse.ranking_decision_preview
             GROUP BY 1
            """
        )
        preview = dict(cur.fetchall())

    repairs: list[Repair] = []
    rule_differences = 0
    for cid, display_name, stored in canonical:
        corrected = normalize_university_name(display_name or "")
        if stored == corrected:
            continue
        if len(letters_only(stored)) < len(letters_only(corrected)):
            repairs.append(
                Repair(
                    canonical_university_id=int(cid),
                    display_name=display_name,
                    stored=stored,
                    corrected=corrected,
                    preview_rows=int(preview.get(stored, 0)),
                )
            )
        else:
            rule_differences += 1
    return repairs, rule_differences


def blocking_collisions(conn, repairs: list[Repair]) -> list[Repair]:
    """Repairs whose corrected name is already taken in the preview.

    ``ranking_decision_preview`` is unique on (normalized_university_name,
    ranking_year). Renaming into a name that already exists would raise mid-way;
    refusing up front keeps the run all-or-nothing rather than half-applied.
    """
    if not repairs:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT normalized_university_name FROM warehouse.ranking_decision_preview"
        )
        taken = {row[0] for row in cur.fetchall()}
    return [r for r in repairs if r.preview_rows and r.corrected in taken]


def apply(conn, repairs: list[Repair]) -> tuple[int, int]:
    canonical_updated = preview_updated = 0
    with conn.cursor() as cur:
        for repair in repairs:
            # The preview first: for the moment between the two statements the
            # join should point at a name that still exists on both sides.
            if repair.preview_rows:
                cur.execute(
                    """
                    UPDATE warehouse.ranking_decision_preview
                       SET normalized_university_name = %s
                     WHERE normalized_university_name = %s
                    """,
                    (repair.corrected, repair.stored),
                )
                preview_updated += cur.rowcount
            cur.execute(
                """
                UPDATE warehouse.canonical_university
                   SET display_name_normalized = %s,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE canonical_university_id = %s
                   AND display_name_normalized = %s
                """,
                (repair.corrected, repair.canonical_university_id, repair.stored),
            )
            canonical_updated += cur.rowcount
    return canonical_updated, preview_updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="actually write; without it this only reports")
    parser.add_argument("--show", type=int, default=12, help="how many repairs to print")
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432")))
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    args = parser.parse_args()

    if psycopg2 is None:
        raise SystemExit("psycopg2 is required")

    conn = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, dbname=args.pg_database,
        user=args.pg_user, password=args.pg_password,
    )
    conn.set_client_encoding("UTF8")
    try:
        repairs, rule_differences = find_repairs(conn)
        affected_preview_rows = sum(r.preview_rows for r in repairs)
        print(f"rows whose normalized form lost characters : {len(repairs)}")
        print(f"rows that only differ by a word-level rule : {rule_differences}  (left alone)")
        print(f"preview rows that move with them           : {affected_preview_rows}")

        collisions = blocking_collisions(conn, repairs)
        if collisions:
            print(f"\nREFUSING: {len(collisions)} corrected name(s) already exist in the preview:")
            for repair in collisions[: args.show]:
                print(f"  {repair.canonical_university_id}: {repair.corrected!r}")
            return 1

        for repair in repairs[: args.show]:
            print(f"\n  {repair.canonical_university_id}: {repair.display_name!r}")
            print(f"    stored    {repair.stored!r}")
            print(f"    corrected {repair.corrected!r}")
            if repair.preview_rows:
                print(f"    preview   {repair.preview_rows} row(s) renamed with it")
        if len(repairs) > args.show:
            print(f"\n  ... and {len(repairs) - args.show} more")

        if not args.commit:
            print("\nReport only. Nothing was written. Re-run with --commit to apply.")
            return 0

        canonical_updated, preview_updated = apply(conn, repairs)
        conn.commit()
        print(f"\nUpdated {canonical_updated} canonical row(s) and {preview_updated} preview row(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
