#!/usr/bin/env python3
"""Retire a QS archive edition that has been re-ingested under a new label.

    retire_relabelled_qs_edition.py --old-year 2016 --new-year 2017            # dry run: checks only
    retire_relabelled_qs_edition.py --old-year 2016 --new-year 2017 --execute  # backup, delete, re-aggregate

Written for the 2026-11-11 relabel of QS's September 2016 table from "2016" to "2017" (the title QS gives that page
today; see crawlernest-kb/qs_archive/manifest.json, entry 2017). The new label is ingested first, by
qs_archive_loader.py, through the normal pipeline. This script then removes the old label, and refuses unless the
two are the same table:

- every QS archive row of the old year has a row in the new year for the same university, with the same position
  and the same printed rank, and the new year has no QS row the old one lacks;
- every old row came from the archive loader (source_version web_archive:...). A live crawl is never touched.

With --execute it takes a pg_dump first, deletes the old QS rows and their missing-entity log, re-aggregates the
old year from warehouse.ranking_record (which drops QS from it), and writes a receipt next to the loader's.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_MODULE_ROOT = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[2]
for _path in (_REPO_ROOT, _MODULE_ROOT, _MODULE_ROOT / "packages", _MODULE_ROOT / "crawlernest-core",
              _MODULE_ROOT / "crawlernest-jobs", _MODULE_ROOT / "crawlernest-extractors"):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

RECEIPT_DIR = _MODULE_ROOT / "crawlernest-kb" / "qs_archive" / "receipts"

_ROWS = """
    SELECT rr.canonical_university_id, rr.rank_position,
           COALESCE(rr.metadata->>'rank_display', rr.metadata->'raw_row'->>'rank'), rr.source_version
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
    WHERE rs.source_code = 'QS' AND rr.ranking_year = %s AND rr.ranking_type = 'world'
      AND rr.universe_type = 'global' AND rr.universe_key = 'global'
"""


def compare(old: list[tuple], new: list[tuple]) -> list[str]:
    """Why the two years are not one table relabelled; empty when they are."""
    problems = []
    not_archive = [row for row in old if not str(row[3] or "").startswith("web_archive:")]
    if not_archive:
        problems.append(f"{len(not_archive)} old rows did not come from the archive loader")
    old_by = {row[0]: (row[1], row[2]) for row in old}
    new_by = {row[0]: (row[1], row[2]) for row in new}
    if not old_by:
        problems.append("the old year holds no QS rows")
    missing = sorted(set(old_by) - set(new_by))
    extra = sorted(set(new_by) - set(old_by))
    differ = sorted(cid for cid in set(old_by) & set(new_by) if old_by[cid] != new_by[cid])
    if missing:
        problems.append(f"{len(missing)} universities ranked in the old year are missing from the new: {missing[:5]}")
    if extra:
        problems.append(f"{len(extra)} universities in the new year are not in the old: {extra[:5]}")
    if differ:
        problems.append(f"{len(differ)} universities have a different rank in the new year: {differ[:5]}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--old-year", type=int, required=True)
    parser.add_argument("--new-year", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    for name, default in (("host", "localhost"), ("database", "clawer"), ("user", "test"), ("password", "test")):
        parser.add_argument(f"--pg-{name}", default=default)
    parser.add_argument("--pg-port", type=int, default=5432)
    args = parser.parse_args(argv)

    import psycopg2

    from qs_archive_loader import PgConfig, make_backup

    conn = psycopg2.connect(host=args.pg_host, port=args.pg_port, dbname=args.pg_database, user=args.pg_user,
                            password=args.pg_password)
    try:
        with conn.cursor() as cur:
            cur.execute(_ROWS, (args.old_year,))
            old = cur.fetchall()
            cur.execute(_ROWS, (args.new_year,))
            new = cur.fetchall()
        problems = compare(old, new)
        print(f"QS {args.old_year}: {len(old)} rows; QS {args.new_year}: {len(new)} rows")
        if problems:
            for line in problems:
                print(f"REFUSED: {line}")
            return 1
        print(f"QS {args.new_year} holds every QS {args.old_year} row with the same rank and printed rank.")
        if not args.execute:
            print("dry run: nothing written (--execute to retire the old label)")
            return 0

        pg = PgConfig(host=args.pg_host, port=args.pg_port, database=args.pg_database, user=args.pg_user,
                      password=args.pg_password)
        backup = make_backup(pg, args.old_year, _REPO_ROOT / ".local" / "backups")
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM warehouse.ranking_record rr
                USING warehouse.ranking_source rs
                WHERE rs.ranking_source_id = rr.ranking_source_id AND rs.source_code = 'QS'
                  AND rr.ranking_year = %s AND rr.source_version LIKE 'web_archive:%%'
                """,
                (args.old_year,),
            )
            deleted = cur.rowcount
            cur.execute("DELETE FROM analytics.missing_entity_log WHERE source_code = 'QS' AND ranking_year = %s",
                        (args.old_year,))
            deleted_log = cur.rowcount
        from pipeline.utils.postgres import build_multi_source_pipeline

        pipeline = build_multi_source_pipeline(conn)
        aggregated = pipeline._refresh_aggregations([args.old_year], ranking_type="world",
                                                    run_label_prefix=f"qs_relabel_{args.old_year}_to_{args.new_year}")
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), count(*) FILTER (WHERE source_ranks_json->>'QS' IS NOT NULL) "
                        "FROM analytics.aggregated_rankings WHERE ranking_year = %s", (args.old_year,))
            rows_after, with_qs_after = cur.fetchone()
        if with_qs_after:
            conn.rollback()
            print(f"REFUSED after the fact: {with_qs_after} aggregated {args.old_year} rows still carry a QS rank; "
                  "rolled back")
            return 1
        conn.commit()
    finally:
        conn.close()

    receipt = {
        "action": "retire_relabelled_qs_edition",
        "old_year": args.old_year,
        "new_year": args.new_year,
        "started_utc": started,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database": args.pg_database,
        "verified_identical_rows": len(old),
        "deleted_ranking_records": deleted,
        "deleted_missing_entity_log": deleted_log,
        "reaggregated_rows": aggregated,
        "aggregated_rows_after": rows_after,
        "backup": {"path": str(backup), "bytes": Path(backup).stat().st_size},
        "rollback": f"pg_restore -h {args.pg_host} -p {args.pg_port} -U {args.pg_user} -d {args.pg_database} "
                    f"--clean --if-exists {backup}",
    }
    path = RECEIPT_DIR / f"{args.old_year}_retired_as_{args.new_year}_{started}.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("deleted_ranking_records", "deleted_missing_entity_log",
                                                 "reaggregated_rows", "aggregated_rows_after")}))
    print(f"receipt -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
