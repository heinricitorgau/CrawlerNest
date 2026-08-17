#!/usr/bin/env python3
"""Seed a reviewed alias file into ``warehouse.university_alias``.

The alias files under ``crawlernest/crawlernest-kb/databases/`` are the reviewed
record of which source name belongs to which canonical university. Until this
script existed they were applied by hand, which meant the committed file and the
database agreed only as long as nobody re-created the database -- the file
documented a state it could not restore.

Usage::

    python3 crawlernest/scripts/seed_alias_file.py \\
        --alias-file crawlernest/crawlernest-kb/databases/arwu_university_aliases_2026.json \\
        --pg-password test

``--dry-run`` reports what would be inserted and touches nothing. Re-running is
safe: rows conflict on ``uq_university_alias_dedup`` and are skipped, so the
script converges on the file rather than accumulating duplicates.

The file may carry a ``method`` of ``rule`` or ``curated``. Both are seeded --
the distinction is for review, not for loading -- but the counts are reported
separately so that a run makes visible how much of the batch rests on an
asserted fact about an institution rather than on a stated rule.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import psycopg2
except ImportError as exc:  # pragma: no cover
    raise SystemExit("psycopg2 is required to run this script.") from exc


def normalize_alias(alias_text: str) -> str:
    """The form stored in ``university_alias.alias_normalized``.

    Deliberately not ``normalize_university_name``: that one preserves case, and
    every one of the rows already in the table is lower-cased. Writing the other
    form would not collide with the dedup index, so a re-run would quietly add a
    second row for an alias that is already there.
    """
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(alias_text or "").strip().lower()).split())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--alias-file", required=True, type=Path)
    parser.add_argument("--source-name", default=None,
                        help="value for university_alias.source_name "
                             "(default: the file's own 'source' field)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = json.loads(args.alias_file.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise SystemExit(f"{args.alias_file}: expected a list of alias objects")

    conn = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, database=args.pg_database,
        user=args.pg_user, password=args.pg_password,
    )
    inserted = Counter()
    skipped = 0
    missing: list[str] = []
    try:
        with conn.cursor() as cur:
            for entry in entries:
                canonical_id = entry.get("canonical_university_id")
                alias_text = entry.get("alias_text")
                if canonical_id is None or not alias_text:
                    raise SystemExit(f"alias entry lacks an id or text: {entry!r}")

                # A canonical id that no longer exists means the file has drifted
                # from the warehouse. Report every one rather than stopping at the
                # first, so a stale file can be repaired in a single pass.
                cur.execute(
                    "SELECT 1 FROM warehouse.canonical_university "
                    "WHERE canonical_university_id = %s",
                    (canonical_id,),
                )
                if cur.fetchone() is None:
                    missing.append(f"#{canonical_id} {alias_text!r}")
                    continue

                source_name = args.source_name or entry.get("source")
                if args.dry_run:
                    # Counting the file's rows would report 70 inserts for a file
                    # whose rows are already all present. The dry run has to ask
                    # the same question the insert asks -- the dedup index --
                    # or it is a number rather than a check.
                    cur.execute(
                        """
                        SELECT 1 FROM warehouse.university_alias
                        WHERE canonical_university_id = %s
                          AND alias_normalized = %s
                          AND COALESCE(language_code, '') = ''
                          AND COALESCE(source_name, '') = COALESCE(%s, '')
                        """,
                        (canonical_id, normalize_alias(alias_text), source_name),
                    )
                    if cur.fetchone() is None:
                        inserted[entry.get("method", "rule")] += 1
                    else:
                        skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO warehouse.university_alias (
                        canonical_university_id, alias_text, alias_normalized,
                        source_name, metadata, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT DO NOTHING
                    RETURNING alias_id
                    """,
                    (
                        canonical_id,
                        alias_text,
                        normalize_alias(alias_text),
                        source_name,
                        json.dumps({k: entry[k] for k in ("method", "reason")
                                    if k in entry}) or None,
                    ),
                )
                if cur.fetchone() is None:
                    skipped += 1
                else:
                    inserted[entry.get("method", "rule")] += 1
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    verb = "would insert" if args.dry_run else "inserted"
    print(f"{args.alias_file.name}: {len(entries)} entries")
    print(f"  {verb} : {sum(inserted.values())}  {dict(inserted)}")
    print(f"  already present : {skipped}")
    if missing:
        print(f"  NO SUCH CANONICAL UNIVERSITY : {len(missing)}")
        for item in missing:
            print(f"    {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
