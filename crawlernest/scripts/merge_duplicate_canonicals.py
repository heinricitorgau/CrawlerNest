#!/usr/bin/env python3
"""Merge canonical universities that are one institution carried twice.

The decisions are a committed file, ``crawlernest-kb/entity_merges/duplicate_canonicals_<date>.json``;
this applies one. Each entry names a *loser* and a *survivor* by slug and says on what evidence they
are the same university. Nothing here decides that: a pair is in the file because both records were
matched to one Wikipedia article and no source lists them as two universities, or because a mapping
review had already moved the loser's only entity to the survivor, or because a person read the names.

How the 2026-10-12 file came about. THE and ARWU print "Ankara University"; the record QS seeded is
"Ankara Üniversitesi" in "Turkey", and THE says "Türkiye". The resolver knew neither that the two
names nor that the two countries are the same, so the THE/ARWU backfill of 2026-09-20 opened a second
record. One university then appeared twice in an edition, each row with fewer sources than it has,
and its history was split between two pages.

What a merge does, following the 2026-09-14 one (``test_merged_canonical_pg.py`` holds the contract):

  * the loser's ranking rows, subject rows, source mappings and aliases move to the survivor;
  * the loser's display name becomes an alias of the survivor, unless that name could also be read as
    another university (``entity_resolution.alias_safety``) or the decision says ``"add_alias": false``;
  * a mapping review that decided an entity onto the loser is re-pointed at the survivor, with a note --
    left alone, the next ingest would apply it and move the entity back onto a merged record;
  * the loser stays, ``status = 'merged'`` with ``metadata.merged_into``, because historical aggregation
    and ML runs reference it. The resolver loads only active records, so it stops attracting names.

It refuses a pair whose two records hold a rank from one source in one table: that is a source saying
they are two universities. The one exception is ``"overlap": "identical_rank"`` -- the same rank on
both, one of the rows a legacy row with no source mapping -- where the unmapped copy is dropped.

Phases. Every phase prints what it would do and writes nothing without ``--commit``:

    merge      move the rows and mark the losers, in one transaction
    aggregate  recompute analytics.aggregated_rankings for every edition and table a merge touched
    preview    rewrite the derived warehouse.ranking_decision_preview rows of the survivors
    verify     read-only: every decision applied, nothing left on a loser, no survivor listed twice

    ./.venv/bin/python crawlernest/scripts/merge_duplicate_canonicals.py merge --pg-password test
    ./.venv/bin/python crawlernest/scripts/merge_duplicate_canonicals.py merge --pg-password test --commit

Afterwards the committed exports are stale and ``./scripts/check_warehouse_drift.sh`` says so:
re-run ``export_cross_edition_ranks.py --commit`` and ``export_qs_the_pairing.py --commit``, and
``wikipedia_profile_loader.py match`` then ``ingest``. Rehearse on a copy of the database first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

_HERE = Path(__file__).resolve()
_MODULE_ROOT = _HERE.parents[1]  # crawlernest/
_REPO_ROOT = _HERE.parents[2]
for _path in (
    _REPO_ROOT,
    _MODULE_ROOT,
    _MODULE_ROOT / "packages",
    _MODULE_ROOT / "crawlernest-core",
    _MODULE_ROOT / "crawlernest-jobs",
    _MODULE_ROOT / "crawlernest-analytics",
):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from entity_resolution.alias_safety import alias_collision, resolver_keys  # noqa: E402

DECISIONS_DIR = _MODULE_ROOT / "crawlernest-kb" / "entity_merges"
DEFAULT_DECISIONS = DECISIONS_DIR / "duplicate_canonicals_2026-10-12.json"

OVERLAP_NONE = "none"
OVERLAP_IDENTICAL_RANK = "identical_rank"

_RANKING_KEY = "ranking_source_id, ranking_year, ranking_type, universe_type, universe_key"


class PreconditionFailed(RuntimeError):
    """The warehouse is not in the state a decision was made against. Nothing was written."""


@dataclass(frozen=True)
class Merge:
    loser_slug: str
    survivor_slug: str
    evidence: str
    why: str
    overlap: str = OVERLAP_NONE
    add_alias: bool = True


@dataclass(frozen=True)
class Decisions:
    decided_on: str
    decided_by: str
    merged_by: str
    merges: tuple[Merge, ...]


def load_decisions(path: Path) -> Decisions:
    """The decision file, refused whole if it could not be applied as written."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    merges = tuple(
        Merge(
            loser_slug=row["loser_slug"], survivor_slug=row["survivor_slug"], evidence=row["evidence"],
            why=row["why"], overlap=row.get("overlap", OVERLAP_NONE), add_alias=bool(row.get("add_alias", True)),
        )
        for row in raw["merges"]
    )
    losers = [m.loser_slug for m in merges]
    survivors = {m.survivor_slug for m in merges}
    if len(losers) != len(set(losers)):
        raise ValueError("a record is merged twice")
    if set(losers) & survivors:
        # A chain would make the result depend on the order the file is read in.
        raise ValueError(f"a record is both merged away and merged into: {sorted(set(losers) & survivors)}")
    for merge in merges:
        if merge.overlap not in (OVERLAP_NONE, OVERLAP_IDENTICAL_RANK):
            raise ValueError(f"{merge.loser_slug}: unknown overlap rule {merge.overlap!r}")
        if not merge.evidence.strip() or not merge.why.strip():
            raise ValueError(f"{merge.loser_slug}: a merge needs its evidence and its reason")
    return Decisions(raw["decided_on"], raw["decided_by"], raw["merged_by"], merges)


