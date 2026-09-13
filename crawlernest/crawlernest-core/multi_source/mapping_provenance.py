"""Which source mapping produced each warehouse.ranking_record row.

``ranking_record.source_mapping_id`` answers "which source entity, resolved how,
is this rank credited through". It was NULL on every row: the writer never set
it. ``MultiSourceRepository.upsert_ranking_records`` now does, from the exact
entity it is writing. This module fills in the rows written before that, and it
has to work from what a row still carries -- because ranking_record is unique
per (university, source, year, universe), and when two source entities resolve
to one university the row keeps whichever was written last without saying
which.

A row is linked only on evidence, in this order:

``source_entity``
    The row names its entity. QS writes the profile path as both
    ``source_entity_id`` and ``source_url``, so ``source_url`` equal to a
    mapping's entity id, under the same source, is an exact identification --
    including for the universities that two QS entities resolve to (the
    Tsinghua main page and its School of Economics and Management), which a
    join on university alone cannot separate. Checked on the 2026 data: 292 of
    292 such rows are settled this way, and the printed name agrees on all 292.

``sole_mapping_name_agrees``
    The row does not name an entity (ARWU's ``source_url`` is the ranking page,
    THE's is not its id), exactly one active mapping of that source resolves to
    the row's university, and the normalized name on the row equals the one on
    the mapping. The name is required, not decorative: a mapping can be
    re-pointed by a later run while an older row still stands, and "the only
    mapping to this university" would then name the wrong entity.

Everything else stays NULL, with the reason recorded by :func:`classify`:

``conflict_entity_resolves_elsewhere``
    The row names an entity whose mapping now points at a different university.
    The row and the mapping disagree about what this rank belongs to; linking
    them would hide that. (One QS row in 2026: a later universe run re-resolved
    the same profile path.)
``conflict_entity_inactive``
    The named entity's mapping was retired by a reviewer's rejection.
``unresolved_sole_mapping_name_differs``, ``unresolved_ambiguous``,
``unresolved_no_mapping``
    Not enough evidence. NULL here means "not known", never "no mapping".

A value already set is never overwritten: the writer sets it from the entity it
actually wrote, which is better evidence than anything recoverable afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

LINKED_BASES = ("source_entity", "sole_mapping_name_agrees")

#: One row per ranking_record in scope: how it would be linked, and to what.
#: ``%(years)s`` is an int[] or NULL for every year.
_CLASSIFIED = """
WITH scope AS (
    SELECT rr.ranking_record_id,
           rr.ranking_source_id,
           rr.canonical_university_id,
           rr.source_url,
           rr.metadata ->> 'normalized_name' AS row_name,
           rr.source_mapping_id              AS current_mapping_id
    FROM warehouse.ranking_record rr
    WHERE %(years)s::int[] IS NULL OR rr.ranking_year = ANY(%(years)s::int[])
),
named_entity AS (
    -- UNIQUE (ranking_source_id, source_entity_id) makes this at most one row.
    SELECT s.ranking_record_id,
           m.source_mapping_id,
           m.canonical_university_id AS mapping_canonical_id,
           m.is_active
    FROM scope s
    JOIN warehouse.source_university_mapping m
      ON m.ranking_source_id = s.ranking_source_id
     AND m.source_entity_id = s.source_url
),
active_for_university AS (
    SELECT s.ranking_record_id,
           count(*)                AS n,
           min(m.source_mapping_id) AS only_mapping_id,
           bool_and(m.metadata ->> 'normalized_name' = s.row_name) AS name_agrees
    FROM scope s
    JOIN warehouse.source_university_mapping m
      ON m.ranking_source_id = s.ranking_source_id
     AND m.canonical_university_id = s.canonical_university_id
     AND m.is_active
    GROUP BY s.ranking_record_id
)
SELECT s.ranking_record_id,
       s.ranking_source_id,
       s.current_mapping_id,
       CASE
           WHEN e.source_mapping_id IS NOT NULL
                AND e.mapping_canonical_id = s.canonical_university_id
                AND e.is_active                          THEN 'source_entity'
           WHEN e.source_mapping_id IS NOT NULL
                AND e.mapping_canonical_id <> s.canonical_university_id
                                                         THEN 'conflict_entity_resolves_elsewhere'
           WHEN e.source_mapping_id IS NOT NULL          THEN 'conflict_entity_inactive'
           WHEN a.n = 1 AND a.name_agrees                THEN 'sole_mapping_name_agrees'
           WHEN a.n = 1                                  THEN 'unresolved_sole_mapping_name_differs'
           WHEN a.n > 1                                  THEN 'unresolved_ambiguous'
           ELSE                                               'unresolved_no_mapping'
       END AS basis,
       CASE
           WHEN e.source_mapping_id IS NOT NULL
                AND e.mapping_canonical_id = s.canonical_university_id
                AND e.is_active                          THEN e.source_mapping_id
           WHEN e.source_mapping_id IS NULL
                AND a.n = 1 AND a.name_agrees            THEN a.only_mapping_id
       END AS resolved_mapping_id
