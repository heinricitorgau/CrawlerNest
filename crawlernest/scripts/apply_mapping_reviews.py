#!/usr/bin/env python3
from __future__ import annotations

"""
Record a batch of entity-resolution decisions in warehouse.mapping_review.

The review screen is one decision at a time. Working through a backlog of
seventy is faster from a file, and this applies one.

Writes warehouse.mapping_review and nothing else -- the same table the API
writes, under the same constraints. Nothing takes effect here: the pipeline
reads these decisions on the next ingest, re-points or drops the mapping, and
retires a rejected one via is_active. Until then the warehouse is unchanged.

    # see what is waiting
    PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer \\
        -f crawlernest/scripts/mapping_review_queue.sql

    # write decisions.csv, then preview -- this is the default, it writes nothing
    ./.venv/bin/python crawlernest/scripts/apply_mapping_reviews.py decisions.csv \\
        --decided-by you@example.com

    # apply
    ./.venv/bin/python crawlernest/scripts/apply_mapping_reviews.py decisions.csv \\
        --decided-by you@example.com --commit

decisions.csv takes one decision per line, `#` starts a comment:

    source_entity_id, decision, canonical_id, note
    718,              confirmed
    587694,           rejected,  ,            Perm is not Tomsk
    649211,           remapped,  1485

`canonical_id` is required for `remapped`, forbidden for `rejected`, and
defaults to the currently matched university for `confirmed` -- confirming
means the resolver was right, so repeating its answer is noise.

The batch is validated in full before anything is written. A bad line fails
the run rather than leaving half a backlog applied.
"""

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

CONFIRMED = "confirmed"
REJECTED = "rejected"
REMAPPED = "remapped"
VALID_DECISIONS = (CONFIRMED, REJECTED, REMAPPED)

#: The skeleton's placeholder, and the things people write in its place while
#: still thinking. All mean "not judged yet", so the line is skipped rather
#: than failing the batch around it.
UNDECIDED = frozenset({"", "?", "??", "???", "-", "--", "todo", "TODO"})


@dataclass(frozen=True)
class Decision:
    line_number: int
    source_entity_id: str
    decision: str
    canonical_id: Optional[int]
    note: Optional[str]


@dataclass(frozen=True)
class Pending:
    source_code: str
    source_entity_id: str
    source_name: str
    canonical_university_id: int
    canonical_name: str
    match_method: str
    confidence_score: float
    existing_decision: Optional[str]


def parse_decisions(path: Path) -> list[Decision]:
    out: list[Decision] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            cells = [cell.strip() for cell in row]
            while cells and cells[-1] == "":
                cells.pop()
            if not cells or cells[0].startswith("#"):
                continue
            if cells[0].lower() in {"source_entity_id", "entity_id"}:
                continue  # header
            if len(cells) < 2 or cells[1] in UNDECIDED:
                # An id with no decision is an entry not yet judged, which is
                # what a freshly generated skeleton is made of. Skipping lets a
                # half-finished file apply the half that is finished. A
                # misspelt decision still fails; only an absent one is quiet.
                continue

            canonical_id: Optional[int] = None
            if len(cells) >= 3 and cells[2] != "":
                try:
                    canonical_id = int(cells[2])
                except ValueError:
                    raise SystemExit(
                        f"{path}:{line_number}: canonical_id must be a number, got {cells[2]!r}"
                    ) from None

            # Everything past the canonical id is the note, rejoined: a
            # reason worth writing down usually has a comma in it, and a
            # truncated explanation is worse than none.
            note = ", ".join(cells[3:]).strip() if len(cells) >= 4 else ""

            out.append(
                Decision(
                    line_number=line_number,
                    source_entity_id=cells[0],
                    decision=cells[1].lower(),
                    canonical_id=canonical_id,
                    note=note or None,
                )
            )
    if not out:
        raise SystemExit(f"{path}: no decisions found")
    return out