def normalize_alias(alias_text: str) -> str:
    """The form ``university_alias.alias_normalized`` holds (as in seed_alias_file.py)."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(alias_text or "").strip().lower()).split())


def _one(cur: Any, sql: str, params: Sequence[Any] = ()) -> Optional[tuple]:
    cur.execute(sql, params)
    return cur.fetchone()


def _load_other_names(cur: Any) -> dict[int, set[str]]:
    cur.execute(
        "SELECT cu.canonical_university_id, cu.display_name, "
        "COALESCE(ARRAY_AGG(ua.alias_text) FILTER (WHERE ua.alias_text IS NOT NULL), ARRAY[]::TEXT[]) "
        "FROM warehouse.canonical_university cu "
        "LEFT JOIN warehouse.university_alias ua ON ua.canonical_university_id = cu.canonical_university_id "
        "WHERE cu.status = 'active' GROUP BY 1, 2"
    )
    out: dict[int, set[str]] = {}
    for canonical_id, display_name, aliases in cur.fetchall():
        keys = resolver_keys(display_name)
        for alias in aliases or []:
            keys |= resolver_keys(alias)
        out[int(canonical_id)] = keys
    return out


def merge_all(conn: Any, decisions: Decisions, *, commit: bool) -> dict[str, Any]:
    """Every merge in the file, in one transaction; rolled back unless ``commit``."""
    actions: list[str] = []
    totals = {"merged": 0, "already": 0, "ranking_rows": 0, "subject_rows": 0, "mappings": 0, "aliases_added": 0,
              "aliases_withheld": 0, "reviews_repointed": 0, "legacy_duplicates_dropped": 0}
    touched: set[tuple[str, int]] = set()
    try:
        with conn.cursor() as cur:
            for merge in decisions.merges:
                loser = _one(cur, "SELECT canonical_university_id, display_name, status, metadata->>'merged_into' "
                                  "FROM warehouse.canonical_university WHERE canonical_slug = %s", (merge.loser_slug,))
                survivor = _one(cur, "SELECT canonical_university_id, display_name, status "
                                     "FROM warehouse.canonical_university WHERE canonical_slug = %s", (merge.survivor_slug,))
                if loser is None or survivor is None:
                    raise PreconditionFailed(f"{merge.loser_slug} -> {merge.survivor_slug}: a record does not exist")
                loser_id, loser_name, loser_status, merged_into = loser
                survivor_id, survivor_name, survivor_status = survivor
                if survivor_status != "active":
                    raise PreconditionFailed(f"{merge.survivor_slug} is {survivor_status}, not active")
                if loser_status == "merged":
                    if merged_into and int(merged_into) == survivor_id:
                        totals["already"] += 1
                        continue
                    raise PreconditionFailed(f"{merge.loser_slug} is already merged into canonical {merged_into}")
                if loser_status != "active":
                    raise PreconditionFailed(f"{merge.loser_slug} is {loser_status}, not active")

                lineage = _one(cur, "SELECT count(*) FROM warehouse.institution_lineage "
                                    "WHERE %s IN (predecessor_canonical_id, successor_canonical_id)", (loser_id,))
                if lineage[0]:
                    raise PreconditionFailed(
                        f"{merge.loser_slug} is named in warehouse.institution_lineage; a record that marks an "
                        "institutional change is not a spelling of another")

                # --- a source listing both records in one table says they are two universities
                cur.execute(
                    f"SELECT x.ranking_record_id, x.rank_position, x.source_mapping_id, "
                    f"       y.ranking_record_id, y.rank_position, y.source_mapping_id "
                    f"FROM warehouse.ranking_record x JOIN warehouse.ranking_record y USING ({_RANKING_KEY}) "
                    f"WHERE x.canonical_university_id = %s AND y.canonical_university_id = %s",
                    (survivor_id, loser_id),
                )
                overlaps = cur.fetchall()
                if overlaps and merge.overlap != OVERLAP_IDENTICAL_RANK:
                    raise PreconditionFailed(
                        f"{merge.loser_slug} -> {merge.survivor_slug}: {len(overlaps)} table(s) rank both records")
                for s_row, s_rank, s_mapping, l_row, l_rank, l_mapping in overlaps:
                    if s_rank != l_rank:
                        raise PreconditionFailed(
                            f"{merge.loser_slug} -> {merge.survivor_slug}: one table gives them ranks {s_rank} and {l_rank}")
                    if (s_mapping is None) == (l_mapping is None):
                        raise PreconditionFailed(
                            f"{merge.loser_slug} -> {merge.survivor_slug}: cannot tell which copy of a shared row is the legacy one")
                    cur.execute("DELETE FROM warehouse.ranking_record WHERE ranking_record_id = %s",
                                (s_row if s_mapping is None else l_row,))
                    totals["legacy_duplicates_dropped"] += 1
                subject_overlap = _one(
                    cur,
                    "SELECT count(*) FROM warehouse.subject_ranking_record x JOIN warehouse.subject_ranking_record y "
                    "USING (ranking_source_id, subject_id, ranking_year) "
                    "WHERE x.canonical_university_id = %s AND y.canonical_university_id = %s", (survivor_id, loser_id))
                if subject_overlap[0]:
                    raise PreconditionFailed(f"{merge.loser_slug} -> {merge.survivor_slug}: a subject table ranks both")

                # --- rows
                cur.execute("UPDATE warehouse.ranking_record SET canonical_university_id = %s, updated_at = now() "
                            "WHERE canonical_university_id = %s RETURNING ranking_type, ranking_year", (survivor_id, loser_id))
                moved = cur.fetchall()
                touched.update((str(ranking_type), int(year)) for ranking_type, year in moved)
                # An identical-rank duplicate that was dropped still changes its table's aggregate.
                cur.execute("SELECT DISTINCT ranking_type, ranking_year FROM warehouse.ranking_record "
                            "WHERE canonical_university_id = %s", (survivor_id,))
                if overlaps:
                    touched.update((str(ranking_type), int(year)) for ranking_type, year in cur.fetchall())
                cur.execute("UPDATE warehouse.subject_ranking_record SET canonical_university_id = %s, updated_at = now() "
                            "WHERE canonical_university_id = %s", (survivor_id, loser_id))
                subject_rows = cur.rowcount
                cur.execute("UPDATE warehouse.source_university_mapping SET canonical_university_id = %s "
                            "WHERE canonical_university_id = %s", (survivor_id, loser_id))
                mappings = cur.rowcount
                cur.execute("UPDATE warehouse.source_mapping SET canonical_university_id = %s "
                            "WHERE canonical_university_id = %s", (survivor_id, loser_id))
                mappings += cur.rowcount
                for table in ("warehouse.admission_record", "warehouse.canonical_university_link"):
                    cur.execute(f"UPDATE {table} SET canonical_university_id = %s WHERE canonical_university_id = %s",
                                (survivor_id, loser_id))
                cur.execute(
                    "DELETE FROM warehouse.saved_university s WHERE canonical_university_id = %s AND EXISTS ("
                    "  SELECT 1 FROM warehouse.saved_university k WHERE k.user_id = s.user_id AND k.canonical_university_id = %s)",
                    (loser_id, survivor_id))
                cur.execute("UPDATE warehouse.saved_university SET canonical_university_id = %s "
                            "WHERE canonical_university_id = %s", (survivor_id, loser_id))
                # The desk's target list (db/auth/V003__create_desk_schema.sql) has no foreign key to
                # canonical_university, so nothing else would notice a target left on the loser. Same
                # shape as saved_university: drop the loser's row where the user already has the survivor.
                cur.execute("SELECT to_regclass('desk.target_entity') IS NOT NULL")
                if cur.fetchone()[0]:
                    cur.execute(
                        "DELETE FROM desk.target_entity t WHERE canonical_university_id = %s AND EXISTS ("
                        "  SELECT 1 FROM desk.target_entity k WHERE k.user_id = t.user_id"
                        "  AND k.canonical_university_id = %s AND k.programme_key = t.programme_key)",
                        (loser_id, survivor_id))
                    cur.execute("UPDATE desk.target_entity SET canonical_university_id = %s, updated_at = now() "
                                "WHERE canonical_university_id = %s", (survivor_id, loser_id))
                cur.execute("SELECT to_regclass('warehouse.university_wikipedia_article') IS NOT NULL")
                if cur.fetchone()[0]:
                    cur.execute("DELETE FROM warehouse.university_wikipedia_article WHERE canonical_university_id = %s",
                                (loser_id,))

                # --- names. Aliases the survivor already has stay behind on the loser, which nothing loads.
                cur.execute(
                    "UPDATE warehouse.university_alias a SET canonical_university_id = %s WHERE canonical_university_id = %s "
                    "AND NOT EXISTS (SELECT 1 FROM warehouse.university_alias k WHERE k.canonical_university_id = %s "
                    "  AND k.alias_normalized = a.alias_normalized "
                    "  AND COALESCE(k.language_code, '') = COALESCE(a.language_code, '') "
                    "  AND COALESCE(k.source_name, '') = COALESCE(a.source_name, ''))",
                    (survivor_id, loser_id, survivor_id))
                alias_note = ""
                if not merge.add_alias:
                    totals["aliases_withheld"] += 1
                    alias_note = "; name not added as an alias (decision)"
                else:
                    collision = alias_collision(loser_name, survivor_id,
                                                {k: v for k, v in _load_other_names(cur).items() if k != loser_id})
                    if collision:
                        totals["aliases_withheld"] += 1
                        alias_note = f"; name not added as an alias ({collision})"
                    else:
                        cur.execute(
                            "INSERT INTO warehouse.university_alias (canonical_university_id, alias_text, alias_normalized, "
                            "source_name, metadata) VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT DO NOTHING",
                            (survivor_id, loser_name, normalize_alias(loser_name), decisions.merged_by,
                             json.dumps({"merged_from": loser_id, "evidence": merge.evidence})))
                        totals["aliases_added"] += cur.rowcount

                # --- standing decisions that name the loser
                cur.execute(
                    "UPDATE warehouse.mapping_review SET decided_canonical_university_id = %s, "
                    "note = concat_ws(' ', note, %s) WHERE decided_canonical_university_id = %s",
                    (survivor_id,
                     f"[{decisions.decided_on}: canonical {loser_id} was merged into {survivor_id}; decision re-pointed.]",
                     loser_id))
                reviews = cur.rowcount

                cur.execute(
                    "UPDATE warehouse.canonical_university SET status = 'merged', updated_at = now(), "
                    "metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb WHERE canonical_university_id = %s",
                    (json.dumps({"merged_into": survivor_id, "merged_by": decisions.merged_by,
                                 "merged_at": decisions.decided_on, "evidence": merge.evidence, "reason": merge.why}),
                     loser_id))

                totals["merged"] += 1
                totals["ranking_rows"] += len(moved)
                totals["subject_rows"] += subject_rows
                totals["mappings"] += mappings
                totals["reviews_repointed"] += reviews
                actions.append(
                    f"c{loser_id} {loser_name!r} -> c{survivor_id} {survivor_name!r}: {len(moved)} ranking rows, "
                    f"{mappings} mappings, {reviews} reviews{alias_note}")
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    return {"committed": commit, "totals": totals, "actions": actions,
            "touched": sorted(touched)}


def touched_tables(conn: Any, decisions: Decisions) -> list[tuple[str, int]]:
    """Every (ranking_type, year) holding a row of a survivor: what ``aggregate`` must recompute.

    Read from the survivors rather than remembered from the merge, so ``aggregate`` can be re-run
    on its own and a rehearsal and the real run recompute the same set.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT rr.ranking_type, rr.ranking_year FROM warehouse.ranking_record rr "
            "JOIN warehouse.canonical_university cu USING (canonical_university_id) "
            "WHERE cu.canonical_slug = ANY(%s) ORDER BY 1, 2",
            ([m.survivor_slug for m in decisions.merges],))
        return [(str(ranking_type), int(year)) for ranking_type, year in cur.fetchall()]


