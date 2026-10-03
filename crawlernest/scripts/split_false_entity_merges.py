#!/usr/bin/env python3
"""Split universities the entity resolver merged by name, on the 2026-10-03 decision.

Seven source entities were attached to a canonical university that is a different
institution. Each was found by looking at what the warehouse stored under it, not by
guessing from names:

  * ``Miami University`` (canonical 1262) held two universities. It was seeded from QS's
    Miami University (Ohio); THE 636, ARWU ``university-of-miami`` and QS
    ``university-miami`` -- the University of Miami (Florida) -- were later attached to it
    by name normalisation, which treats "Miami University" and "University of Miami" as the
    same string. 1262 is renamed to the University of Miami, and the Ohio university gets a
    canonical of its own (the legacy bridge, which is Ohio's, moves with it).
  * Four THE entities, first seen on 2026-10-02 when THE 2015-2024 was ingested, were matched
    fuzzily (0.85-0.90) to a different university: Kazan National Research Technical
    University -> Technological University; UNIRIO -> Federal University of Rio de Janeiro;
    ENS Paris-Saclay -> ENS Paris; National Taichung University of Science and Technology ->
    Taiwan Tech.
  * One more, THE 623826 Jiangxi University of Finance and Economics -> Guangxi University of
    Finance and Economics, collides with nothing but is the same defect.

Two universities on one canonical keep one rank per edition and silently drop the other, so
the damage is rows that are missing or belong to the wrong university, not only a wrong label.

A decision in ``warehouse.mapping_review`` changes nothing by itself: the pipeline applies it
during the next ingest, which is also what rewrites the rows. So this does it in the order the
rest of the repository already uses.

    1. ``prepare``     rename 1262, create the missing canonicals, move the legacy bridge,
                       record a ``remapped`` review for each entity. One transaction.
    2. ``reingest-the`` replay the committed THE files for the affected editions through
                       ``ingest_rankings_payload``; the ingest applies the reviews and rewrites
                       the rows.
    3. QS cannot be re-crawled, so its rows are fixed from what is already on disk:
         * 2026 ``world`` and ``region:north-america`` are replayed with ``reingest_qs_universes.py``
           (rehearsed: the only rows it changes are the Miami ones and one FIU slug spelling).
         * 2025 ``world`` is NOT replayed. Its prune would delete 13 legacy rows that carry a
           ``relabelled_on`` note and are in no snapshot. The 2025 snapshot also holds no row for the
           University of Miami, so there is nothing to restore there: only Ohio's one row is on the wrong
           canonical.
         * 2026 ``special:sustainability`` has no verified snapshot to replay either.
         * ``qs-leftovers`` therefore moves those two Ohio rows (2025 global, 2026 special/sustainability)
           by id, after checking they are exactly what it expects, and moves the special row's aggregated
           row, which is QS-only. ``qs-2025`` then ingests Ohio's single 2025 row with no batch id, which
           prunes nothing and recomputes the 2025 aggregates.
    4. ``preview`` repairs the two derived ``warehouse.ranking_decision_preview`` keys the rename moves.
       The Java scoped read joins that table on the canonical's normalised name, so the stale
       ``miami university`` rows (a blend of both universities) would otherwise attach to the Ohio
       canonical. ``decision-ranking-preview`` is NOT used: it inserts with ``ON CONFLICT DO NOTHING``, so
       it would leave the stale rows and instead add some fifteen thousand rows for editions the
       preview table never held.
    5. ``verify`` is read-only: the collision scan, the remaps, and the Miami split.

Every phase prints what it would do and writes nothing without ``--commit``. Re-running a phase
after it has been applied does nothing.

    ./.venv/bin/python crawlernest/scripts/split_false_entity_merges.py prepare --pg-password test
    ./.venv/bin/python crawlernest/scripts/split_false_entity_merges.py prepare --pg-password test --commit
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

DATABASES_DIR = _MODULE_ROOT / "crawlernest-kb" / "databases"

#: Who the review rows say decided. They record a decision a person made and this script applied.
DECIDED_BY = "claude-code, at the direction of ek2412045@gmail.com"
DECIDED_ON = "2026-10-03"


@dataclass(frozen=True)
class NewCanonical:
    key: str
    slug: str
    display_name: str
    #: An existing canonical whose country the new one shares.
    country_from: int
    why: str


@dataclass(frozen=True)
class Rename:
    canonical_id: int
    expect_slug: str
    expect_name: str
    slug: str
    display_name: str


@dataclass(frozen=True)
class Remap:
    source_code: str
    source_entity_id: str
    source_name: str
    #: The canonical the entity is on now, and must be for the remap to apply.
    expect_canonical: int
    #: A key into NEW_CANONICALS, or an existing canonical id.
    target: "str | int"
    why: str


RENAME = Rename(
    canonical_id=1262,
    expect_slug="miami-university",
    expect_name="Miami University",
    slug="university-of-miami",
    display_name="University of Miami",
)

NEW_CANONICALS: tuple[NewCanonical, ...] = (
    NewCanonical(
        "miami_ohio", "miami-university", "Miami University", 1262,
        "Miami University, Oxford, Ohio; the slug and legacy bridge 1262 always described it",
    ),
    NewCanonical(
        "kazan_technical", "kazan-national-research-technical-university",
        "Kazan National Research Technical University", 1247,
        "a different university from Kazan National Research Technological University (c1247)",
    ),
    NewCanonical(
        "ens_paris_saclay", "ecole-normale-superieure-paris-saclay",
        "École normale supérieure Paris-Saclay", 561011,
        "a different institution from the ENS in Paris (c561011)",
    ),
    NewCanonical(
        "ntcust", "national-taichung-university-of-science-and-technology",
        "National Taichung University of Science and Technology", 389,
        "a different university from National Taiwan University of Science and Technology (c389)",
    ),
    NewCanonical(
        "jxufe", "jiangxi-university-of-finance-and-economics",
        "Jiangxi University of Finance and Economics", 363854,
        "a different university from Guangxi University of Finance and Economics (c363854)",
    ),
)

REMAPS: tuple[Remap, ...] = (
    Remap("THE", "131462", "Miami University", 1262, "miami_ohio",
          "THE lists Miami University (Ohio) separately from the University of Miami (THE 636)"),
    Remap("QS", "/universities/miami-university", "Miami University", 1262, "miami_ohio",
          "QS's Miami University is the Ohio university; the University of Miami is /universities/university-miami"),
    Remap("THE", "624081", "Kazan National Research Technical University", 1247, "kazan_technical",
          "fuzzy match 0.88 to the Technological University, which THE lists as its own entry (587760)"),
    Remap("THE", "639095", "Federal University of the State of Rio de Janeiro (UNIRIO)", 560898, 1484,
          "UNIRIO is c1484, Universidade Federal do Estado do Rio de Janeiro; c560898 is UFRJ"),
    Remap("THE", "131404", "École normale supérieure Paris-Saclay", 561011, "ens_paris_saclay",
          "fuzzy match 0.87 to the ENS in Paris; THE lists both (523 and 131404)"),
    Remap("THE", "715159", "National Taichung University of Science and Technology", 389, "ntcust",
          "fuzzy match 0.87 to Taiwan Tech, a different university"),
    Remap("THE", "623826", "Jiangxi University of Finance and Economics", 363854, "jxufe",
          "fuzzy match 0.86 to a university in another province"),
)

@dataclass(frozen=True)
class Reject:
    """A source entity a person says is NOT the canonical it would otherwise be matched to."""

    source_code: str
    source_entity_id: str
    source_name: str
    #: The NEW_CANONICALS key the resolver would match it to once that canonical exists.
    would_match: str
    why: str


#: Creating a canonical named "Kazan National Research Technical University" gives the resolver something
#: to match "Irkutsk National Research Technical University" to (fuzzy, 0.83). Found by rehearsing this
#: repair on a copy: the replay attached it, and the collision scan flagged the result. Rejecting it first
#: leaves it unresolved, as it has been.
REJECTS: tuple[Reject, ...] = (
    Reject("THE", "624069", "Irkutsk National Research Technical University", "kazan_technical",
           "a different university from Kazan National Research Technical University; found by rehearsal"),
)

#: The THE entities whose editions are replayed. A rejection is not in it: it only has to be on record before
#: the replay, and the rejected entity (Irkutsk) is also in THE 2025 and 2026, which have nothing to repair.
#: The 2026-10-03 run replayed those two as well, before this was narrowed; the counts were identical to the
#: rehearsal's, so nothing depended on it.
THE_IDS = {r.source_entity_id for r in REMAPS if r.source_code == "THE"}


class PreconditionFailed(RuntimeError):
    """The warehouse is not in a state this decision was made against; nothing was written."""


def _normalize(display_name: str) -> str:
    from entity_resolution.normalizer import normalize_university_name

    return normalize_university_name(display_name)


def affected_the_years(databases_dir: Path = DATABASES_DIR, ids: Sequence[str] = tuple(sorted(THE_IDS))) -> list[int]:
    """The THE editions whose committed file mentions any of the remapped entities."""
    wanted = {str(i) for i in ids}
    years: list[int] = []
    for path in sorted(Path(databases_dir).glob("the_rankings_*.json")):
        year = int(path.stem.rsplit("_", 1)[1])
        rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
        if any(str(row.get("id")) in wanted for row in rows):
            years.append(year)
    return years


def _one(cur: Any, sql: str, params: Sequence[Any] = ()) -> Optional[tuple]:
    cur.execute(sql, params)
    return cur.fetchone()


def plan_and_apply(conn: Any, *, commit: bool) -> dict[str, Any]:
    """Every step of ``prepare``, in one transaction; rolled back unless ``commit``."""
    actions: list[str] = []
    created: dict[str, int] = {}
    with conn.cursor() as cur:
        # --- rename 1262 (must precede creating the Ohio canonical, which takes its old slug)
        row = _one(cur, "SELECT canonical_slug, display_name FROM warehouse.canonical_university "
                        "WHERE canonical_university_id = %s", (RENAME.canonical_id,))
        if row is None:
            raise PreconditionFailed(f"canonical {RENAME.canonical_id} does not exist")
        if (row[0], row[1]) == (RENAME.slug, RENAME.display_name):
            actions.append(f"rename c{RENAME.canonical_id}: already {RENAME.display_name!r}")
        elif (row[0], row[1]) == (RENAME.expect_slug, RENAME.expect_name):
            cur.execute(
                "UPDATE warehouse.canonical_university SET canonical_slug = %s, display_name = %s, "
                "display_name_normalized = %s, updated_at = now() WHERE canonical_university_id = %s",
                (RENAME.slug, RENAME.display_name, _normalize(RENAME.display_name), RENAME.canonical_id),
            )
            actions.append(f"rename c{RENAME.canonical_id}: {row[1]!r} ({row[0]}) -> {RENAME.display_name!r} ({RENAME.slug})")
        else:
            raise PreconditionFailed(f"canonical {RENAME.canonical_id} is {row!r}, not the state this was decided against")

        # --- new canonicals
        for spec in NEW_CANONICALS:
            existing = _one(cur, "SELECT canonical_university_id, display_name FROM warehouse.canonical_university "
                                 "WHERE canonical_slug = %s", (spec.slug,))
            if existing is not None:
                if existing[1] != spec.display_name:
                    raise PreconditionFailed(f"slug {spec.slug!r} is taken by {existing[1]!r}")
                created[spec.key] = int(existing[0])
                actions.append(f"canonical {spec.display_name!r}: already c{existing[0]}")
                continue
            country = _one(cur, "SELECT country_id FROM warehouse.canonical_university WHERE canonical_university_id = %s",
                           (spec.country_from,))
            if country is None:
                raise PreconditionFailed(f"canonical {spec.country_from}, whose country {spec.key} shares, does not exist")
            cur.execute(
                "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized, "
                "country_id, status, metadata) VALUES (%s, %s, %s, %s, 'active', %s::jsonb) "
                "RETURNING canonical_university_id",
                (spec.slug, spec.display_name, _normalize(spec.display_name), country[0],
                 json.dumps({"created_by": "split_false_entity_merges", "decided_on": DECIDED_ON, "why": spec.why})),
            )
            created[spec.key] = int(cur.fetchone()[0])
            actions.append(f"canonical {spec.display_name!r}: created c{created[spec.key]} ({spec.slug})")

        # --- legacy bridge: the legacy university 1262 is the Ohio one
        ohio = created["miami_ohio"]
        link = _one(cur, "SELECT canonical_university_id FROM warehouse.canonical_university_link "
                         "WHERE university_id = %s AND link_method = 'legacy_bridge'", (RENAME.canonical_id,))
        if link is None:
            raise PreconditionFailed("no legacy bridge row for university 1262")
        if int(link[0]) == ohio:
            actions.append("legacy bridge 1262: already on the Ohio canonical")
        elif int(link[0]) == RENAME.canonical_id:
            cur.execute("UPDATE warehouse.canonical_university_link SET canonical_university_id = %s, updated_at = now() "
                        "WHERE university_id = %s AND link_method = 'legacy_bridge'", (ohio, RENAME.canonical_id))
            actions.append(f"legacy bridge 1262: c{RENAME.canonical_id} -> c{ohio}")
        else:
            raise PreconditionFailed(f"legacy bridge 1262 points at c{link[0]}")

        # --- one review per entity
        for remap in REMAPS:
            target = created[remap.target] if isinstance(remap.target, str) else int(remap.target)
            mapping = _one(cur, "SELECT canonical_university_id, match_method, confidence_score, ranking_source_id "
                                "FROM warehouse.source_university_mapping WHERE source_code = %s AND source_entity_id = %s "
                                "AND is_active", (remap.source_code, remap.source_entity_id))
            if mapping is None:
                raise PreconditionFailed(f"{remap.source_code} {remap.source_entity_id} has no active mapping")
            current = int(mapping[0]) if mapping[0] is not None else None
            if current not in (remap.expect_canonical, target):
                raise PreconditionFailed(
                    f"{remap.source_code} {remap.source_entity_id} is on c{current}, expected c{remap.expect_canonical}")
            review = _one(cur, "SELECT decision, decided_canonical_university_id FROM warehouse.mapping_review "
                               "WHERE source_code = %s AND source_entity_id = %s",
                          (remap.source_code, remap.source_entity_id))
            if review is not None:
                if review[0] == "remapped" and int(review[1]) == target:
                    actions.append(f"review {remap.source_code} {remap.source_entity_id}: already -> c{target}")
                    continue
                raise PreconditionFailed(
                    f"{remap.source_code} {remap.source_entity_id} already has a {review[0]} review; a person's decision is not overwritten")
            cur.execute(
                "INSERT INTO warehouse.mapping_review (ranking_source_id, source_entity_id, reviewed_source_name, "
                "reviewed_canonical_university_id, reviewed_match_method, reviewed_confidence_score, decision, "
                "decided_canonical_university_id, decided_by, note, source_code) "
                "VALUES (%s, %s, %s, %s, %s, %s, 'remapped', %s, %s, %s, %s)",
                (mapping[3], remap.source_entity_id, remap.source_name, current, mapping[1], mapping[2], target,
                 DECIDED_BY, f"{DECIDED_ON}: {remap.why}", remap.source_code),
            )
            actions.append(f"review {remap.source_code} {remap.source_entity_id}: c{current} -> c{target}")

        # --- rejections: entities the new canonicals would otherwise attract
        for reject in REJECTS:
            target = created[reject.would_match]
            mapped = _one(cur, "SELECT canonical_university_id FROM warehouse.source_university_mapping "
                               "WHERE source_code = %s AND source_entity_id = %s AND is_active "
                               "AND canonical_university_id IS NOT NULL", (reject.source_code, reject.source_entity_id))
            if mapped is not None:
                raise PreconditionFailed(
                    f"{reject.source_code} {reject.source_entity_id} is already mapped to c{mapped[0]}; this "
                    "rejection was written for an entity that has no mapping")
            review = _one(cur, "SELECT decision FROM warehouse.mapping_review WHERE source_code = %s AND source_entity_id = %s",
                          (reject.source_code, reject.source_entity_id))
            if review is not None:
                if review[0] == "rejected":
                    actions.append(f"review {reject.source_code} {reject.source_entity_id}: already rejected")
                    continue
                raise PreconditionFailed(f"{reject.source_code} {reject.source_entity_id} already has a {review[0]} review")
            source_id = _one(cur, "SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = %s",
                             (reject.source_code,))
            cur.execute(
                "INSERT INTO warehouse.mapping_review (ranking_source_id, source_entity_id, reviewed_source_name, "
                "reviewed_canonical_university_id, reviewed_match_method, reviewed_confidence_score, decision, "
                "decided_canonical_university_id, decided_by, note, source_code) "
                "VALUES (%s, %s, %s, %s, 'fuzzy_review', NULL, 'rejected', NULL, %s, %s, %s)",
                (source_id[0] if source_id else None, reject.source_entity_id, reject.source_name, target,
                 DECIDED_BY, f"{DECIDED_ON}: {reject.why}", reject.source_code),
            )
            actions.append(f"review {reject.source_code} {reject.source_entity_id}: rejected as c{target}")

    if commit:
        conn.commit()
    else:
        conn.rollback()
    return {"committed": commit, "actions": actions, "created": created}


def reingest_the(years: Sequence[int], pg: dict[str, Any], *, commit: bool) -> list[dict[str, Any]]:
    from pipeline.commands.canonical import ingest_rankings_payload, load_json_payload

    results = []
    for year in years:
        path = DATABASES_DIR / f"the_rankings_{year}.json"
        payload = load_json_payload(path)
        if not commit:
            results.append({"year": year, "rows": len(payload), "committed": False})
            continue
        summary = ingest_rankings_payload(
            source="THE", payload=payload, ranking_year=year, ranking_type="world", source_version=None,
            pg_host=pg["host"], pg_port=pg["port"], pg_database=pg["database"], pg_user=pg["user"],
            pg_password=pg["password"],
        )
        results.append({
            "year": year, "rows": len(payload), "committed": True,
            "matched": summary.matched_count, "unresolved": summary.unresolved_count,
            "rows_written": summary.rows_written, "aggregated_rows": summary.aggregated_row_count,
        })
    return results


MIAMI_QS_IDS = ("/universities/miami-university", "/universities/university-miami")
SNAPSHOTS_DIR = _MODULE_ROOT / "crawlernest-kb" / "qs_universes"


def qs_2025_miami_rows(snapshots_dir: Path = SNAPSHOTS_DIR) -> list[dict[str, Any]]:
    """Ohio's row of the verified 2025 QS snapshot, exactly one, or an error. The snapshot has no Florida row."""
    from ranking_edition import snapshot_edition_ok

    base = Path(snapshots_dir) / "2025" / "global" / "global"
    status = json.loads((base / "run_status.json").read_text(encoding="utf-8"))
    if not snapshot_edition_ok(status, ranking_year=2025):
        raise PreconditionFailed("the 2025 QS snapshot records no verified 2025 edition")
    rows = json.loads((base / "raw_snapshot.json").read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("rows", [])
    wanted = MIAMI_QS_IDS[0]
    hit = [r for r in rows if isinstance(r, dict)
           and str(r.get("qs_profile_path") or r.get("path") or "").strip() == wanted]
    if len(hit) != 1:
        raise PreconditionFailed(f"{wanted} appears {len(hit)} times in the 2025 snapshot, expected 1")
    return hit


def reingest_qs_2025(pg: dict[str, Any], *, commit: bool) -> dict[str, Any]:
    from models import University
    from multi_source.adapters import QSAdapter
    from pipeline.utils.postgres import build_multi_source_pipeline, connect_postgres

    rows = qs_2025_miami_rows()
    if not commit:
        return {"rows": [(r.get("qs_profile_path") or r.get("path"), r.get("rank")) for r in rows], "committed": False}
    standardized = QSAdapter(ranking_year=2025, ranking_type="world", universe_type="global",
                             universe_key="global").adapt([University.from_dict(r) for r in rows])
    conn = connect_postgres(pg["host"], pg["port"], pg["database"], pg["user"], pg["password"])
    try:
        pipeline = build_multi_source_pipeline(conn)
        # No batch_id on purpose: the prune and the shrink guard both need one, and a one-row batch
        # must not prune the other fifteen hundred rows of the edition.
        summary = pipeline.ingest_records(standardized, batch_id=None, run_label_prefix="entity_split",
                                          ranking_type="world", enable_aggregation=True)
        conn.commit()
    finally:
        conn.close()
    return {"committed": True, "matched": summary.matched_count, "unresolved": summary.unresolved_count,
            "rows_written": summary.rows_written, "aggregated_rows": summary.aggregated_row_count}


def move_qs_leftovers(conn: Any, *, commit: bool) -> dict[str, Any]:
    """Ohio's QS rows no replay reaches: 2025 global, and 2026 ``special:sustainability`` (no snapshot)."""
    ohio_slug = "miami-university"
    actions: list[str] = []
    with conn.cursor() as cur:
        ohio = _one(cur, "SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = %s",
                    (ohio_slug,))
        mapping = _one(cur, "SELECT source_mapping_id, canonical_university_id FROM warehouse.source_university_mapping "
                            "WHERE source_code = 'QS' AND source_entity_id = %s AND is_active", (MIAMI_QS_IDS[0],))
        if ohio is None or mapping is None or int(mapping[1]) != int(ohio[0]):
            raise PreconditionFailed("run the prepare phase and the QS replays first: the Ohio mapping is not on its own canonical")
        cur.execute(
            "SELECT ranking_record_id FROM warehouse.ranking_record WHERE source_mapping_id = %s "
            "AND canonical_university_id = %s", (mapping[0], RENAME.canonical_id))
        stuck = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT ranking_year, universe_type, universe_key, count(*) FROM warehouse.ranking_record "
            "WHERE ranking_record_id = ANY(%s) GROUP BY 1,2,3", (stuck,)) if stuck else None
        found = cur.fetchall() if stuck else []
        expected = [(2025, "global", "global", 1), (2026, "special", "sustainability", 1)]
        if found and sorted(found) != expected:
            raise PreconditionFailed(f"unexpected Ohio rows left on c{RENAME.canonical_id}: {found}")
        if stuck:
            cur.execute("UPDATE warehouse.ranking_record SET canonical_university_id = %s, updated_at = now() "
                        "WHERE ranking_record_id = ANY(%s)", (ohio[0], stuck))
            actions.append(f"ranking_record {stuck}: c{RENAME.canonical_id} -> c{ohio[0]}")
            # Only the special universe's aggregated row is moved by hand: it is QS-only, so it is the
            # Ohio row unchanged. The 2025 global aggregate mixes sources and is recomputed by qs-2025.
            cur.execute("SELECT aggregated_ranking_id, source_ranks_json::text FROM analytics.aggregated_rankings "
                        "WHERE canonical_university_id = %s AND ranking_year = 2026 AND universe_type = 'special' "
                        "AND universe_key = 'sustainability'", (RENAME.canonical_id,))
            agg = cur.fetchall()
            if len(agg) > 1 or any('"THE"' in a[1] and '"THE": null' not in a[1] for a in agg):
                raise PreconditionFailed(f"the special/sustainability aggregated row is not QS-only: {agg}")
            if agg:
                cur.execute("UPDATE analytics.aggregated_rankings SET canonical_university_id = %s, updated_at = now() "
                            "WHERE aggregated_ranking_id = %s", (ohio[0], agg[0][0]))
                actions.append(f"aggregated_rankings {agg[0][0]}: c{RENAME.canonical_id} -> c{ohio[0]}")
        else:
            actions.append("qs-leftovers: nothing left to move")
    if commit:
        conn.commit()
    else:
        conn.rollback()
    return {"committed": commit, "actions": actions}


