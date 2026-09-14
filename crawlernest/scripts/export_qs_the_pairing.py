#!/usr/bin/env python3
from __future__ import annotations

"""
Re-export the QS<->THE pairing the warehouse currently holds.

crawlernest-kb/databases/qs_the_pairing_2026.json is the warehouse's answer to
"which QS university is which THE university", kept as a file so the ML jobs
can read it without a database. Nothing keeps the two in step by itself:
re-ingest THE, correct a match, forget the export, and the disagreement model
trains against a pairing that used to be true -- silently, because a stale join
produces a plausible number rather than an error.

test_pairing_matches_warehouse fails when they differ. This is what to run when
it does.

    # show the difference; writes nothing
    ./.venv/bin/python crawlernest/scripts/export_qs_the_pairing.py

    # write it
    ./.venv/bin/python crawlernest/scripts/export_qs_the_pairing.py --commit

This exports what the warehouse says, not a curated answer. A wrong pairing
that is still awaiting review is exported as it stands; correcting it means
deciding the mapping -- see crawlernest/scripts/apply_mapping_reviews.py -- and
re-exporting afterwards. Editing this file by hand only moves the disagreement
to the next ingest.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PAIRING_FILE = (
    REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases" / "qs_the_pairing_2026.json"
)

#: The edition the file describes. The warehouse also holds THE 2025, and
#: reading across editions would propose every 2025-only university as an
#: addition to a 2026 file.
PAIRING_YEAR = 2026

#: Deliberately identical to the query in
#: crawlernest-tests/test_pairing_matches_warehouse.py, including its edition
#: filter. The two are compared against each other, so they have to ask the
#: same question; the nid is the one thing this needs and that does not.
PAIRING_QUERY = """
    SELECT cu.display_name,
           rr.metadata #>> '{raw_row,name}',
           rr.metadata #>> '{raw_row,nid}'
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs USING (ranking_source_id)
    JOIN warehouse.canonical_university cu USING (canonical_university_id)
    WHERE rs.source_code = 'THE'
      AND rr.ranking_year = %s
      AND rr.ranking_type = 'world'
      AND rr.universe_type = 'global'
"""


def load_existing(path: Path) -> dict[str, tuple[str, str]]:
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row["qs_name"]): (str(row.get("the_name") or ""), _id_text(row.get("the_id")))
        for row in rows
    }


def _id_text(value: Any) -> str:
    return "" if value is None else str(value)


def read_warehouse(conn: Any) -> dict[str, tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(PAIRING_QUERY, (PAIRING_YEAR,))
        return {
            str(qs_name): (str(the_name), _id_text(nid))
            for qs_name, the_name, nid in cur.fetchall()
            if the_name
        }


def report(
    existing: dict[str, tuple[str, str]],
    warehouse: dict[str, tuple[str, str]],
) -> None:
    added = sorted(set(warehouse) - set(existing))
    removed = sorted(set(existing) - set(warehouse))
    renamed = [
        (qs, existing[qs][0], warehouse[qs][0])
        for qs in sorted(set(existing) & set(warehouse))
        if existing[qs][0] != warehouse[qs][0]
    ]
    reidentified = [
        (qs, existing[qs][1], warehouse[qs][1])
        for qs in sorted(set(existing) & set(warehouse))
        if existing[qs][0] == warehouse[qs][0] and existing[qs][1] != warehouse[qs][1]
    ]

    print(f"on file   : {len(existing)} pairs")
    print(f"warehouse : {len(warehouse)} pairs")
    print()

    print(f"added     : {len(added)}")
    for qs in added[:20]:
        print(f"  + {qs}  ->  {warehouse[qs][0]}")
    if len(added) > 20:
        print(f"    ... {len(added) - 20} more")

    print(f"removed   : {len(removed)}")
    for qs in removed[:20]:
        print(f"  - {qs}  (was {existing[qs][0]})")
    if len(removed) > 20:
        print(f"    ... {len(removed) - 20} more")

    print(f"re-paired : {len(renamed)}")
    for qs, old, new in renamed[:20]:
        print(f"  ~ {qs}: {old}  ->  {new}")

    print(f"id only   : {len(reidentified)}")
    for qs, old, new in reidentified[:10]:
        print(f"  ~ {qs}: the_id {old or 'null'} -> {new or 'null'}")
    if len(reidentified) > 10:
        print(f"    ... {len(reidentified) - 10} more")


def write(path: Path, warehouse: dict[str, tuple[str, str]]) -> int:
    payload = [
        {"qs_name": qs, "the_name": warehouse[qs][0], "the_id": warehouse[qs][1] or None}
        for qs in sorted(warehouse)
    ]
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return len(payload)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-export the QS<->THE pairing from the warehouse.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="actually write the file. Without it this reports the difference only.",
    )
    parser.add_argument("--out", default=str(PAIRING_FILE), help="pairing file to write")
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument(
        "--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432"))
    )
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        import psycopg2
    except ImportError:
        raise SystemExit(
            "psycopg2 is required. Activate the venv first: source .venv/bin/activate"
        ) from None

    out_path = Path(args.out)
    existing = load_existing(out_path)

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    # Read-only at the session level: this reports on the warehouse and writes
    # only a file.
    conn.set_session(readonly=True, autocommit=True)
    try:
        warehouse = read_warehouse(conn)
    finally:
        conn.close()

    if not warehouse:
        print(
            "The warehouse holds no THE ranking records, so there is no pairing to "
            "export. Ingest THE before running this.",
            file=sys.stderr,
        )
        return 1

    report(existing, warehouse)

    if existing == warehouse:
        print()
        print("The file already matches the warehouse. Nothing to do.")
        return 0

    if not args.commit:
        print()
        print("Report only. Nothing was written. Re-run with --commit to update the file.")
        return 0

    written = write(out_path, warehouse)
    print()
    print(f"Wrote {written} pairs to {out_path}")
    print("Re-run the PostgreSQL tests to confirm the export and the warehouse agree:")
    print("  CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\")
    print("      ./.venv/bin/python crawlernest/crawlernest-tests/run_tests.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