def refresh_aggregations(conn: Any, decisions: Decisions, *, commit: bool) -> dict[str, Any]:
    """Recompute the aggregated rankings of every table a survivor is in, from ``warehouse.ranking_record``."""
    tables = touched_tables(conn, decisions)
    by_type: dict[str, list[int]] = {}
    for ranking_type, year in tables:
        by_type.setdefault(ranking_type, []).append(year)
    if not commit:
        conn.rollback()
        return {"committed": False, "would_recompute": {k: v for k, v in sorted(by_type.items())}}
    from pipeline.utils.postgres import build_multi_source_pipeline

    pipeline = build_multi_source_pipeline(conn)
    written = {}
    for ranking_type, years in sorted(by_type.items()):
        written[ranking_type] = pipeline._refresh_aggregations(
            years, ranking_type=ranking_type, run_label_prefix=decisions.merged_by)
    conn.commit()
    return {"committed": True, "aggregated_rows": written}


def refresh_preview(conn: Any, decisions: Decisions, *, commit: bool) -> dict[str, Any]:
    """Rewrite the survivors' rows of ``warehouse.ranking_decision_preview``, and drop the losers'.

    The table is keyed by normalised name and written with ``ON CONFLICT DO NOTHING``, so its own
    command would leave a survivor's row at the source count it had before the merge. Only rows the
    table already holds are rewritten (see ENTITY_SPLIT_2026-10-03.md for why nothing is added).
    """
    from crawlernest_ranking_crawler.decision_writer import (
        build_decision_row, load_aggregated_rows_from_warehouse, write_decision_rows,
    )
    from crawlernest_ranking_crawler.explain_layer import build_explain

    with conn.cursor() as cur:
        cur.execute("SELECT canonical_slug, display_name_normalized FROM warehouse.canonical_university "
                    "WHERE canonical_slug = ANY(%s)",
                    ([m.survivor_slug for m in decisions.merges] + [m.loser_slug for m in decisions.merges],))
        normalized = dict(cur.fetchall())
        cur.execute("SELECT DISTINCT ranking_year FROM warehouse.ranking_decision_preview ORDER BY 1")
        years = [int(row[0]) for row in cur.fetchall()]
    survivor_of = {normalized[m.loser_slug]: normalized[m.survivor_slug] for m in decisions.merges
                   if m.loser_slug in normalized and m.survivor_slug in normalized}
    survivor_names = sorted(set(survivor_of.values()))
    loser_names = sorted(set(survivor_of) - set(survivor_names))
    # Which (name, edition) rows the table holds is not this script's to decide: a survivor gets a row
    # only where it, or the record merged into it, already had one.
    with conn.cursor() as cur:
        cur.execute("SELECT normalized_university_name, ranking_year FROM warehouse.ranking_decision_preview "
                    "WHERE normalized_university_name = ANY(%s)", (survivor_names + loser_names,))
        held = {(survivor_of.get(name, name), int(year)) for name, year in cur.fetchall()}
    rows = [r for r in load_aggregated_rows_from_warehouse(conn)
            if (r.normalized_university_name, int(r.ranking_year)) in held]
    decision_rows = [build_decision_row(r, build_explain(r)) for r in rows]
    summary = {"years": years, "survivor_rows": len(decision_rows), "loser_names": len(loser_names)}
    if not commit:
        conn.rollback()
        return {"committed": False, **summary}
    with conn.cursor() as cur:
        cur.execute("DELETE FROM warehouse.ranking_decision_preview "
                    "WHERE normalized_university_name = ANY(%s) AND ranking_year = ANY(%s)",
                    (survivor_names + loser_names, years))
        deleted = cur.rowcount
    write_decision_rows(decision_rows, conn)  # commits, together with the delete above
    return {"committed": True, **summary, "deleted": deleted, "inserted": len(decision_rows)}