def refresh_miami_preview(conn: Any, *, commit: bool) -> dict[str, Any]:
    """Rewrite the 2025 and 2026 preview rows of the two Miami universities from the aggregated rankings."""
    from crawlernest_ranking_crawler.decision_writer import (
        build_decision_row, load_aggregated_rows_from_warehouse, write_decision_rows,
    )
    from crawlernest_ranking_crawler.explain_layer import build_explain

    years = (2025, 2026)
    with conn.cursor() as cur:
        cur.execute("SELECT canonical_slug, display_name_normalized FROM warehouse.canonical_university "
                    "WHERE canonical_slug IN (%s, %s)", (RENAME.slug, "miami-university"))
        found = dict(cur.fetchall())
    if set(found) != {RENAME.slug, "miami-university"}:
        raise PreconditionFailed("run the prepare phase first: both Miami canonicals must exist")
    # The stale key is the old shared name; the two new ones are what the canonicals are called now.
    names = sorted(set(found.values()) | {_normalize(RENAME.expect_name)})
    rows = [r for r in load_aggregated_rows_from_warehouse(conn)
            if r.normalized_university_name in names and int(r.ranking_year) in years]
    decision_rows = [build_decision_row(r, build_explain(r)) for r in rows]
    summary = {"names": names,
               "rows": [(d.normalized_university_name, d.ranking_year, d.sources) for d in decision_rows]}
    if not commit:
        conn.rollback()
        return {"committed": False, "preview": summary}
    with conn.cursor() as cur:
        cur.execute("DELETE FROM warehouse.ranking_decision_preview "
                    "WHERE normalized_university_name = ANY(%s) AND ranking_year = ANY(%s)", (names, list(years)))
        deleted = cur.rowcount
    write_decision_rows(decision_rows, conn)  # commits, together with the delete above
    return {"committed": True, "preview": summary, "deleted": deleted, "inserted": len(decision_rows)}