def load_pending(conn: Any) -> dict[str, list[Pending]]:
    """Everything reviewable, keyed by source_entity_id.

    A list per key: entity ids are only unique within a source, and silently
    picking one of two would write a decision against the wrong source.

    Read from warehouse.v_entity_mapping rather than
    warehouse.source_university_mapping, so that a source which is not a
    ranking -- admission pages, whose mappings land in
    warehouse.source_mapping -- is reviewable through this same file format.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                m.source_code,
                m.source_entity_id,
                COALESCE(
                    m.metadata #>> '{raw_row,name}',
                    m.metadata ->> 'normalized_name',
                    m.source_entity_id
                ),
                m.canonical_university_id,
                cu.display_name,
                m.match_method,
                m.confidence_score,
                r.decision
            FROM warehouse.v_entity_mapping m
            JOIN warehouse.canonical_university cu
                ON cu.canonical_university_id = m.canonical_university_id
            LEFT JOIN warehouse.mapping_review r
                ON r.source_code = m.source_code
               AND r.source_entity_id = m.source_entity_id
            WHERE m.is_active
              AND m.match_method IN ('fuzzy', 'fuzzy_review')
            """
        )
        rows = cur.fetchall()

    pending: dict[str, list[Pending]] = {}
    for row in rows:
        entry = Pending(
            source_code=str(row[0]),
            source_entity_id=str(row[1]),
            source_name=str(row[2]),
            canonical_university_id=int(row[3]),
            canonical_name=str(row[4]),
            match_method=str(row[5]),
            confidence_score=float(row[6]),
            existing_decision=None if row[7] is None else str(row[7]),
        )
        pending.setdefault(entry.source_entity_id, []).append(entry)
    return pending


def canonical_exists(conn: Any, canonical_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM warehouse.canonical_university WHERE canonical_university_id = %s",
            (canonical_id,),
        )
        return cur.fetchone() is not None


def resolve(
    conn: Any,
    decisions: list[Decision],
    pending: dict[str, list[Pending]],
    *,
    overwrite: bool,
) -> tuple[list[tuple[Decision, Pending, Optional[int]]], list[str]]:
    """Pair each decision with its mapping, collecting every problem found.

    Returns (resolved, problems). Problems are reported together so one run
    surfaces every bad line rather than the first.
    """
    resolved: list[tuple[Decision, Pending, Optional[int]]] = []
    problems: list[str] = []
    seen: set[tuple[str, str]] = set()

    for decision in decisions:
        where = f"line {decision.line_number} ({decision.source_entity_id})"

        candidates = pending.get(decision.source_entity_id, [])
        if not candidates:
            problems.append(f"{where}: no active fuzzy mapping with this id")
            continue
        if len(candidates) > 1:
            sources = ", ".join(sorted(c.source_code for c in candidates))
            problems.append(
                f"{where}: id exists for more than one source ({sources}); "
                "this file format cannot say which"
            )
            continue
        match = candidates[0]

        key = (match.source_code, match.source_entity_id)
        if key in seen:
            problems.append(f"{where}: decided twice in this file")
            continue
        seen.add(key)

        if match.existing_decision is not None and not overwrite:
            problems.append(
                f"{where}: already decided as {match.existing_decision!r}; "
                "pass --overwrite to replace it"
            )
            continue

        if decision.decision not in VALID_DECISIONS:
            problems.append(
                f"{where}: decision must be one of {', '.join(VALID_DECISIONS)}, "
                f"got {decision.decision!r}"
            )
            continue

        target: Optional[int]
        if decision.decision == REJECTED:
            if decision.canonical_id is not None:
                problems.append(f"{where}: a rejection cannot name a canonical university")
                continue
            target = None
        elif decision.decision == CONFIRMED:
            # Confirming means the resolver was right, so its answer stands
            # unless the file deliberately names a different one.
            target = decision.canonical_id or match.canonical_university_id
        else:
            if decision.canonical_id is None:
                problems.append(f"{where}: a remap must name a canonical university")
                continue
            target = decision.canonical_id

        if target is not None and not canonical_exists(conn, target):
            problems.append(f"{where}: no canonical university with id {target}")
            continue

        resolved.append((decision, match, target))

    return resolved, problems


