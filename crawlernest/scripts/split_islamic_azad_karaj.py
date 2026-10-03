#!/usr/bin/env python3
"""Take THE's "Islamic Azad University Karaj" off the canonical it was fuzzily matched to.

THE 587685, "Islamic Azad University Karaj" (Iran; THE 2017, 801+), is mapped to canonical 364060,
"Islamic Azad University.", by ``fuzzy_review`` at 0.851. No person reviewed it. What is known:

  * THE's entity is one branch. THE gives it a page of its own, and Wikipedia describes the Karaj
    branch (established 1984) as one of the university's branches.
  * Canonical 364060 is QS's ``/universities/islamic-azad-university``: a name with no branch or city
    ("Islamic Azad University.", location blank, QS 2026 1201-1400). QS's own page could not be read
    (HTTP 403), so what that entry covers is not known.
  * The warehouse already keeps every other Islamic Azad branch it holds on a canonical of its own:
    Isfahan (Khorasgan), Najafabad (THE 703295 is on its own canonical, matched by name) and Science
    and Research. Karaj is the one branch whose only link to a canonical is a name similarity.

Nothing shows that a branch and an unspecified entry are one institution; the warehouse's own
convention says a branch is its own. So Karaj gets a canonical of its own, the way Najafabad has.
Nothing is lost: THE 2017 holds it alone on either canonical, so no edition has two universities
fighting for one rank. What changes is which university a THE 2017 rank of 801 is shown under.

A decision in ``warehouse.mapping_review`` changes nothing by itself; the next ingest applies it. So,
as in split_false_entity_merges.py:

    1. ``prepare``      create the Karaj canonical, record a ``remapped`` review. One transaction.
    2. ``reingest-the`` replay the committed THE 2017 file; the ingest applies the review.
    3. ``verify``       read-only.

Every phase reports and writes nothing without ``--commit``; re-running an applied phase does nothing.

    ./.venv/bin/python crawlernest/scripts/split_islamic_azad_karaj.py prepare --pg-password test
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

_HERE = Path(__file__).resolve()
for _p in (str(_HERE.parent), str(_HERE.parents[1]), str(_HERE.parents[2])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import split_false_entity_merges as base  # noqa: E402

DECIDED_BY = base.DECIDED_BY
DECIDED_ON = "2026-10-04"


@dataclass(frozen=True)
class Decision:
    source_code: str
    source_entity_id: str
    source_name: str
    #: The canonical the entity is on now, and must be for the decision to apply.
    expect_canonical: int
    expect_slug: str
    new_slug: str
    new_display_name: str
    #: Existing canonical whose country the new one shares.
    country_from: int
    ranking_year: int
    why: str


DECISION = Decision(
    source_code="THE",
    source_entity_id="587685",
    source_name="Islamic Azad University Karaj",
    expect_canonical=364060,
    expect_slug="islamic-azad-university",
    new_slug="islamic-azad-university-karaj-branch",
    new_display_name="Islamic Azad University, Karaj Branch",
    country_from=364060,
    ranking_year=2017,
    why=("THE's Karaj entry is one branch of Islamic Azad University; canonical 364060 is QS's unspecified "
         "'Islamic Azad University.'. The match was fuzzy_review 0.851 and was never reviewed, and the "
         "warehouse keeps every other IAU branch on its own canonical"),
)


def plan_and_apply(conn: Any, *, commit: bool, decision: Decision = DECISION) -> dict[str, Any]:
    actions: list[str] = []
    d = decision
    with conn.cursor() as cur:
        mapping = base._one(
            cur, "SELECT canonical_university_id, match_method, confidence_score, ranking_source_id "
                 "FROM warehouse.source_university_mapping WHERE source_code = %s AND source_entity_id = %s AND is_active",
            (d.source_code, d.source_entity_id))
        if mapping is None:
            raise base.PreconditionFailed(f"{d.source_code} {d.source_entity_id} has no active mapping")
        current = int(mapping[0]) if mapping[0] is not None else None

        existing = base._one(cur, "SELECT canonical_university_id, display_name FROM warehouse.canonical_university "
                                  "WHERE canonical_slug = %s", (d.new_slug,))
        if existing is not None:
            if existing[1] != d.new_display_name:
                raise base.PreconditionFailed(f"slug {d.new_slug!r} is taken by {existing[1]!r}")
            target = int(existing[0])
            actions.append(f"canonical {d.new_display_name!r}: already c{target}")
        else:
            origin = base._one(cur, "SELECT canonical_slug, country_id FROM warehouse.canonical_university "
                                    "WHERE canonical_university_id = %s", (d.expect_canonical,))
            if origin is None or origin[0] != d.expect_slug:
                raise base.PreconditionFailed(
                    f"canonical {d.expect_canonical} is {origin!r}, not the {d.expect_slug!r} this was decided against")
            if current != d.expect_canonical:
                raise base.PreconditionFailed(
                    f"{d.source_code} {d.source_entity_id} is on c{current}, expected c{d.expect_canonical}")
            country = base._one(cur, "SELECT country_id FROM warehouse.canonical_university WHERE canonical_university_id = %s",
                                (d.country_from,))
            cur.execute(
                "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized, "
                "country_id, status, metadata) VALUES (%s, %s, %s, %s, 'active', %s::jsonb) "
                "RETURNING canonical_university_id",
                (d.new_slug, d.new_display_name, base._normalize(d.new_display_name), country[0],
                 json.dumps({"created_by": "split_islamic_azad_karaj", "decided_on": DECIDED_ON, "why": d.why})))
            target = int(cur.fetchone()[0])
            actions.append(f"canonical {d.new_display_name!r}: created c{target} ({d.new_slug})")

        if current not in (d.expect_canonical, target):
            raise base.PreconditionFailed(
                f"{d.source_code} {d.source_entity_id} is on c{current}, expected c{d.expect_canonical}")
        review = base._one(cur, "SELECT decision, decided_canonical_university_id FROM warehouse.mapping_review "
                                "WHERE source_code = %s AND source_entity_id = %s", (d.source_code, d.source_entity_id))
        if review is not None:
            if review[0] == "remapped" and int(review[1]) == target:
                actions.append(f"review {d.source_code} {d.source_entity_id}: already -> c{target}")
            else:
                raise base.PreconditionFailed(
                    f"{d.source_code} {d.source_entity_id} already has a {review[0]} review; a person's decision is not overwritten")
        else:
            cur.execute(
                "INSERT INTO warehouse.mapping_review (ranking_source_id, source_entity_id, reviewed_source_name, "
                "reviewed_canonical_university_id, reviewed_match_method, reviewed_confidence_score, decision, "
                "decided_canonical_university_id, decided_by, note, source_code) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'remapped', %s, %s, %s, %s)",
                (mapping[3], d.source_entity_id, d.source_name, current, mapping[1], mapping[2], target,
                 DECIDED_BY, f"{DECIDED_ON}: {d.why}", d.source_code))
            actions.append(f"review {d.source_code} {d.source_entity_id}: c{current} -> c{target}")
    if commit:
        conn.commit()
    else:
        conn.rollback()
    return {"committed": commit, "actions": actions, "target": target}


def verify(conn: Any, decision: Decision = DECISION) -> dict[str, Any]:
    """Read-only."""
    d = decision
    out: dict[str, Any] = {"problems": []}
    with conn.cursor() as cur:
        cur.execute("SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = %s",
                    (d.new_slug,))
        row = cur.fetchone()
        target = int(row[0]) if row else None
        cur.execute("SELECT canonical_university_id FROM warehouse.source_university_mapping "
                    "WHERE source_code = %s AND source_entity_id = %s AND is_active", (d.source_code, d.source_entity_id))
        mapped = cur.fetchone()
        if target is None or mapped is None or int(mapped[0]) != target:
            out["problems"].append(f"{d.source_code} {d.source_entity_id} is on {mapped}, expected c{target}")
        # Nothing but the decided entity may sit on the canonical this script created.
        cur.execute("SELECT source_code, source_entity_id FROM warehouse.source_university_mapping "
                    "WHERE is_active AND canonical_university_id = %s", (target,))
        on_new = sorted(cur.fetchall())
        out["entities_on_the_new_canonical"] = on_new
        if target is not None and on_new != [(d.source_code, d.source_entity_id)]:
            out["problems"].append(f"the new canonical holds {on_new}")
        cur.execute("SELECT rr.canonical_university_id, count(*) FROM warehouse.ranking_record rr "
                    "JOIN warehouse.source_university_mapping m USING (source_mapping_id) "
                    "WHERE rr.canonical_university_id <> m.canonical_university_id GROUP BY 1")
        mismatched = cur.fetchall()
        out["ranking_records_whose_canonical_differs_from_their_mapping"] = mismatched
        if mismatched:
            out["problems"].append(f"ranking_record rows disagree with their mapping: {mismatched[:5]}")
        cur.execute("SELECT ar.canonical_university_id, ar.source_ranks_json::text FROM analytics.aggregated_rankings ar "
                    "WHERE ar.ranking_year = %s AND ar.universe_type = 'global' AND ar.canonical_university_id IN (%s, %s) "
                    "ORDER BY 1", (d.ranking_year, d.expect_canonical, target or -1))
        out["aggregated_global"] = cur.fetchall()
        # The old canonical must no longer carry THE's rank for the edition.
        for cid, ranks in out["aggregated_global"]:
            if cid == d.expect_canonical and json.loads(ranks).get("THE") is not None:
                out["problems"].append(f"c{d.expect_canonical} still carries a THE {d.ranking_year} rank")
    collisions = base.collision_scan(conn)
    out["same_edition_collisions"] = collisions
    if collisions:
        out["problems"].append(f"{len(collisions)} canonical(s) hold two universities in one edition")
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("phase", choices=("prepare", "reingest-the", "verify"))
    parser.add_argument("--commit", action="store_true", help="write; without it the phase only reports")
    parser.add_argument("--receipt", type=Path, help="write a JSON receipt here when committing")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    args = parser.parse_args(argv)
    pg = {"host": args.pg_host, "port": args.pg_port, "database": args.pg_database,
          "user": args.pg_user, "password": args.pg_password}

    if args.phase == "reingest-the":
        result = {"ingests": base.reingest_the([DECISION.ranking_year], pg, commit=args.commit)}
    else:
        import psycopg2

        conn = psycopg2.connect(host=pg["host"], port=pg["port"], dbname=pg["database"], user=pg["user"],
                                password=pg["password"])
        try:
            if args.phase == "verify":
                conn.set_session(readonly=True)
                result = verify(conn)
            else:
                result = plan_and_apply(conn, commit=args.commit)
        except base.PreconditionFailed as exc:
            conn.rollback()
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        finally:
            conn.close()
    result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result["database"] = args.pg_database
    for line in result.get("actions", []):
        print(f"  {line}")
    for item in result.get("ingests", []):
        print(f"  THE {item}")
    for key in ("problems", "entities_on_the_new_canonical", "aggregated_global",
                "ranking_records_whose_canonical_differs_from_their_mapping", "same_edition_collisions"):
        if key in result:
            print(f"  {key}: {result[key]}")
    print("verify is read-only: nothing was written" if args.phase == "verify"
          else "committed" if args.commit else "Plan only. Nothing was written. Re-run with --commit to apply.")
    if args.commit and args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps({"phase": args.phase, **result}, ensure_ascii=False, indent=2, default=str) + "\n",
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