def collision_scan(conn: Any, databases_dir: Path = DATABASES_DIR) -> list[str]:
    """Canonicals with two actively mapped universities in one THE or ARWU edition."""
    import re
    from collections import defaultdict

    with conn.cursor() as cur:
        cur.execute("SELECT source_code, source_entity_id, canonical_university_id FROM "
                    "warehouse.source_university_mapping WHERE is_active AND canonical_university_id IS NOT NULL")
        mapping = {(s, e): c for s, e, c in cur.fetchall()}
        cur.execute("SELECT canonical_university_id, display_name FROM warehouse.canonical_university")
        names = dict(cur.fetchall())
    found: list[str] = []
    for source, prefix in (("THE", "the_rankings_"), ("ARWU", "arwu_rankings_")):
        for path in sorted(Path(databases_dir).glob(f"{prefix}*.json")):
            by: dict[int, list[str]] = defaultdict(list)
            for row in json.loads(path.read_text(encoding="utf-8")).get("rows", []):
                eid = str(row["id"])
                canonical = mapping.get((source, eid)) or mapping.get((source, re.sub(r":(19|20)\d{2}(?=:)", "", eid)))
                if canonical is not None:
                    by[canonical].append(str(row["name"]))
            for canonical, entries in by.items():
                if len(entries) > 1:
                    found.append(f"{source} {path.stem[-4:]}: c{canonical} {names.get(canonical)!r} holds {entries}")
    return found