FROM scope s
LEFT JOIN named_entity e USING (ranking_record_id)
LEFT JOIN active_for_university a USING (ranking_record_id)
"""


@dataclass(frozen=True)
class BasisCount:
    source_code: str
    basis: str
    records: int
    already_set: int
    to_fill: int
    disagrees_with_current: int


def classify(conn: Any, years: Optional[Sequence[int]] = None) -> list[BasisCount]:
    """How every row in scope would be linked. Reads only."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH c AS ({_CLASSIFIED})
            SELECT rs.source_code,
                   c.basis,
                   count(*),
                   count(*) FILTER (WHERE c.current_mapping_id IS NOT NULL),
                   count(*) FILTER (WHERE c.current_mapping_id IS NULL AND c.resolved_mapping_id IS NOT NULL),
                   count(*) FILTER (WHERE c.current_mapping_id IS NOT NULL
                                      AND c.resolved_mapping_id IS NOT NULL
                                      AND c.current_mapping_id <> c.resolved_mapping_id)
            FROM c
            JOIN warehouse.ranking_source rs ON rs.ranking_source_id = c.ranking_source_id
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            {"years": list(years) if years else None},
        )
        return [BasisCount(str(a), str(b), int(c), int(d), int(e), int(f)) for a, b, c, d, e, f in cur.fetchall()]


def conflicts(conn: Any, years: Optional[Sequence[int]] = None, limit: int = 20) -> list[tuple[Any, ...]]:
    """The rows left NULL because the row and its named entity disagree, for a person to look at."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH c AS ({_CLASSIFIED})
            SELECT rs.source_code, rr.ranking_record_id, rr.ranking_year,
                   rr.universe_type || ':' || rr.universe_key,
                   cu.display_name, rr.source_url, c.basis, m.canonical_university_id, mcu.display_name
            FROM c
            JOIN warehouse.ranking_record rr ON rr.ranking_record_id = c.ranking_record_id
            JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
            JOIN warehouse.canonical_university cu ON cu.canonical_university_id = rr.canonical_university_id
            LEFT JOIN warehouse.source_university_mapping m
              ON m.ranking_source_id = rr.ranking_source_id AND m.source_entity_id = rr.source_url
            LEFT JOIN warehouse.canonical_university mcu ON mcu.canonical_university_id = m.canonical_university_id
            WHERE c.basis LIKE 'conflict%%'
            ORDER BY 1, 2
            LIMIT %(limit)s
            """,
            {"years": list(years) if years else None, "limit": limit},
        )
        return cur.fetchall()


def backfill(conn: Any, years: Optional[Sequence[int]] = None) -> int:
    """Link every NULL row that has evidence, in one transaction. Returns rows filled.

    ``updated_at`` is left alone: it records when the source's data last
    changed, and verify_ranking_year.sql reads it to find stale rows. Filling in
    provenance changes neither.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH c AS ({_CLASSIFIED})
                UPDATE warehouse.ranking_record rr
                SET source_mapping_id = c.resolved_mapping_id
                FROM c
                WHERE rr.ranking_record_id = c.ranking_record_id
                  AND rr.source_mapping_id IS NULL
                  AND c.resolved_mapping_id IS NOT NULL
                """,
                {"years": list(years) if years else None},
            )
            filled = int(cur.rowcount or 0)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return filled
