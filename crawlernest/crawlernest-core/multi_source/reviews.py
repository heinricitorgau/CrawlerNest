from __future__ import annotations

"""
Applying human decisions about fuzzy matches to a batch of unified rows.

The resolver's fuzzy stages are a hypothesis. Sampling the fuzzy_review band
against real THE/ARWU data found most of it wrong -- "NOVA University of
Lisbon" credited to "University of Lisbon", "Nagoya City University" to
"Nagoya University" -- so these matches need a person, and the person's answer
has to outrank the resolver on every subsequent run.

This module holds the rule; warehouse.mapping_review holds the decisions, and
MultiSourceRankingPipeline.ingest_records applies them before either upsert.

A decision is keyed by the exact source_entity_id it was made against, so it
only holds while the source keeps that id. When the id changes -- ARWU's used
to embed the year, and its HTML fallback emits a profile URL instead -- the
decision stops matching and the resolver re-decides the entity from scratch.
For a rejection that means re-crediting the very false match a person threw
out. :func:`refuse_reappeared_reviews` is what stops that being silent.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional, TypeVar

from .types import UnifiedRankingRecord

#: Any frozen record carrying the fields a decision overwrites:
#: canonical_university_id, matched_alias, confidence_score, matching_method
#: and metadata. UnifiedRankingRecord is one; entity_resolution's
#: ResolutionResult, which the admission pipeline resolves into, is another.
ResolvedRow = TypeVar("ResolvedRow")

CONFIRMED = "confirmed"
REJECTED = "rejected"
REMAPPED = "remapped"

VALID_DECISIONS = frozenset({CONFIRMED, REJECTED, REMAPPED})

METHOD_BY_DECISION = {
    CONFIRMED: "human_confirmed",
    REJECTED: "human_rejected",
    REMAPPED: "human_remapped",
}

# A remap is asserted, not measured: the resolver's similarity score described a
# match to a different university and says nothing about this one. 1.0 records
# "a person stated this", which `human_remapped` makes unambiguous. Confidence
# *levels* remain derived from source count and are untouched by any of this.
REMAPPED_CONFIDENCE = 1.0
REJECTED_CONFIDENCE = 0.0


@dataclass(frozen=True)
class MappingReview:
    source_code: str
    source_entity_id: str
    decision: str
    decided_canonical_university_id: Optional[int] = None
    decided_by: str = "unknown"
    note: Optional[str] = None
    #: The name the reviewer was shown, from mapping_review.reviewed_source_name.
    #: Only read to recognise the entity again if its id changes.
    reviewed_source_name: Optional[str] = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_code, self.source_entity_id)


@dataclass(frozen=True)
class MappingReviewApplication:
    rows_considered: int = 0
    confirmed: int = 0
    rejected: int = 0
    remapped: int = 0
    invalid: int = 0
    # Decisions with no matching row in this payload: usually a source that
    # dropped the entity, occasionally a stale decision worth revisiting.
    unapplied_reviews: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    # Entities a reviewer threw out. The mapping upsert skips them, which would
    # otherwise leave the old row asserting the rejected match forever.
    rejected_keys: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def applied(self) -> int:
        return self.confirmed + self.rejected + self.remapped

    def to_dict(self) -> dict[str, object]:
        return {
            "rows_considered": self.rows_considered,
            "applied": self.applied,
            "confirmed": self.confirmed,
            "rejected": self.rejected,
            "remapped": self.remapped,
            "invalid": self.invalid,
            "unapplied_review_count": len(self.unapplied_reviews),
        }


def _ranking_source_of(row: Any) -> str:
    """Where a ranking record carries its source code."""
    return row.source


def _audit_metadata(row: Any, review: MappingReview) -> dict[str, object]:
    metadata = dict(row.metadata or {})
    metadata["human_review"] = {
        "decision": review.decision,
        "decided_by": review.decided_by,
        "note": review.note,
        "superseded_method": row.matching_method,
        "superseded_confidence": row.confidence_score,
        "superseded_canonical_university_id": row.canonical_university_id,
    }
    return metadata


def apply_mapping_reviews(
    unified_rows: list[ResolvedRow],
    reviews: dict[tuple[str, str], MappingReview],
    *,
    source_of: Callable[[Any], str] = _ranking_source_of,
) -> tuple[list[ResolvedRow], MappingReviewApplication]:
    """
    Overlay standing human decisions on a batch of resolved rows.

    A rejected row comes back with canonical_university_id=None, which drops it
    into the existing unresolved path: it is logged to missing_entity_log and no
    warehouse.ranking_record is written for it. That is the whole mechanism for
    withdrawing a wrong source credit -- no delete, no separate cleanup.

    Rows without a decision are returned untouched.

    ``source_of`` reads the source code off a row. It exists because the
    admission pipeline resolves into entity_resolution's ResolutionResult,
    which spells that field ``source_name`` rather than ``source``. The rule
    itself does not vary by source: a reviewer deciding whether a name is a
    given university is answering the same question either way, and two
    implementations of that rule would eventually disagree.
    """
    if not reviews:
        return list(unified_rows), MappingReviewApplication(rows_considered=len(unified_rows))

    out: list[ResolvedRow] = []
    seen_keys: set[tuple[str, str]] = set()
    rejected_keys: list[tuple[str, str]] = []
    confirmed = rejected = remapped = invalid = 0

    for row in unified_rows:
        review = reviews.get((source_of(row), row.source_entity_id))
        if review is None:
            out.append(row)
            continue

        seen_keys.add(review.key)

        if review.decision not in VALID_DECISIONS:
            invalid += 1
            out.append(row)
            continue

        if review.decision == REJECTED:
            rejected += 1
            rejected_keys.append(review.key)
            out.append(
                replace(
                    row,
                    canonical_university_id=None,
                    matched_alias=None,
                    confidence_score=REJECTED_CONFIDENCE,
                    matching_method=METHOD_BY_DECISION[REJECTED],
                    metadata=_audit_metadata(row, review),
                )
            )
            continue

        if review.decided_canonical_university_id is None:
            # The table's CHECK constraint forbids this, but a hand-written row
            # or a future migration could still produce it. Refusing to guess
            # leaves the resolver's answer in place rather than silently
            # dropping the record.
            invalid += 1
            out.append(row)
            continue

        if review.decision == CONFIRMED:
            confirmed += 1
            out.append(
                replace(
                    row,
                    canonical_university_id=review.decided_canonical_university_id,
                    matching_method=METHOD_BY_DECISION[CONFIRMED],
                    metadata=_audit_metadata(row, review),
                )
            )
            continue

        remapped += 1
        out.append(
            replace(
                row,
                canonical_university_id=review.decided_canonical_university_id,
                matched_alias=None,
                confidence_score=REMAPPED_CONFIDENCE,
                matching_method=METHOD_BY_DECISION[REMAPPED],
                metadata=_audit_metadata(row, review),
            )
        )

    unapplied = tuple(sorted(key for key in reviews if key not in seen_keys))
    return out, MappingReviewApplication(
        rows_considered=len(unified_rows),
        confirmed=confirmed,
        rejected=rejected,
        remapped=remapped,
        invalid=invalid,
        unapplied_reviews=unapplied,
        rejected_keys=tuple(rejected_keys),
    )


# ---------------------------------------------------------------------------
# A decision whose entity came back under another id
# ---------------------------------------------------------------------------
#
# An unapplied review is usually harmless: a partial run (--limit), a QS
# universe that does not contain that university, or a source that dropped it.
# Nothing is written for an entity that is not in the batch, so nothing is
# misattributed. Refusing on every unapplied review would block all of those,
# and a guard that blocks routine runs gets bypassed.
#
# The harmful case is narrower and detectable: the entity *is* in the batch,
# under a different source_entity_id. Then the decision is skipped and the
# resolver's fuzzy answer is written in its place. That is refused outright --
# no threshold, no override -- because the only correct fix is to re-key the
# decision to the new id, never to ingest past it.
#
# "The same entity" is judged on two readable handles, compared in slug form:
# the name the source printed, and the last segment of the id
# ("arwu:2026:ruhr-university-bochum", "/universities/ruhr-university-bochum").
# A match on either is enough. Both are exact comparisons, so a false positive
# needs two different institutions with the same name in one source -- and
# when that happens the run stops and names the pair, which is the safe way to
# be wrong.

_SLUG_JUNK = re.compile(r"[^a-z0-9]+")


def _slug(value: Optional[str]) -> Optional[str]:
    slug = _SLUG_JUNK.sub("-", str(value or "").strip().lower()).strip("-")
    return slug or None


def _id_tail(source_entity_id: Optional[str]) -> Optional[str]:
    text = str(source_entity_id or "").strip().rstrip("/")
    return _slug(re.split(r"[:/]", text)[-1]) if text else None


def _handles(*values: Optional[str]) -> frozenset[str]:
    return frozenset(v for v in values if v)


@dataclass(frozen=True)
class ReappearedReview:
    """A standing decision that did not apply although its entity is in the batch."""

    source_code: str
    reviewed_source_entity_id: str
    decision: str
    batch_source_entity_id: str
    batch_name: str
    matched_on: str  # "name" or "id"


class UnappliedReviewError(RuntimeError):
    """Raised before any warehouse write when a decision would be silently lost."""

    def __init__(self, reappeared: tuple[ReappearedReview, ...]):
        self.reappeared = reappeared
        rejected = sum(1 for r in reappeared if r.decision == REJECTED)
        sources = ", ".join(sorted({r.source_code for r in reappeared}))
        sample = "\n".join(
            f"  {r.source_code} {r.reviewed_source_entity_id} ({r.decision}) is in this batch as "
            f"{r.batch_source_entity_id} [{r.batch_name}], matched on {r.matched_on}"
            for r in reappeared[:10]
        )
        more = f"\n  ... and {len(reappeared) - 10} more" if len(reappeared) > 10 else ""
        super().__init__(
            f"Refusing to ingest {sources}: {len(reappeared)} standing mapping review(s) did not "
            f"apply, but the entities they decide are in this batch under a different "
            f"source_entity_id. Writing now would let the resolver re-decide them"
            + (f", re-crediting {rejected} match(es) a reviewer rejected" if rejected else "")
            + ". Re-key the decisions to the new ids first (for ARWU: "
            "crawlernest/scripts/rekey_arwu_source_ids.py). No mapping or ranking row was written.\n"
            + sample
            + more
        )


def find_reappeared_reviews(
    reviews: dict[tuple[str, str], MappingReview],
    unapplied_keys: Iterable[tuple[str, str]],
    batch: Iterable[tuple[str, str, Optional[str]]],
) -> tuple[ReappearedReview, ...]:
    """Unapplied decisions whose entity is present in ``batch`` under another id.

    ``batch`` is ``(source_code, source_entity_id, printed_name)`` per input row.
    Only compared within one source: a THE row never revives an ARWU decision.
    """
    unapplied = [reviews[key] for key in unapplied_keys if key in reviews]
    if not unapplied:
        return ()

    by_handle: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for source_code, entity_id, name in batch:
        source_code = str(source_code or "").strip().upper()
        entity_id = str(entity_id or "").strip()
        name_slug, tail = _slug(name), _id_tail(entity_id)
        for handle, kind in ((name_slug, "name"), (tail, "id")):
            if handle:
                by_handle.setdefault((source_code, handle), []).append(
                    (entity_id, str(name or ""), kind)
                )

    found: list[ReappearedReview] = []
    for review in sorted(unapplied, key=lambda r: r.key):
        source_code = review.source_code.upper()
        handles = _handles(_slug(review.reviewed_source_name), _id_tail(review.source_entity_id))
        hit = next(
            (
                match
                for handle in sorted(handles)
                for match in by_handle.get((source_code, handle), ())
                if match[0] != review.source_entity_id
            ),
            None,
        )
        if hit is not None:
            found.append(
                ReappearedReview(
                    source_code=review.source_code,
                    reviewed_source_entity_id=review.source_entity_id,
                    decision=review.decision,
                    batch_source_entity_id=hit[0],
                    batch_name=hit[1],
                    matched_on=hit[2],
                )
            )
    return tuple(found)


def refuse_reappeared_reviews(
    reviews: dict[tuple[str, str], MappingReview],
    application: MappingReviewApplication,
    batch: Iterable[tuple[str, str, Optional[str]]],
) -> None:
    """Raise :class:`UnappliedReviewError` if any decision's entity came back under a new id."""
    reappeared = find_reappeared_reviews(reviews, application.unapplied_reviews, batch)
    if reappeared:
        raise UnappliedReviewError(reappeared)
