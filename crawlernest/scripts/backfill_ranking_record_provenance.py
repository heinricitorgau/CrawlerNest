#!/usr/bin/env python3
from __future__ import annotations

"""
Fill warehouse.ranking_record.source_mapping_id for rows written before the
writer set it.

The rule, and why each row is or is not linked, lives in
crawlernest-core/multi_source/mapping_provenance.py. This prints that
classification per source and, with --commit, applies it. It only ever turns a
NULL into an id; it never changes or clears a value already set.

    # preview -- the default; writes nothing
    ./.venv/bin/python crawlernest/scripts/backfill_ranking_record_provenance.py

    # apply
    ./.venv/bin/python crawlernest/scripts/backfill_ranking_record_provenance.py --commit

    # one edition only
    ./.venv/bin/python crawlernest/scripts/backfill_ranking_record_provenance.py --ranking-year 2026

Safe to re-run: a second pass finds nothing left to fill. The legacy writer
(pipeline/commands/canonical.py, backfill_qs_ranking_records_from_legacy)
inserts rows without an entity id, so run this again after it.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

CORE_DIR = Path(__file__).resolve().parents[1] / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from multi_source.mapping_provenance import LINKED_BASES, backfill, classify, conflicts  # noqa: E402


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill ranking_record.source_mapping_id from evidence.")
    parser.add_argument(
        "--ranking-year",
        type=int,
        action="append",
        default=[],
        help="limit to this edition (repeatable); every year by default",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="actually write. Without it this previews and changes nothing.",
    )
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432")))
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    return parser.parse_args(argv)


def _print_classification(rows) -> int:
    print(f"{'source':<6} {'basis':<38} {'records':>8} {'already':>8} {'to fill':>8}")
    to_fill = 0
    for row in rows:
        marker = "" if row.basis in LINKED_BASES else "   (stays NULL)"
        print(f"{row.source_code:<6} {row.basis:<38} {row.records:>8} {row.already_set:>8} {row.to_fill:>8}{marker}")
        if row.disagrees_with_current:
            print(f"{'':<6} {'':<38} {row.disagrees_with_current} row(s) already set to a different mapping; left as set")
        to_fill += row.to_fill
    return to_fill


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        import psycopg2
    except ImportError:
        raise SystemExit("psycopg2 is required. Activate the venv first: source .venv/bin/activate") from None

    years = args.ranking_year or None
    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    try:
        to_fill = _print_classification(classify(conn, years))

        found = conflicts(conn, years)
        if found:
            print()
            print("Left NULL because the row and the entity it names disagree:")
            for source, record_id, year, universe, name, url, basis, mapped_id, mapped_name in found:
                print(f"  {source} #{record_id} {year} {universe}: row credits {name!r}; "
                      f"{url} {'now resolves to ' + repr(mapped_name) if mapped_name else 'is retired'} "
                      f"[{basis}]")

        print()
        if not args.commit:
            print(f"Preview only. {to_fill} row(s) would be filled. Re-run with --commit to apply.")
            return 0
        if not to_fill:
            print("Nothing to fill.")
            return 0

        filled = backfill(conn, years)
        print(f"Filled source_mapping_id on {filled} row(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