def verify(conn: Any, decisions: Decisions) -> dict[str, Any]:
    """Read-only. ``problems`` is empty when every decision holds and nothing points at a merged record."""
    problems: list[str] = []
    with conn.cursor() as cur:
        for merge in decisions.merges:
            row = _one(cur, "SELECT l.canonical_university_id, l.status, l.metadata->>'merged_into', s.canonical_university_id, s.status "
                            "FROM warehouse.canonical_university l, warehouse.canonical_university s "
                            "WHERE l.canonical_slug = %s AND s.canonical_slug = %s", (merge.loser_slug, merge.survivor_slug))
            if row is None:
                problems.append(f"{merge.loser_slug} -> {merge.survivor_slug}: a record is missing")
                continue
            loser_id, loser_status, merged_into, survivor_id, survivor_status = row
            if loser_status != "merged" or not merged_into or int(merged_into) != survivor_id:
                problems.append(f"{merge.loser_slug}: not merged into {merge.survivor_slug}")
            if survivor_status != "active":
                problems.append(f"{merge.survivor_slug}: is {survivor_status}")
        for table, column in (
            ("warehouse.ranking_record", "canonical_university_id"),
            ("warehouse.subject_ranking_record", "canonical_university_id"),
            ("warehouse.source_university_mapping", "canonical_university_id"),
            ("warehouse.source_mapping", "canonical_university_id"),
            ("warehouse.mapping_review", "decided_canonical_university_id"),
            ("warehouse.admission_record", "canonical_university_id"),
            ("warehouse.saved_university", "canonical_university_id"),
            ("warehouse.canonical_university_link", "canonical_university_id"),
            ("analytics.v_aggregated_rankings_latest", "canonical_university_id"),
            ("desk.target_entity", "canonical_university_id"),
        ):
            if _one(cur, "SELECT to_regclass(%s) IS NULL", (table,))[0]:
                continue  # the desk schema exists only where the API has started
            count = _one(cur, f"SELECT count(*) FROM {table} t JOIN warehouse.canonical_university cu "
                              f"ON cu.canonical_university_id = t.{column} "
                              f"WHERE cu.status = 'merged' AND cu.metadata->>'merged_by' = %s", (decisions.merged_by,))[0]
            if count:
                problems.append(f"{table}.{column}: {count} row(s) still on a record merged by {decisions.merged_by}")
        survivors = [m.survivor_slug for m in decisions.merges]
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE (SELECT count(*) FROM jsonb_each(v.source_ranks_json) e "
            "                                         WHERE e.value <> 'null'::jsonb) >= 2) "
            "FROM analytics.v_aggregated_rankings_latest v JOIN warehouse.canonical_university cu USING (canonical_university_id) "
            "WHERE cu.canonical_slug = ANY(%s) AND v.ranking_year = (SELECT max(ranking_year) FROM analytics.v_aggregated_rankings_latest) "
            "AND v.universe_type = 'global' AND v.universe_key = 'global'", (survivors,))
        in_latest, multi_source = cur.fetchone()
    conn.rollback()
    return {"problems": problems, "decisions": len(decisions.merges),
            "survivors_in_latest_global_edition": in_latest, "of_which_two_or_more_sources": multi_source}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", choices=["merge", "aggregate", "preview", "verify"])
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--commit", action="store_true", help="write; without it every phase only reports")
    parser.add_argument("--verbose", action="store_true", help="merge: list every merge")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)

    import psycopg2

    decisions = load_decisions(args.decisions)
    conn = psycopg2.connect(host=args.pg_host, port=args.pg_port, dbname=args.pg_database, user=args.pg_user,
                            password=args.pg_password)
    try:
        if args.phase == "merge":
            result = merge_all(conn, decisions, commit=args.commit)
            if not args.verbose:
                result["actions"] = [a for a in result["actions"] if "not added as an alias" in a]
        elif args.phase == "aggregate":
            result = refresh_aggregations(conn, decisions, commit=args.commit)
        elif args.phase == "preview":
            result = refresh_preview(conn, decisions, commit=args.commit)
        else:
            result = verify(conn, decisions)
    except PreconditionFailed as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 1 if result.get("problems") else 0


if __name__ == "__main__":
    raise SystemExit(main())
