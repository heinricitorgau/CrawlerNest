"""Tests for human review decisions overriding fuzzy entity resolution.

The decisions live in warehouse.mapping_review; this covers the rule that
applies them, which runs before both upserts in
MultiSourceRankingPipeline.ingest_records.
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

from multi_source.reviews import (  # noqa: E402
    MappingReview,
    apply_mapping_reviews,
)
from multi_source.types import UnifiedRankingRecord  # noqa: E402


def _row(
    *,
    source: str = "THE",
    source_entity_id: str = "846",
    canonical_university_id=101,
    matching_method: str = "fuzzy_review",
    confidence_score: float = 0.8205,
) -> UnifiedRankingRecord:
    return UnifiedRankingRecord(
        canonical_university_id=canonical_university_id,
        source=source,
        source_entity_id=source_entity_id,
        rank=501,
        score=None,
        year=2026,
        ranking_type="world",
        matched_alias="University of Lisbon",
        confidence_score=confidence_score,
        matching_method=matching_method,
        metadata={"normalized_name": "nova university lisbon"},
    )


def _reviews(*reviews: MappingReview) -> dict:
    return {review.key: review for review in reviews}


class TestNoReviews(unittest.TestCase):
    def test_empty_reviews_returns_rows_untouched(self):
        rows = [_row()]
        out, stats = apply_mapping_reviews(rows, {})
        self.assertEqual(rows, out)
        self.assertEqual(0, stats.applied)
        self.assertEqual(1, stats.rows_considered)

    def test_row_without_a_decision_is_untouched(self):
        rows = [_row(source_entity_id="999")]
        out, stats = apply_mapping_reviews(
            rows,
            _reviews(MappingReview("THE", "846", "rejected")),
        )
        self.assertEqual(rows, out)
        self.assertEqual(0, stats.applied)
        self.assertEqual((("THE", "846"),), stats.unapplied_reviews)


class TestRejection(unittest.TestCase):
    """A rejection has to withdraw the source credit, not just flag it."""

    def _rejected(self) -> UnifiedRankingRecord:
        out, _ = apply_mapping_reviews(
            [_row()],
            _reviews(MappingReview("THE", "846", "rejected", decided_by="reviewer")),
        )
        return out[0]

    def test_canonical_id_is_cleared(self):
        # This is the whole mechanism: a None id is skipped by
        # upsert_ranking_records, so no source credit is written.
        self.assertIsNone(self._rejected().canonical_university_id)

    def test_matched_alias_is_cleared(self):
        self.assertIsNone(self._rejected().matched_alias)

    def test_method_records_the_human_decision(self):
        self.assertEqual("human_rejected", self._rejected().matching_method)

    def test_confidence_drops_to_zero(self):
        self.assertEqual(0.0, self._rejected().confidence_score)

    def test_superseded_match_is_kept_for_audit(self):
        audit = self._rejected().metadata["human_review"]
        self.assertEqual("rejected", audit["decision"])
        self.assertEqual("reviewer", audit["decided_by"])
        self.assertEqual("fuzzy_review", audit["superseded_method"])
        self.assertEqual(101, audit["superseded_canonical_university_id"])
        self.assertAlmostEqual(0.8205, audit["superseded_confidence"])

    def test_original_metadata_survives(self):
        self.assertEqual(
            "nova university lisbon", self._rejected().metadata["normalized_name"]
        )

    def test_the_input_row_is_not_mutated(self):
        rows = [_row()]
        apply_mapping_reviews(
            rows, _reviews(MappingReview("THE", "846", "rejected"))
        )
        self.assertEqual(101, rows[0].canonical_university_id)
        self.assertNotIn("human_review", rows[0].metadata)


class TestRemap(unittest.TestCase):
    def _remapped(self) -> UnifiedRankingRecord:
        out, _ = apply_mapping_reviews(
            [_row()],
            _reviews(
                MappingReview("THE", "846", "remapped", 777, decided_by="reviewer")
            ),
        )
        return out[0]

    def test_canonical_id_moves_to_the_reviewed_target(self):
        self.assertEqual(777, self._remapped().canonical_university_id)

    def test_method_records_the_human_decision(self):
        self.assertEqual("human_remapped", self._remapped().matching_method)

    def test_confidence_is_asserted_not_carried_over(self):
        # The old score measured similarity to a different university and says
        # nothing about this one.
        self.assertEqual(1.0, self._remapped().confidence_score)

    def test_stale_alias_is_dropped(self):
        self.assertIsNone(self._remapped().matched_alias)


class TestConfirmation(unittest.TestCase):
    def _confirmed(self) -> UnifiedRankingRecord:
        out, _ = apply_mapping_reviews(
            [_row()],
            _reviews(
                MappingReview("THE", "846", "confirmed", 101, decided_by="reviewer")
            ),
        )
        return out[0]

    def test_canonical_id_is_kept(self):
        self.assertEqual(101, self._confirmed().canonical_university_id)

    def test_method_records_the_human_decision(self):
        self.assertEqual("human_confirmed", self._confirmed().matching_method)

    def test_measured_confidence_is_preserved(self):
        # Unlike a remap, the score still describes this match, so it stays as
        # evidence of what the resolver saw.
        self.assertAlmostEqual(0.8205, self._confirmed().confidence_score)


class TestMalformedDecisions(unittest.TestCase):
    """The table's CHECK constraints forbid these; a migration could not."""

    def test_unknown_decision_leaves_the_row_alone(self):
        out, stats = apply_mapping_reviews(
            [_row()], _reviews(MappingReview("THE", "846", "maybe"))
        )
        self.assertEqual(101, out[0].canonical_university_id)
        self.assertEqual("fuzzy_review", out[0].matching_method)
        self.assertEqual(1, stats.invalid)
        self.assertEqual(0, stats.applied)

    def test_remap_without_a_target_leaves_the_row_alone(self):
        out, stats = apply_mapping_reviews(
            [_row()], _reviews(MappingReview("THE", "846", "remapped", None))
        )
        self.assertEqual(101, out[0].canonical_university_id)
        self.assertEqual(1, stats.invalid)

    def test_confirm_without_a_target_leaves_the_row_alone(self):
        out, stats = apply_mapping_reviews(
            [_row()], _reviews(MappingReview("THE", "846", "confirmed", None))
        )
        self.assertEqual(101, out[0].canonical_university_id)
        self.assertEqual(1, stats.invalid)


