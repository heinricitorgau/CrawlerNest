"""Structural changes to institutions, and when they make two editions incomparable.

A rank delta compares one canonical university across two editions. Mergers,
splits and renames break that comparison without leaving a trace the pipeline
can see: the 2026 editions rank "Institute of Science Tokyo", the entity
resolver attached those rows to the existing Tokyo Tech record, and ARWU kept
its old institution slug -- so a 2025-to-2026 delta on that record would pass
every identity check :mod:`crawlernest.core.rank_delta` has and compare Tokyo
Tech with an institution formed by merging it with TMDU.

``warehouse.institution_lineage`` records those events; the DDL and the two
seeded mergers are in ``crawlernest-schema/institution_lineage_postgresql.sql``.
This module holds the rule for reading them, which ``clawer.service.
InstitutionLineage`` mirrors in Java:

    A university is on a lineage boundary for a comparison of ``prior_year``
    with ``current_year`` when an event names it -- as predecessor or successor
    -- and the event's effective year lies in
    ``[prior_year - EDITION_LAG_YEARS, current_year]``.

``effective_year`` is the calendar year the change took effect. Edition labels
run ahead of publication (QS and THE name an edition a year after they publish
it), so the window reaches one year further back than the prior edition's
label. Institute of Science Tokyo (effective 2024-10-01) therefore withholds
2025-to-2026, whose 2025 editions were published before the merger, and nothing
after it. Adelaide University (effective 2026-01-01) withholds 2026-to-2027 and
2027-to-2028: a year cannot say whether an event fell before or after an edition
went to press, so the rule treats it as possibly after, and the second of those
comparisons -- in fact sound -- is withheld too. Withholding a sound comparison
is the safe error; reporting movement across a merger is not.

Nothing here decides how to phrase the result: :func:`lineage_boundary` returns
the event, and ``rank_delta`` turns it into ``REASON_ENTITY_CHANGED``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "EDITION_LAG_YEARS",
    "KINDS",
    "LineageEvent",
    "fetch_lineage",
    "lineage_boundary",
]

KINDS = frozenset({"merger", "split", "rename"})

#: How far an edition label can run ahead of the institutional state it describes.
EDITION_LAG_YEARS = 1


@dataclass(frozen=True, slots=True)
class LineageEvent:
    """One row of ``warehouse.institution_lineage``.

    ``predecessor_canonical_id`` may equal ``successor_canonical_id``: the
    warehouse holds a record per resolved name, not per legal entity, so a merger
    whose absorbed institution was never ingested, or a rename, has only one
    record to name.
    """

    predecessor_canonical_id: int
    successor_canonical_id: int
    effective_year: int
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown lineage kind {self.kind!r}; expected one of {sorted(KINDS)}")

    def involves(self, canonical_university_id: int) -> bool:
        return canonical_university_id in (self.predecessor_canonical_id, self.successor_canonical_id)


def lineage_boundary(
    canonical_university_id: int,
    *,
    prior_year: int,
    current_year: int,
    lineage: Iterable[LineageEvent],
) -> LineageEvent | None:
    """The event separating ``prior_year`` from ``current_year`` for this university, if any."""
    if prior_year >= current_year:
        raise ValueError(f"prior_year {prior_year} must precede current_year {current_year}")
    window_start = prior_year - EDITION_LAG_YEARS
    for event in lineage:
        if event.involves(canonical_university_id) and window_start <= event.effective_year <= current_year:
            return event
    return None


def fetch_lineage(conn: Any, canonical_university_ids: Collection[int] | None = None) -> tuple[LineageEvent, ...]:
    """Events from ``warehouse.institution_lineage``, optionally only those naming these universities.

    Raises if the table is absent rather than returning nothing. An empty lineage
    reads as "no institution ever changed", which would let every comparison
    through; a database missing the table needs the schema applied, not a
    silent pass.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('warehouse.institution_lineage') IS NOT NULL")
        present = cur.fetchone()
        if not present or not present[0]:
            raise RuntimeError(
                "warehouse.institution_lineage is missing; apply "
                "crawlernest-schema/institution_lineage_postgresql.sql before computing rank deltas"
            )
        sql = (
            "SELECT predecessor_canonical_id, successor_canonical_id, effective_year, kind "
            "FROM warehouse.institution_lineage"
        )
        params: tuple[Any, ...] = ()
        if canonical_university_ids is not None:
            ids = sorted({int(i) for i in canonical_university_ids})
            sql += " WHERE predecessor_canonical_id = ANY(%s) OR successor_canonical_id = ANY(%s)"
            params = (ids, ids)
        cur.execute(sql + " ORDER BY effective_year, lineage_id", params)
        rows = cur.fetchall()
    return tuple(LineageEvent(int(p), int(s), int(y), str(k)) for p, s, y, k in rows)