def verify(conn: Any) -> dict[str, Any]:
    """Read-only. The two things this decision promised."""
    out: dict[str, Any] = {"problems": []}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT m.canonical_university_id, count(*) FROM warehouse.source_university_mapping m "
            "WHERE m.is_active AND m.canonical_university_id IS NOT NULL AND (m.source_code, m.source_entity_id) IN %s "
            "GROUP BY 1", (tuple((r.source_code, r.source_entity_id) for r in REMAPS),))
        out["remapped_entities_per_canonical"] = dict(cur.fetchall())
        for remap in REMAPS:
            cur.execute("SELECT canonical_university_id FROM warehouse.source_university_mapping "
                        "WHERE source_code = %s AND source_entity_id = %s AND is_active",
                        (remap.source_code, remap.source_entity_id))
            row = cur.fetchone()
            target = remap.target
            cur.execute("SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = %s",
                        (next((n.slug for n in NEW_CANONICALS if n.key == target), "") if isinstance(target, str) else "",))
            want = cur.fetchone()
            want_id = int(want[0]) if want else (int(target) if not isinstance(target, str) else None)
            if row is None or want_id is None or int(row[0]) != want_id:
                out["problems"].append(f"{remap.source_code} {remap.source_entity_id} is on {row}, expected c{want_id}")
        cur.execute("SELECT rr.canonical_university_id, count(*) FROM warehouse.ranking_record rr "
                    "JOIN warehouse.source_university_mapping m USING (source_mapping_id) "
                    "WHERE rr.canonical_university_id <> m.canonical_university_id GROUP BY 1")
        mismatched = cur.fetchall()
        out["ranking_records_whose_canonical_differs_from_their_mapping"] = mismatched
        # Nothing but the entities decided here may sit on a canonical this script created.
        cur.execute("SELECT m.source_code, m.source_entity_id FROM warehouse.source_university_mapping m "
                    "JOIN warehouse.canonical_university cu USING (canonical_university_id) "
                    "WHERE m.is_active AND cu.canonical_slug = ANY(%s)", ([n.slug for n in NEW_CANONICALS],))
        on_new = sorted(cur.fetchall())
        expected_on_new = sorted((r.source_code, r.source_entity_id) for r in REMAPS if isinstance(r.target, str))
        out["entities_on_the_new_canonicals"] = on_new
        if on_new != expected_on_new:
            out["problems"].append(f"the new canonicals attracted other entities: {sorted(set(on_new) - set(expected_on_new))}")
        if mismatched:
            out["problems"].append(f"ranking_record rows disagree with their mapping: {mismatched[:5]}")
        cur.execute("SELECT ar.ranking_year, cu.display_name, ar.source_ranks_json::text FROM analytics.aggregated_rankings ar "
                    "JOIN warehouse.canonical_university cu USING (canonical_university_id) "
                    "WHERE cu.canonical_slug IN (%s, 'miami-university') AND ar.universe_type = 'global' "
                    "AND ar.ranking_year IN (2016, 2017, 2021, 2024, 2025, 2026) ORDER BY 2, 1", (RENAME.slug,))
        out["miami_aggregated_global"] = cur.fetchall()
    collisions = collision_scan(conn)
    out["same_edition_collisions"] = collisions
    if collisions:
        out["problems"].append(f"{len(collisions)} canonical(s) still hold two universities in one edition")
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("phase", choices=("prepare", "reingest-the", "qs-leftovers", "qs-2025", "preview", "verify"))
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

    if args.phase == "prepare":
        import psycopg2

        conn = psycopg2.connect(host=pg["host"], port=pg["port"], dbname=pg["database"], user=pg["user"],
                                password=pg["password"])
        try:
            result = plan_and_apply(conn, commit=args.commit)
        except PreconditionFailed as exc:
            conn.rollback()
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        finally:
            conn.close()
    elif args.phase == "qs-2025":
        try:
            result = {"qs_2025": reingest_qs_2025(pg, commit=args.commit)}
        except PreconditionFailed as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
    elif args.phase in ("qs-leftovers", "verify", "preview"):
        import psycopg2

        conn = psycopg2.connect(host=pg["host"], port=pg["port"], dbname=pg["database"], user=pg["user"],
                                password=pg["password"])
        try:
            if args.phase == "verify":
                conn.set_session(readonly=True)
                result = verify(conn)
            elif args.phase == "preview":
                result = refresh_miami_preview(conn, commit=args.commit)
            else:
                result = move_qs_leftovers(conn, commit=args.commit)
        except PreconditionFailed as exc:
            conn.rollback()
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
        finally:
            conn.close()
    else:
        years = affected_the_years()
        result = {"years": years, "ingests": reingest_the(years, pg, commit=args.commit)}

    result["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    result["database"] = args.pg_database
    for line in result.get("actions", []):
        print(f"  {line}")
    for item in result.get("ingests", []):
        print(f"  THE {item}")
    for key in ("qs_2025", "preview", "deleted", "inserted", "problems", "entities_on_the_new_canonicals",
                "remapped_entities_per_canonical",
                "ranking_records_whose_canonical_differs_from_their_mapping", "same_edition_collisions"):
        if key in result:
            print(f"  {key}: {result[key]}")
    for row in result.get("miami_aggregated_global", []):
        print(f"  miami_aggregated_global: {row}")
    if args.phase == "verify":
        print("verify is read-only: nothing was written")
    else:
        print("committed" if args.commit else "Plan only. Nothing was written. Re-run with --commit to apply.")
    if args.commit and args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps({"phase": args.phase, **result}, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
