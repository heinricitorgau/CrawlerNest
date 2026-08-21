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
"""

from dataclasses import dataclass, field, replace
from typing import Optional

from .types import UnifiedRankingRecord

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


def _audit_metadata(row: UnifiedRankingRecord, review: MappingReview) -> dict[str, object]:
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
    unified_rows: list[UnifiedRankingRecord],
    reviews: dict[tuple[str, str], MappingReview],
) -> tuple[list[UnifiedRankingRecord], MappingReviewApplication]:
    """
    Overlay standing human decisions on a batch of resolved rows.

    A rejected row comes back with canonical_university_id=None, which drops it
    into the existing unresolved path: it is logged to missing_entity_log and no
    warehouse.ranking_record is written for it. That is the whole mechanism for
    withdrawing a wrong source credit -- no delete, no separate cleanup.

    Rows without a decision are returned untouched.
    """
    if not reviews:
        return list(unified_rows), MappingReviewApplication(rows_considered=len(unified_rows))

    out: list[UnifiedRankingRecord] = []
    seen_keys: set[tuple[str, str]] = set()
    rejected_keys: list[tuple[str, str]] = []
    confirmed = rejected = remapped = invalid = 0

    for row in unified_rows:
        review = reviews.get((row.source, row.source_entity_id))
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
