from __future__ import annotations

"""
Keeping a source entity on the university it is already mapped to.

warehouse.source_university_mapping holds one row per (source, entity id), but
the resolver decides each batch afresh by name. A source that prints one entity
under two names used to flip that row between two canonical universities:
QS calls /universities/istanbul-bilgi-university "İstanbul Bilgi University" in
its world, Asia and sustainability tables and "Istanbul Bilgi Üniversitesi" in
its MBA table, and a duplicate canonical matched each spelling. Every ingest
overwrote the mapping, so which university the entity meant depended on which
table was crawled last -- and the MBA rank ended up on a different university
from the world rank, with nothing flagging it.

The rule here: the id a source assigns is stronger evidence than the name it
prints. An entity with an active mapping keeps that mapping's university, and a
resolver that disagrees is recorded in metadata and logged, never applied.
Moving an entity to another university is a human decision, filed in
warehouse.mapping_review as a remap, which apply_mapping_reviews honours ahead
of this.

Within one batch the same rule holds without a stored mapping to lean on: rows
for one entity that resolved to different universities are put on one of them,
so a single ingest cannot split an entity either.
"""

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional, TypeVar

from .reviews import METHOD_BY_DECISION

logger = logging.getLogger("MultiSourceRankingPipeline")

ResolvedRow = TypeVar("ResolvedRow")

#: Matching methods that carry a person's decision. The continuity rule never
#: overrides these: a remap exists precisely to move an entity.
HUMAN_METHODS = frozenset(METHOD_BY_DECISION.values())


@dataclass(frozen=True)
class ExistingMapping:
    canonical_university_id: int
    match_method: Optional[str] = None
    confidence_score: Optional[float] = None


@dataclass(frozen=True)
class MappingConflict:
    source_code: str
    source_entity_id: str
    kept_canonical_university_id: int
    resolver_canonical_university_id: Optional[int]
    resolver_method: Optional[str]
    printed_name: Optional[str]
    reason: str  # "existing_mapping" or "split_within_batch"


@dataclass(frozen=True)
class MappingContinuityApplication:
    rows_held: int = 0
    conflicts: tuple[MappingConflict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "rows_held": self.rows_held,
            "entities_held": len(self.conflicts),
            "held": [
                {
                    "source": c.source_code,
                    "source_entity_id": c.source_entity_id,
                    "kept_canonical_university_id": c.kept_canonical_university_id,
                    "resolver_canonical_university_id": c.resolver_canonical_university_id,
                    "reason": c.reason,
                }
                for c in self.conflicts[:20]
            ],
        }


class MappingReassignmentError(RuntimeError):
    """A write would move an active mapping to another university without a human decision."""

    def __init__(self, reassignments: list[tuple[str, str, int, int, Optional[str]]]):
        self.reassignments = reassignments
        sample = "\n".join(
            f"  {source} {entity_id}: mapped to {current}, write says {proposed} ({method})"
            for source, entity_id, current, proposed, method in reassignments[:10]
        )
        more = f"\n  ... and {len(reassignments) - 10} more" if len(reassignments) > 10 else ""
        super().__init__(
            f"Refusing to reassign {len(reassignments)} active source mapping(s) to a different "
            "canonical university. A source entity changes university only through a remap in "
            "warehouse.mapping_review; run the batch through apply_mapping_continuity, or file "
            "the remap. No mapping row was written.\n" + sample + more
        )


def _ranking_source_of(row: Any) -> str:
    return row.source


def find_reassignments(
    unified_rows: list[Any],
    existing: dict[tuple[str, str], ExistingMapping],
    *,
    source_of: Callable[[Any], str] = _ranking_source_of,
) -> list[tuple[str, str, int, int, Optional[str]]]:
    """(source, entity id, current, proposed, method) for every silent canonical change.

    ``source_of`` reads the source code off a row: ranking records spell it
    ``source``, entity_resolution's ResolutionResult ``source_name``.
    """
    found: dict[tuple[str, str], tuple[str, str, int, int, Optional[str]]] = {}
    for row in unified_rows:
        if row.canonical_university_id is None or row.matching_method in HUMAN_METHODS:
            continue
        key = (source_of(row), str(row.source_entity_id))
        mapping = existing.get(key)
        if mapping is not None and int(mapping.canonical_university_id) != int(row.canonical_university_id):
            found.setdefault(
                key,
                (key[0], key[1], int(mapping.canonical_university_id), int(row.canonical_university_id), row.matching_method),
            )
    return [found[key] for key in sorted(found)]


