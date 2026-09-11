#!/usr/bin/env python3
from __future__ import annotations

"""
Re-key ARWU entity ids from the year-bearing form to ShanghaiRanking's own slug.

ARWU rows used to be ingested as ``arwu:{year}:{slug of the printed name}``.
The crawler now emits ``arwu:{univUp}`` -- the source's institution slug, which
has no year in it and survives renames (see ``arwu_crawler.arwu_source_id``).
Every human decision in warehouse.mapping_review is keyed by the old form, so
the first ingest under the new crawler would find none of them. The pipeline
refuses that ingest (``multi_source.reviews.refuse_reappeared_reviews``); this
script is the fix it points at.

It rewrites the id in place on exactly two tables:

  warehouse.mapping_review            the decisions -- the reason this exists
  warehouse.source_university_mapping the resolver's rows, in place so that
                                      source_mapping_id is unchanged; the
                                      provenance backfill on ranking_record
                                      points at those ids and must not have to
                                      be redone

analytics.entity_resolution_event and analytics.missing_entity_log are logs of
what happened under the old ids and are left as history.

The new id is looked up, never derived. For 19 of the 61 reviewed entities in
the 2026 data, ``univUp`` is not the slug of the printed name
("university-of-texas-southwestern-medical-center" is
"the-university-of-texas-southwestern-medical-center-at-dallas"), so stripping
the year would orphan a third of the decisions. The lookup comes from a crawl of
the same edition the old ids came from: the old slug is ``_slugify`` of that
edition's printed name, and only that edition's names are guaranteed to
reproduce it.

    # preview -- the default; writes nothing. Crawls the 2026 edition first.
    ./.venv/bin/python crawlernest/scripts/rekey_arwu_source_ids.py --crawl-year 2026

    # or from a crawl output the new crawler already wrote
    ./.venv/bin/python crawlernest/scripts/rekey_arwu_source_ids.py \\
        --rows-json crawlernest/crawlernest-kb/databases/arwu_rankings_2026.json

    # apply, in one transaction, with an audit file of every old -> new pair
    ./.venv/bin/python crawlernest/scripts/rekey_arwu_source_ids.py --crawl-year 2026 \\
        --commit --audit-out rekey_arwu_2026.json

Every id must resolve, and no two may collide, before anything is written. One
unresolvable id fails the run rather than leaving the decisions half re-keyed.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

JOBS_DIR = Path(__file__).resolve().parents[1] / "crawlernest-jobs"
if str(JOBS_DIR) not in sys.path:
    sys.path.insert(0, str(JOBS_DIR))

from arwu_crawler import _slugify, _univ_up_from_link, arwu_source_id  # noqa: E402

SOURCE_CODE = "ARWU"
REVIEW_TABLE = "warehouse.mapping_review"
MAPPING_TABLE = "warehouse.source_university_mapping"
TABLES = (REVIEW_TABLE, MAPPING_TABLE)

#: ``arwu:2026:ruhr-university-bochum`` -- the form being retired.
_YEAR_BEARING = re.compile(r"^arwu:((?:19|20)\d{2}):(.+)$")
#: ``arwu:ruhr-university-bochum`` -- already stable, nothing to do.
_STABLE = re.compile(r"^arwu:[a-z0-9]+(?:-[a-z0-9]+)*$")
#: ``arwu:name:<slug>`` -- name-derived; the new crawler's fallback. Stable
#: across years, but not source-assigned. Left alone and reported.
_NAME_DERIVED = re.compile(r"^arwu:name:")


@dataclass(frozen=True)
class Rekey:
    table: str
    old_id: str
    new_id: str
    via: str  # "crosswalk" or "profile_url"


def crosswalk_from_rows(rows: Iterable[dict[str, Any]]) -> tuple[dict[tuple[int, str], str], list[str]]:
    """``(edition year, slug of printed name) -> arwu:<univUp>`` from crawl output rows.

    Only rows whose id is source-assigned are used; a name-derived id is no
    better than the id it would replace. A slug that maps to two different
    institutions is reported, not guessed.
    """
    candidates: dict[tuple[int, str], set[str]] = {}
    for row in rows:
        new_id = str(row.get("id") or "")
        if not _STABLE.match(new_id):
            continue
        try:
            year = int(row.get("year"))
        except (TypeError, ValueError):
            continue
        slug = _slugify(str(row.get("name") or ""))
        if slug:
            candidates.setdefault((year, slug), set()).add(new_id)

    crosswalk: dict[tuple[int, str], str] = {}
    problems: list[str] = []
    for key, ids in sorted(candidates.items()):
        if len(ids) > 1:
            problems.append(
                f"{key[0]} name slug {key[1]!r} belongs to more than one institution: {sorted(ids)}"
            )
            continue
        crosswalk[key] = next(iter(ids))
    return crosswalk, problems


def plan_rekey(
    ids_by_table: dict[str, set[str]],
    crosswalk: dict[tuple[int, str], str],
) -> tuple[list[Rekey], list[str], list[str]]:
    """Pair every retiring id with its replacement.

    Returns ``(plan, problems, notes)``. Any problem means nothing may be
    written: an unresolved id, an edition the crosswalk does not cover, or two
    rows that would land on one id where the table allows only one.
    """
    plan: list[Rekey] = []
    problems: list[str] = []
    notes: list[str] = []
    years_covered = {year for year, _ in crosswalk}

    for table in TABLES:
        existing = ids_by_table.get(table, set())
        targets: dict[str, str] = {}
        for old_id in sorted(existing):
            if _STABLE.match(old_id):
                continue
            if _NAME_DERIVED.match(old_id):
                notes.append(f"{table}: {old_id} is name-derived; left as is")
                continue

            new_id: Optional[str] = None
            via = ""
            year_bearing = _YEAR_BEARING.match(old_id)
            if year_bearing:
                year, slug = int(year_bearing.group(1)), year_bearing.group(2)
                if year not in years_covered:
                    problems.append(
                        f"{table}: {old_id} is from the {year} edition, which the crosswalk does "
                        f"not cover; crawl {year} (--crawl-year {year})"
                    )
                    continue
                new_id = crosswalk.get((year, slug))
                via = "crosswalk"
                if new_id is None:
                    problems.append(
                        f"{table}: {old_id} has no institution named {slug!r} in the {year} crawl"
                    )
                    continue
            else:
                univ_up = _univ_up_from_link(old_id)
                if univ_up:
                    new_id, via = arwu_source_id(univ_up, ""), "profile_url"
                else:
                    problems.append(f"{table}: {old_id} is not a recognised ARWU id form")
                    continue

            if new_id in existing:
                problems.append(
                    f"{table}: {old_id} -> {new_id}, but {new_id} already exists; "
                    "decide which row survives before re-keying"
                )
                continue
            if new_id in targets:
                problems.append(
                    f"{table}: {old_id} and {targets[new_id]} both resolve to {new_id}; "
                    "the table allows one row per id"
                )
                continue
            targets[new_id] = old_id
            plan.append(Rekey(table=table, old_id=old_id, new_id=new_id, via=via))

    return plan, problems, notes


def load_rows_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: expected a crawl output with a 'rows' list")
    return [row for row in rows if isinstance(row, dict)]


def crawl_rows(year: int) -> list[dict[str, Any]]:
    from arwu_crawler import crawl_arwu_rankings

    with tempfile.TemporaryDirectory(prefix="rekey_arwu_") as tmp:
        return load_rows_json(crawl_arwu_rankings(year=year, output_dir=Path(tmp)))


def load_ids(conn: Any) -> tuple[int, dict[str, set[str]]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = %s",
            (SOURCE_CODE,),
        )
        found = cur.fetchone()
        if found is None:
            raise SystemExit("No ARWU row in warehouse.ranking_source; nothing to re-key.")
        ranking_source_id = int(found[0])

        cur.execute(
            "SELECT source_entity_id FROM warehouse.mapping_review WHERE source_code = %s",
            (SOURCE_CODE,),
        )
        review_ids = {str(r[0]) for r in cur.fetchall()}
        cur.execute(
            "SELECT source_entity_id FROM warehouse.source_university_mapping "
            "WHERE ranking_source_id = %s",
            (ranking_source_id,),
        )
        mapping_ids = {str(r[0]) for r in cur.fetchall()}
    return ranking_source_id, {REVIEW_TABLE: review_ids, MAPPING_TABLE: mapping_ids}


def write(conn: Any, plan: list[Rekey], *, ranking_source_id: int) -> dict[str, int]:
    """Apply the plan in one transaction, and check the result before committing."""
    written = {table: 0 for table in TABLES}
    try:
        with conn.cursor() as cur:
            for step in plan:
                if step.table == REVIEW_TABLE:
                    cur.execute(
                        "UPDATE warehouse.mapping_review SET source_entity_id = %s "
                        "WHERE source_code = %s AND source_entity_id = %s",
                        (step.new_id, SOURCE_CODE, step.old_id),
                    )
                else:
                    cur.execute(
                        "UPDATE warehouse.source_university_mapping SET source_entity_id = %s "
                        "WHERE ranking_source_id = %s AND source_entity_id = %s",
                        (step.new_id, ranking_source_id, step.old_id),
                    )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"{step.table}: expected to update one row for {step.old_id}, "
                        f"updated {cur.rowcount}; the table changed under the plan"
                    )
                written[step.table] += 1

            cur.execute(
                "SELECT count(*) FROM warehouse.mapping_review "
                "WHERE source_code = %s AND source_entity_id ~ '^arwu:(19|20)[0-9]{2}:'",
                (SOURCE_CODE,),
            )
            left = int(cur.fetchone()[0])
            if left:
                raise RuntimeError(f"{left} ARWU decision(s) still year-keyed after re-keying")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return written


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-key ARWU entity ids to ShanghaiRanking's own slug.")
    source = parser.add_argument_group("crosswalk source (at least one)")
    source.add_argument(
        "--crawl-year",
        type=int,
        action="append",
        default=[],
        help="crawl this ARWU edition now and build the crosswalk from it (repeatable)",
    )
    source.add_argument(
        "--rows-json",
        type=Path,
        action="append",
        default=[],
        help="a crawl output written by the current crawler (repeatable)",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="actually write. Without it this previews and changes nothing.",
    )
    parser.add_argument(
        "--audit-out",
        type=Path,
        help="where to record every old -> new pair; required with --commit",
    )
    parser.add_argument("--pg-host", default=os.environ.get("CRAWLERNEST_PG_HOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("CRAWLERNEST_PG_PORT", "5432")))
    parser.add_argument("--pg-database", default=os.environ.get("CRAWLERNEST_PG_DATABASE", "clawer"))
    parser.add_argument("--pg-user", default=os.environ.get("CRAWLERNEST_PG_USER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("CRAWLERNEST_PG_PASSWORD", "test"))
    args = parser.parse_args(argv)
    if not args.crawl_year and not args.rows_json:
        parser.error("give --crawl-year or --rows-json: the new ids are looked up, never derived")
    if args.commit and args.audit_out is None:
        parser.error("--commit needs --audit-out: a re-key with no record of the old ids cannot be undone")
    return args


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        import psycopg2
    except ImportError:
        raise SystemExit("psycopg2 is required. Activate the venv first: source .venv/bin/activate") from None

    rows: list[dict[str, Any]] = []
    for path in args.rows_json:
        rows.extend(load_rows_json(path))
    for year in args.crawl_year:
        rows.extend(crawl_rows(year))
    crosswalk, problems = crosswalk_from_rows(rows)
    print(f"crosswalk: {len(crosswalk)} institution(s) across editions "
          f"{sorted({year for year, _ in crosswalk})}")

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    try:
        ranking_source_id, ids_by_table = load_ids(conn)
        plan, plan_problems, notes = plan_rekey(ids_by_table, crosswalk)
        problems.extend(plan_problems)

        for note in notes:
            print(f"  note: {note}")
        if problems:
            print(f"{len(problems)} problem(s); nothing written:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1

        for table in TABLES:
            steps = [s for s in plan if s.table == table]
            renamed = sum(1 for s in steps if s.new_id.split(":", 1)[1] != s.old_id.rsplit(":", 1)[-1])
            print(f"{table}: {len(steps)} id(s) to re-key "
                  f"({renamed} where the source slug differs from the old name slug)")
        for step in plan:
            if step.table == REVIEW_TABLE:
                print(f"  {step.old_id} -> {step.new_id}")

        if not plan:
            print("Nothing to re-key.")
            return 0
        if not args.commit:
            print()
            print("Preview only. Nothing was written. Re-run with --commit --audit-out PATH to apply.")
            return 0

        args.audit_out.write_text(
            json.dumps(
                {
                    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "source_code": SOURCE_CODE,
                    "crosswalk_editions": sorted({year for year, _ in crosswalk}),
                    "rekeys": [asdict(step) for step in plan],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        written = write(conn, plan, ranking_source_id=ranking_source_id)
        print()
        print(f"Re-keyed {written[REVIEW_TABLE]} decision(s) and {written[MAPPING_TABLE]} mapping row(s). "
              f"Old ids recorded in {args.audit_out}.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
