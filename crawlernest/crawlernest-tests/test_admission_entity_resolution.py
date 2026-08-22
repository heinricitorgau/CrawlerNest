"""Tests for admission rows resolving through the shared EntityResolver.

The admission pipeline used to carry an exact-match resolver of its own, which
matched 3 of the 8 checked-in snapshot universities. These cover the pieces of
the replacement that do not need a database: what gets resolved, what a
reviewer is given to judge it by, how the outcome is counted, and that a
standing decision still overrides the resolver now that the row type is
entity_resolution's ResolutionResult rather than a ranking record.
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
REPO_ROOT = PACKAGE_ROOT.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(REPO_ROOT))

from entity_resolution.resolver import EntityResolver  # noqa: E402
from entity_resolution.types import CanonicalProfile, ResolutionResult  # noqa: E402
from multi_source.reviews import MappingReview, apply_mapping_reviews  # noqa: E402

from crawlernest_admission_crawler.entity_resolver import (  # noqa: E402
    SOURCE_CODE,
    _empty_counts,
    _load_admission_rows,
    _resolve_row,
    _tally,
)

PROFILES = [
    CanonicalProfile(
        canonical_university_id=13,
        display_name="The University of Melbourne",
        country_hint="australia",
    ),
    CanonicalProfile(
        canonical_university_id=8,
        display_name="National University of Singapore (NUS)",
        country_hint="singapore",
    ),
    CanonicalProfile(
        canonical_university_id=3,
        display_name="University of Oxford",
        country_hint="united kingdom",
    ),
]


def _resolver() -> EntityResolver:
    return EntityResolver(PROFILES)


def _row(
    *,
    name="University of Melbourne",
    country="Australia",
    source_url="https://study.unimelb.edu.au/admissions/english-language-requirements",
    row_id=1,
):
    return {
        "id": row_id,
        "source_entity_id": "study.unimelb.edu.au/admissions/english-language-requirements",
        "university_name": name,
        "country": country,
        "source_url": source_url,
    }


class FakeCursor:
    """Just enough cursor for _load_admission_rows."""

    def __init__(self, rows):
        self._rows = rows
        self.executed = None

    def execute(self, sql, params=None):
        self.executed = sql

    def fetchall(self):
        return self._rows


class TestResolutionImprovesOnExactMatch(unittest.TestCase):
    def test_a_leading_the_no_longer_blocks_a_match(self):
        # The old exact-match resolver missed this: the source says
        # "University of Melbourne", the canonical row says "The University
        # of Melbourne".
        result = _resolve_row(_resolver(), _row())
        self.assertEqual(13, result.canonical_university_id)
        self.assertEqual("normalized_display", result.matching_method)

    def test_a_parenthetical_suffix_no_longer_blocks_a_match(self):
        result = _resolve_row(_resolver(), _row(name="National University of Singapore"))
        self.assertEqual(8, result.canonical_university_id)

    def test_an_unknown_university_stays_unresolved(self):
        result = _resolve_row(_resolver(), _row(name="Nowhere Polytechnic Institute"))
        self.assertIsNone(result.canonical_university_id)
        self.assertEqual("unresolved", result.matching_method)

    def test_the_source_code_identifies_admission_rows(self):
        self.assertEqual("university_site", SOURCE_CODE)
        self.assertEqual(SOURCE_CODE, _resolve_row(_resolver(), _row()).source_name)


class TestReviewEvidence(unittest.TestCase):
    """The review screen reads raw_row; EntityResolver does not write it."""

    def test_raw_row_carries_the_name_the_reviewer_must_see(self):
        result = _resolve_row(_resolver(), _row())
        self.assertEqual("University of Melbourne", result.metadata["raw_row"]["name"])

    def test_raw_row_carries_the_country(self):
        result = _resolve_row(_resolver(), _row())
        self.assertEqual("Australia", result.metadata["raw_row"]["location"])

    def test_raw_row_carries_the_page_it_came_from(self):
        result = _resolve_row(_resolver(), _row())
        self.assertEqual(
            "https://study.unimelb.edu.au/admissions/english-language-requirements",
            result.metadata["raw_row"]["source_url"],
        )

    def test_resolver_signals_survive_alongside_it(self):
        result = _resolve_row(_resolver(), _row())
        for key in ("normalized_name", "token_overlap", "candidate_count_hint"):
            self.assertIn(key, result.metadata)

    def test_the_resolver_result_is_not_mutated(self):
        resolver = _resolver()
        row = _row()
        first = _resolve_row(resolver, row)
        second = _resolve_row(resolver, row)
        self.assertEqual(first.metadata["raw_row"], second.metadata["raw_row"])


class TestOutcomeCounting(unittest.TestCase):
    def _tallied(self, method, canonical_id=13):
        counts = _empty_counts()
        _tally(
            counts,
            ResolutionResult(
                source_name=SOURCE_CODE,
                source_entity_id="x",
                canonical_university_id=canonical_id,
                matched_alias=None,
                confidence_score=0.9,
                matching_method=method,
                candidate_count=1,
            ),
        )
        return counts

    def test_exact_variants_count_as_exact(self):
        self.assertEqual(1, self._tallied("exact_display")["exact"])

    def test_transliterated_normalized_still_counts_as_normalized(self):
        self.assertEqual(1, self._tallied("normalized_transliterated")["normalized"])

    def test_fuzzy_counts_as_fuzzy(self):
        self.assertEqual(1, self._tallied("fuzzy")["fuzzy"])

    def test_fuzzy_is_also_pending_review(self):
        self.assertEqual(1, self._tallied("fuzzy_review")["review_pending"])

    def test_an_exact_match_is_not_pending_review(self):
        self.assertEqual(0, self._tallied("exact")["review_pending"])

    def test_resolved_is_decided_by_the_canonical_id_not_the_method(self):
        # A human rejection keeps a descriptive method but no target.
        counts = self._tallied("human_rejected", canonical_id=None)
        self.assertEqual(1, counts["unresolved"])
        self.assertEqual(0, counts["resolved"])


class TestStandingDecisionsStillWin(unittest.TestCase):
    """The review rule is shared with the ranking pipeline, not reimplemented."""

    def _result(self, entity_id="unimelb", canonical_id=13):
        return ResolutionResult(
            source_name=SOURCE_CODE,
            source_entity_id=entity_id,
            canonical_university_id=canonical_id,
            matched_alias="The University of Melbourne",
            confidence_score=0.8402,
            matching_method="fuzzy_review",
            candidate_count=9,
            metadata={"raw_row": {"name": "University of Melbourne"}},
        )

    def _apply(self, review):
        return apply_mapping_reviews(
            [self._result()],
            {review.key: review},
            source_of=lambda result: result.source_name,
        )

    def test_a_rejection_clears_the_match(self):
        out, stats = self._apply(
            MappingReview(SOURCE_CODE, "unimelb", "rejected", decided_by="reviewer")
        )
        self.assertIsNone(out[0].canonical_university_id)
        self.assertEqual("human_rejected", out[0].matching_method)
        self.assertEqual(1, stats.rejected)

    def test_a_remap_moves_the_match(self):
        out, stats = self._apply(
            MappingReview(SOURCE_CODE, "unimelb", "remapped", 3, decided_by="reviewer")
        )
        self.assertEqual(3, out[0].canonical_university_id)
        self.assertEqual(1, stats.remapped)

    def test_a_confirmation_keeps_the_match_and_records_who_said_so(self):
        out, stats = self._apply(
            MappingReview(SOURCE_CODE, "unimelb", "confirmed", 13, decided_by="reviewer")
        )
        self.assertEqual(13, out[0].canonical_university_id)
        self.assertEqual("human_confirmed", out[0].matching_method)
        self.assertEqual("reviewer", out[0].metadata["human_review"]["decided_by"])
        self.assertEqual(1, stats.confirmed)

    def test_the_reviewer_evidence_survives_the_override(self):
        out, _ = self._apply(
            MappingReview(SOURCE_CODE, "unimelb", "rejected", decided_by="reviewer")
        )
        self.assertEqual("University of Melbourne", out[0].metadata["raw_row"]["name"])

    def test_a_decision_for_another_source_does_not_apply(self):
        out, stats = self._apply(MappingReview("THE", "unimelb", "rejected", decided_by="reviewer"))
        self.assertEqual(13, out[0].canonical_university_id)
        self.assertEqual(0, stats.applied)


class TestSourceEntityIdFallback(unittest.TestCase):
    def test_a_null_column_is_derived_from_the_url(self):
        # source_entity_id is nullable until it becomes half of the natural
        # key, so a row written before that migration still has to resolve.
        cur = FakeCursor([(7, None, "University of Oxford", "United Kingdom",
                           "https://www.ox.ac.uk/admissions/graduate/")])
        rows = _load_admission_rows(cur, target_schema="warehouse", target_table="admission_record")
        self.assertEqual("www.ox.ac.uk/admissions/graduate", rows[0]["source_entity_id"])

    def test_an_existing_column_is_used_as_is(self):
        cur = FakeCursor([(7, "already.set/path", "University of Oxford", "UK", "https://ignored.example/")])
        rows = _load_admission_rows(cur, target_schema="warehouse", target_table="admission_record")
        self.assertEqual("already.set/path", rows[0]["source_entity_id"])

    def test_a_blank_country_becomes_none(self):
        cur = FakeCursor([(7, "x", "University of Oxford", "   ", "https://example.edu/")])
        rows = _load_admission_rows(cur, target_schema="warehouse", target_table="admission_record")
        self.assertIsNone(rows[0]["country"])


if __name__ == "__main__":
    unittest.main()