def _continuity_metadata(row: Any, conflict: MappingConflict) -> dict[str, object]:
    metadata = dict(row.metadata or {})
    metadata["mapping_continuity"] = {
        "reason": conflict.reason,
        "kept_canonical_university_id": conflict.kept_canonical_university_id,
        "resolver_canonical_university_id": row.canonical_university_id,
        "resolver_method": row.matching_method,
        "resolver_confidence": row.confidence_score,
        "resolver_matched_alias": row.matched_alias,
        "note": "The resolver disagreed with this entity's mapping and was not applied. "
        "File a remap in warehouse.mapping_review if it is right.",
    }
    return metadata


def _hold(row: Any, keep: int, conflict: MappingConflict, existing: Optional[ExistingMapping]) -> Any:
    return replace(
        row,
        canonical_university_id=keep,
        matched_alias=None,
        matching_method=(existing.match_method if existing and existing.match_method else row.matching_method),
        confidence_score=(
            existing.confidence_score if existing and existing.confidence_score is not None else row.confidence_score
        ),
        metadata=_continuity_metadata(row, conflict),
    )


def _batch_choice(rows: list[Any]) -> int:
    """One university for an entity the batch split: best-supported, then most confident."""
    tally: dict[int, tuple[int, float]] = {}
    for row in rows:
        cid = int(row.canonical_university_id)
        count, best = tally.get(cid, (0, 0.0))
        tally[cid] = (count + 1, max(best, float(row.confidence_score or 0.0)))
    return min(tally, key=lambda cid: (-tally[cid][0], -tally[cid][1], cid))


def apply_mapping_continuity(
    unified_rows: list[ResolvedRow],
    existing: dict[tuple[str, str], ExistingMapping],
    *,
    source_of: Callable[[Any], str] = _ranking_source_of,
) -> tuple[list[ResolvedRow], MappingContinuityApplication]:
    """
    Hold every row whose entity is already mapped on that mapping's university.

    ``existing`` is the active mappings for this batch's entities, keyed by
    (source_code, source_entity_id). Rows carrying a human decision pass through
    untouched. A row the resolver left unresolved is held too: an entity that
    was matched last run and not this run has not stopped being that university.

    Serves the admission resolver as well as the ranking pipeline; ``source_of``
    is how it reads the source code off either row type.
    """
    groups: dict[tuple[str, str], list[int]] = {}
    for index, row in enumerate(unified_rows):
        if row.matching_method in HUMAN_METHODS or not row.source_entity_id:
            continue
        groups.setdefault((source_of(row), str(row.source_entity_id)), []).append(index)

    out = list(unified_rows)
    conflicts: list[MappingConflict] = []
    rows_held = 0
    for key, indexes in groups.items():
        mapping = existing.get(key)
        if mapping is not None:
            keep, reason = int(mapping.canonical_university_id), "existing_mapping"
        else:
            resolved = [unified_rows[i] for i in indexes if unified_rows[i].canonical_university_id is not None]
            if len({int(r.canonical_university_id) for r in resolved}) < 2:
                continue
            keep, reason = _batch_choice(resolved), "split_within_batch"

        disagreeing = [i for i in indexes if unified_rows[i].canonical_university_id != keep]
        if not disagreeing:
            continue
        first = unified_rows[disagreeing[0]]
        conflict = MappingConflict(
            source_code=key[0],
            source_entity_id=key[1],
            kept_canonical_university_id=keep,
            resolver_canonical_university_id=first.canonical_university_id,
            resolver_method=first.matching_method,
            printed_name=getattr(first, "university_name", None),
            reason=reason,
        )
        conflicts.append(conflict)
        for i in disagreeing:
            out[i] = _hold(unified_rows[i], keep, conflict, mapping)
            rows_held += 1

    conflicts.sort(key=lambda c: (c.source_code, c.source_entity_id))
    return out, MappingContinuityApplication(rows_held=rows_held, conflicts=tuple(conflicts))