class TestScoping(unittest.TestCase):
    def test_a_decision_is_scoped_to_one_source(self):
        # THE and ARWU use different entity id schemes, but a shared id must not
        # let one source's decision leak into the other's.
        rows = [
            _row(source="THE", source_entity_id="846"),
            _row(source="ARWU", source_entity_id="846"),
        ]
        out, stats = apply_mapping_reviews(
            rows, _reviews(MappingReview("THE", "846", "rejected"))
        )
        self.assertIsNone(out[0].canonical_university_id)
        self.assertEqual(101, out[1].canonical_university_id)
        self.assertEqual(1, stats.rejected)

    def test_counts_are_reported_per_decision(self):
        rows = [
            _row(source_entity_id="1"),
            _row(source_entity_id="2"),
            _row(source_entity_id="3"),
            _row(source_entity_id="4"),
        ]
        out, stats = apply_mapping_reviews(
            rows,
            _reviews(
                MappingReview("THE", "1", "confirmed", 101),
                MappingReview("THE", "2", "remapped", 777),
                MappingReview("THE", "3", "rejected"),
                MappingReview("THE", "55", "rejected"),
            ),
        )
        self.assertEqual(4, stats.rows_considered)
        self.assertEqual(1, stats.confirmed)
        self.assertEqual(1, stats.remapped)
        self.assertEqual(1, stats.rejected)
        self.assertEqual(3, stats.applied)
        self.assertEqual((("THE", "55"),), stats.unapplied_reviews)
        self.assertEqual(101, out[3].canonical_university_id)

    def test_summary_dict_is_serialisable(self):
        _, stats = apply_mapping_reviews(
            [_row()], _reviews(MappingReview("THE", "846", "rejected"))
        )
        payload = stats.to_dict()
        self.assertEqual(1, payload["rejected"])
        self.assertEqual(1, payload["applied"])
        self.assertEqual(0, payload["unapplied_review_count"])


if __name__ == "__main__":
    unittest.main()