def preview(resolved: list[tuple[Decision, Pending, Optional[int]]], conn: Any) -> None:
    names: dict[int, str] = {}
    targets = {target for _, _, target in resolved if target is not None}
    if targets:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT canonical_university_id, display_name
                FROM warehouse.canonical_university
                WHERE canonical_university_id = ANY(%s)
                """,
                (sorted(targets),),
            )
            names = {int(a): str(b) for a, b in cur.fetchall()}

    for decision, match, target in resolved:
        print(f"  [{match.source_code}] {match.source_name}")
        if decision.decision == REJECTED:
            print(f"      reject   was -> {match.canonical_name} (id={match.canonical_university_id})")
        elif target == match.canonical_university_id:
            print(f"      confirm  -> {match.canonical_name} (id={target})")
        else:
            print(f"      remap    {match.canonical_name} -> {names.get(target, '?')} (id={target})")
        if decision.note:
            print(f"      note     {decision.note}")


def write(
    conn: Any,
    resolved: list[tuple[Decision, Pending, Optional[int]]],
    *,
    decided_by: str,
) -> int:
    """Store the batch in one transaction.

    reviewed_* is copied from the live mapping row inside the statement rather
    than taken from the file, so the recorded evidence always describes what
    the resolver actually produced.

    ranking_source_id is filled in by a LEFT JOIN rather than carried from the
    file. It is a legacy column kept for one release so the source_code
    migration stays revertible; a non-ranking source has no id to record and
    correctly leaves it NULL.
    """
    written = 0
    with conn.cursor() as cur:
        for decision, match, target in resolved:
            cur.execute(
                """
                INSERT INTO warehouse.mapping_review (
                    source_code, ranking_source_id, source_entity_id,
                    reviewed_source_name,
                    reviewed_canonical_university_id, reviewed_match_method,
                    reviewed_confidence_score, decision,
                    decided_canonical_university_id, decided_by, note
                )
                SELECT
                    m.source_code,
                    rs.ranking_source_id,
                    m.source_entity_id,
                    COALESCE(
                        m.metadata #>> '{raw_row,name}',
                        m.metadata ->> 'normalized_name',
                        m.source_entity_id
                    ),
                    m.canonical_university_id,
                    m.match_method,
                    m.confidence_score,
                    %s, %s, %s, %s
                FROM warehouse.v_entity_mapping m
                LEFT JOIN warehouse.ranking_source rs
                    ON rs.source_code = m.source_code
                WHERE m.source_code = %s AND m.source_entity_id = %s
                ON CONFLICT (source_code, source_entity_id)
                DO UPDATE SET
                    decision = EXCLUDED.decision,
                    decided_canonical_university_id = EXCLUDED.decided_canonical_university_id,
                    decided_by = EXCLUDED.decided_by,
                    decided_at = CURRENT_TIMESTAMP,
                    note = EXCLUDED.note
                """,
                (
                    decision.decision,
                    target,
                    decided_by,
                    decision.note,
                    match.source_code,
                    match.source_entity_id,
                ),
            )
            written += cur.rowcount
    conn.commit()
    return written


def remaining(conn: Any) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM warehouse.v_entity_mapping m
            LEFT JOIN warehouse.mapping_review r
                ON r.source_code = m.source_code
               AND r.source_entity_id = m.source_entity_id
            WHERE m.is_active
              AND m.match_method IN ('fuzzy', 'fuzzy_review')
              AND r.mapping_review_id IS NULL
            """
        )
        return int(cur.fetchone()[0] or 0)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a batch of entity-resolution decisions.",
    )
    parser.add_argument("decisions", help="CSV of source_entity_id, decision, canonical_id, note")
    parser.add_argument(
        "--decided-by",
        required=True,
        help="who is making these calls; recorded verbatim, so name a person or a rule",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="actually write. Without it this previews and changes nothing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace decisions that already exist for these mappings",
    )
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

    decisions = parse_decisions(Path(args.decisions))

    conn = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )
    try:
        pending = load_pending(conn)
        resolved, problems = resolve(conn, decisions, pending, overwrite=args.overwrite)

        if problems:
            print(f"{len(problems)} problem(s); nothing written:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1

        print(f"{len(resolved)} decision(s):")
        preview(resolved, conn)

        if not args.commit:
            print()
            print("Preview only. Nothing was written. Re-run with --commit to apply.")
            return 0

        written = write(conn, resolved, decided_by=args.decided_by)
        left = remaining(conn)
        print()
        print(f"Wrote {written} decision(s) as {args.decided_by!r}. {left} mapping(s) still undecided.")
        print("Nothing has changed in the warehouse yet: the pipeline applies these")
        print("on the next ingest, and retires rejected mappings then.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
