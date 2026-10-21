#!/usr/bin/env python3
"""Give eight source entities the university they are, on the 2026-10-12 decision.

Seven of them hold no rank at all. Each was matched by ``fuzzy_review`` to a different university
with a similar name, and the match was then rejected in ``warehouse.mapping_review`` -- five by the
deterministic-collision rule, two by a person ("Henan is not Hunan"). A rejection withdraws the wrong
credit and stops there: the entity resolves to nothing, so every rank its source published for it is
absent. The record each entity belongs on exists, created empty on 2026-09-20 under the entity's
own name (for the Federal University of São Paulo, the record QS and THE already use).

    ARWU federal-university-of-sao-paulo               was matched to UFSCar            10 editions missing
    ARWU henan-normal-university                       was matched to Hunan Normal       5
    ARWU jiangsu-university-of-science-and-technology  was matched to Nanjing UST        4
    THE  685267 (the same university)                  was matched to Nanjing UST        1
    ARWU nanjing-university-of-chinese-medicine        was matched to Beijing UCM        7
    ARWU wuhan-university-of-science-and-technology    was matched to Wuhan UT           5
    ARWU xian-university-of-technology                 was matched to Xi'an UST          7

The eighth does hold a rank, on the wrong university. QS renamed the University at Albany's page to
``/universities/university-albany-state-university-new-york`` in the crawl of 2026-10-08; the new id
was matched by ``fuzzy_review`` (0.856) to "University at Buffalo, the State University of New York",
so Albany's QS 2026 world rank (941) is shown on a Buffalo record, beside Buffalo's ARWU ranks.

A rejection says "not that university". Turning it into a remap to the right one keeps that
statement and adds the half it left out, so the two reviews a person wrote are amended, not
overruled: the decision becomes ``remapped``, and the note keeps what they wrote.

Phases, as in split_false_entity_merges.py -- each reports and writes nothing without ``--commit``,
and re-running an applied phase does nothing:

    1. ``prepare``  amend the seven reviews and record one for Albany; move Albany's one QS row and
                    its mapping to the Albany record. One transaction.
    2. ``replay``   replay the committed ARWU and THE files of the editions that list those entities;
                    the ingest applies the reviews and writes the rows.
    3. ``verify``   read-only: every entity on its university, every published rank present, and
                    the collision scan of split_false_entity_merges.py.

    ./.venv/bin/python crawlernest/scripts/restore_rejected_entities.py prepare --pg-password test
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

_HERE = Path(__file__).resolve()
for _p in (str(_HERE.parent), str(_HERE.parents[1]), str(_HERE.parents[2])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import split_false_entity_merges as base  # noqa: E402

DECIDED_BY = base.DECIDED_BY
DECIDED_ON = "2026-10-12"
PreconditionFailed = base.PreconditionFailed


@dataclass(frozen=True)
class Decision:
    source_code: str
    source_entity_id: str
    #: The name the source prints, as in the committed files.
    source_name: str
    #: The record the entity was wrongly matched to; the review or mapping must still name it.
    wrong_slug: str
    target_slug: str
    why: str
    #: True when a ``rejected`` review stands; False when the wrong match is still active.
    rejected: bool = True


DECISIONS: tuple[Decision, ...] = (
    Decision("ARWU", "arwu:federal-university-of-sao-paulo", "Federal University of São Paulo",
             "universidade-federal-de-são-carlos-ufscar", "universidade-federal-de-são-paulo",
             "UNIFESP, in São Paulo, is not UFSCar, in São Carlos. QS and THE already rank it on this record."),
    Decision("ARWU", "arwu:henan-normal-university", "Henan Normal University",
             "hunan-normal-university", "henan-normal-university",
             "Henan Normal University (Xinxiang) is not Hunan Normal University (Changsha); ARWU lists both."),
    Decision("ARWU", "arwu:jiangsu-university-of-science-and-technology", "Jiangsu University of Science and Technology",
             "nanjing-university-of-science-and-technology", "jiangsu-university-of-science-and-technology",
             "JUST (Zhenjiang) is not Nanjing University of Science and Technology; ARWU lists both."),
    Decision("THE", "685267", "Jiangsu University of Science and Technology",
             "nanjing-university-of-science-and-technology", "jiangsu-university-of-science-and-technology",
             "JUST (Zhenjiang) is not Nanjing University of Science and Technology; THE lists both."),
    Decision("ARWU", "arwu:nanjing-university-of-chinese-medicine", "Nanjing University of Chinese Medicine",
             "beijing-university-of-chinese-medicine", "nanjing-university-of-chinese-medicine",
             "Two universities in two cities; ARWU lists both."),
    Decision("ARWU", "arwu:wuhan-university-of-science-and-technology", "Wuhan University of Science and Technology",
             "wuhan-university-of-technology", "wuhan-university-of-science-and-technology",
             "WUST is not Wuhan University of Technology; ARWU lists both."),
    Decision("ARWU", "arwu:xian-university-of-technology", "Xi'an University of Technology",
             "xi-an-university-of-science-and-technology", "xi-an-university-of-technology",
             "XAUT is not Xi'an University of Science and Technology; ARWU lists both."),
    Decision("QS", "/universities/university-albany-state-university-new-york",
             "University at Albany, State University of New York",
             "university-at-buffalo-the-state-university-of-new-york", "university-at-albany-suny",
             "The id is the University at Albany's QS page under its new address; the record it was matched to is "
             "the University at Buffalo. The Albany record already holds QS's earlier id for the same page.",
             rejected=False),
)

#: The one QS row prepare moves, and the only one it will: Albany's 2026 world rank.
ALBANY_ROW = {"ranking_year": 2026, "ranking_type": "world", "rank_position": 941}


def _file(source_code: str, year: int) -> Path:
    return base.DATABASES_DIR / f"{source_code.lower()}_rankings_{year}.json"


def published(
    decisions: Sequence[Decision] = DECISIONS, years: Sequence[int] = range(2015, 2027)
) -> dict[tuple[str, str], dict[int, str]]:
    """What the committed files hold for each entity: ``{(source, entity id): {edition: printed rank}}``."""
    from pipeline.commands.canonical import load_json_payload

    wanted = {(d.source_code, d.source_entity_id) for d in decisions if d.source_code in ("ARWU", "THE")}
    found: dict[tuple[str, str], dict[int, str]] = {key: {} for key in wanted}
    for source_code in sorted({s for s, _ in wanted}):
        for year in years:
            path = _file(source_code, year)
            if not path.exists():
                continue
            for row in load_json_payload(path):
                key = (source_code, str(row.get("id")))
                if key in found:
                    found[key][int(year)] = str(row.get("rank"))
    return found


def _canonical(cur: Any, slug: str) -> tuple[int, str]:
    row = base._one(cur, "SELECT canonical_university_id, status FROM warehouse.canonical_university "
                         "WHERE canonical_slug = %s", (slug,))
    if row is None:
        raise PreconditionFailed(f"no canonical with slug {slug!r}")
    return int(row[0]), str(row[1])


def plan_and_apply(conn: Any, *, commit: bool, decisions: Sequence[Decision] = DECISIONS) -> dict[str, Any]:
    """Every step of ``prepare``, in one transaction; rolled back unless ``commit``."""
    actions: list[str] = []
    try:
        with conn.cursor() as cur:
            for d in decisions:
                wrong_id, _ = _canonical(cur, d.wrong_slug)
                target_id, target_status = _canonical(cur, d.target_slug)
                if target_status != "active":
                    raise PreconditionFailed(f"{d.target_slug} is {target_status}; an entity is not remapped onto it")
                label = f"{d.source_code} {d.source_entity_id}"
                mapping = base._one(
                    cur, "SELECT source_mapping_id, canonical_university_id, match_method, confidence_score, "
                         "ranking_source_id, is_active FROM warehouse.source_university_mapping "
                         "WHERE source_code = %s AND source_entity_id = %s", (d.source_code, d.source_entity_id))
                if mapping is None:
                    raise PreconditionFailed(f"{label} has no mapping row")
                mapping_id, mapped_to, method, confidence, ranking_source_id, _is_active = mapping
                review = base._one(
                    cur, "SELECT mapping_review_id, decision, reviewed_canonical_university_id, "
                         "decided_canonical_university_id FROM warehouse.mapping_review "
                         "WHERE source_code = %s AND source_entity_id = %s", (d.source_code, d.source_entity_id))
                if review is not None and review[1] == "remapped" and review[3] is not None and int(review[3]) == target_id:
                    actions.append(f"review {label}: already -> c{target_id}")
                elif d.rejected:
                    if review is None or review[1] != "rejected" or review[2] is None or int(review[2]) != wrong_id:
                        raise PreconditionFailed(
                            f"{label}: expected a rejected review of the match to c{wrong_id}, found {review!r}")
                    cur.execute(
                        "UPDATE warehouse.mapping_review SET decision = 'remapped', decided_canonical_university_id = %s, "
                        "note = concat_ws(' ', note, %s) WHERE mapping_review_id = %s",
                        (target_id,
                         f"[{DECIDED_ON}, {DECIDED_BY}: the rejection stands, and the entity is remapped to the "
                         f"university it is, c{target_id}. {d.why}]", review[0]))
                    actions.append(f"review {label}: rejected (as c{wrong_id}) -> remapped to c{target_id}")
                else:
                    if review is not None:
                        raise PreconditionFailed(f"{label} already has a {review[1]} review; a decision is not overwritten")
                    if mapped_to is None or int(mapped_to) not in (wrong_id, target_id):
                        raise PreconditionFailed(f"{label} is on c{mapped_to}, expected c{wrong_id}")
                    cur.execute(
                        "INSERT INTO warehouse.mapping_review (ranking_source_id, source_entity_id, reviewed_source_name, "
                        "reviewed_canonical_university_id, reviewed_match_method, reviewed_confidence_score, decision, "
                        "decided_canonical_university_id, decided_by, note, source_code) "
                        "VALUES (%s, %s, %s, %s, %s, %s, 'remapped', %s, %s, %s, %s)",
                        (ranking_source_id, d.source_entity_id, d.source_name, wrong_id, method, confidence, target_id,
                         DECIDED_BY, f"{DECIDED_ON}: {d.why}", d.source_code))
                    actions.append(f"review {label}: c{wrong_id} -> c{target_id}")

                if d.source_code != "QS":
                    continue
                # QS is not replayed (its prune would take rows that are in no snapshot), so its one row
                # is moved by id, after checking it is exactly the row this was decided about.
                cur.execute(
                    "SELECT ranking_record_id, canonical_university_id, ranking_year, ranking_type, rank_position "
                    "FROM warehouse.ranking_record WHERE source_mapping_id = %s", (mapping_id,))
                rows = cur.fetchall()
                expected = (ALBANY_ROW["ranking_year"], ALBANY_ROW["ranking_type"], ALBANY_ROW["rank_position"])
                if [tuple(r[2:]) for r in rows] != [expected]:
                    raise PreconditionFailed(
                        f"{label}: expected the single row {expected}, found {[tuple(r[2:]) for r in rows]}")
                row_id, row_canonical = int(rows[0][0]), int(rows[0][1])
                if row_canonical == target_id and mapped_to is not None and int(mapped_to) == target_id:
                    actions.append(f"row {label}: already on c{target_id}")
                    continue
                if row_canonical != wrong_id:
                    raise PreconditionFailed(f"{label}: its row is on c{row_canonical}, expected c{wrong_id}")
                clash = base._one(
                    cur, "SELECT count(*) FROM warehouse.ranking_record t JOIN warehouse.ranking_record r "
                         "USING (ranking_source_id, ranking_year, ranking_type, universe_type, universe_key) "
                         "WHERE r.ranking_record_id = %s AND t.canonical_university_id = %s", (row_id, target_id))
                if clash[0]:
                    raise PreconditionFailed(f"{label}: c{target_id} already holds a rank in that table")
                cur.execute("UPDATE warehouse.ranking_record SET canonical_university_id = %s, updated_at = now() "
                            "WHERE ranking_record_id = %s", (target_id, row_id))
                cur.execute(
                    "UPDATE warehouse.source_university_mapping SET canonical_university_id = %s, "
                    "match_method = 'human_remapped', confidence_score = 1.0 WHERE source_mapping_id = %s",
                    (target_id, mapping_id))
                actions.append(
                    f"row {label}: QS {expected[0]} {expected[1]} rank {expected[2]} moved c{wrong_id} -> c{target_id}")
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    return {"committed": commit, "actions": actions}


def replay(pg: dict[str, Any], *, commit: bool, decisions: Sequence[Decision] = DECISIONS) -> list[dict[str, Any]]:
    """Replay each committed edition that lists one of the entities; the ingest applies the reviews."""
    from pipeline.commands.canonical import ingest_rankings_payload, load_json_payload

    editions = sorted({(source, year) for (source, _eid), by_year in published(decisions).items() for year in by_year})
    results = []
    for source_code, year in editions:
        payload = load_json_payload(_file(source_code, year))
        if not commit:
            results.append({"source": source_code, "year": year, "rows": len(payload), "committed": False})
            continue
        summary = ingest_rankings_payload(
            source=source_code, payload=payload, ranking_year=year, ranking_type="world", source_version=None,
            pg_host=pg["host"], pg_port=pg["port"], pg_database=pg["database"], pg_user=pg["user"],
            pg_password=pg["password"],
        )
        results.append({
            "source": source_code, "year": year, "rows": len(payload), "committed": True,
            "matched": summary.matched_count, "unresolved": summary.unresolved_count,
            "rows_written": summary.rows_written, "aggregated_rows": summary.aggregated_row_count,
        })
    return results


def verify(conn: Any, decisions: Sequence[Decision] = DECISIONS) -> dict[str, Any]:
    """Read-only. ``problems`` is empty when every entity is on its university with every published rank."""
    problems: list[str] = []
    restored: dict[str, int] = {}
    files = published(decisions)
    with conn.cursor() as cur:
        for d in decisions:
            label = f"{d.source_code} {d.source_entity_id}"
            target_id, _ = _canonical(cur, d.target_slug)
            mapping = base._one(
                cur, "SELECT source_mapping_id, canonical_university_id, is_active FROM warehouse.source_university_mapping "
                     "WHERE source_code = %s AND source_entity_id = %s", (d.source_code, d.source_entity_id))
            if mapping is None or mapping[1] is None or int(mapping[1]) != target_id or not mapping[2]:
                problems.append(f"{label}: not actively mapped to c{target_id} ({mapping!r})")
                continue
            cur.execute("SELECT ranking_year, canonical_university_id FROM warehouse.ranking_record "
                        "WHERE source_mapping_id = %s AND ranking_type = 'world'", (mapping[0],))
            held = dict(cur.fetchall())
            elsewhere = sorted(year for year, canonical in held.items() if int(canonical) != target_id)
            if elsewhere:
                problems.append(f"{label}: editions {elsewhere} are on another university")
            if d.source_code == "QS":
                wanted = {ALBANY_ROW["ranking_year"]}
            else:
                wanted = set(files.get((d.source_code, d.source_entity_id), {}))
            if set(held) != wanted:
                problems.append(f"{label}: holds editions {sorted(held)}, its source published {sorted(wanted)}")
            restored[label] = len(held)
        collisions = base.collision_scan(conn)
    problems.extend(f"collision: {c}" for c in collisions)
    conn.rollback()
    return {"problems": problems, "rows_per_entity": restored, "rows": sum(restored.values())}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", choices=["prepare", "replay", "verify"])
    parser.add_argument("--commit", action="store_true", help="write; without it every phase only reports")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    args = parser.parse_args(argv)
    pg = {"host": args.pg_host, "port": args.pg_port, "database": args.pg_database, "user": args.pg_user,
          "password": args.pg_password}

    if args.phase == "replay":
        print(json.dumps(replay(pg, commit=args.commit), ensure_ascii=False, indent=1))
        return 0

    import psycopg2

    conn = psycopg2.connect(host=args.pg_host, port=args.pg_port, dbname=args.pg_database, user=args.pg_user,
                            password=args.pg_password)
    try:
        result = plan_and_apply(conn, commit=args.commit) if args.phase == "prepare" else verify(conn)
    except PreconditionFailed as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 1 if result.get("problems") else 0


if __name__ == "__main__":
    raise SystemExit(main())