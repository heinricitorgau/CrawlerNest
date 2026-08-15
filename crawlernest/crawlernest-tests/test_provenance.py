"""The provenance/absence/completeness checker.

The point of these tests is not that the checker fires on bad text -- a keyword
list would do that. It is that each check *reads the structured field it claims
to read*. Every positive case is paired with a negative that keeps the wording
identical and flips only the field. A check that fires on both is a phrase
blacklist, which is the failure this layer would be easiest to build by accident:
it would look like coverage, be measured as coverage, and have no relationship to
the evidence.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.provenance import check_provenance
from crawlernest.agent.web_agent.generation.verification import (
    USE_FALLBACK,
    reset_verification_stats,
    verification_stats,
    verify_explanation,
)

_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]


def _check(explanation, items=None, evidence=None, caveats=None):
    return check_provenance(
        explanation=explanation, items=items, evidence=evidence, caveats=caveats
    )


class TestEstimateAttribution(unittest.TestCase):
    """A model estimate must not be handed to the ranking body as its own figure."""

    TEXT = "QS scores it at 20.4 on employer reputation."

    def test_fires_when_the_value_is_flagged_as_an_estimate(self):
        report = _check(self.TEXT, items=[{"employerReputation": 20.4, "isEstimated": True}])
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["estimate_credited_to_source"])

    def test_silent_on_identical_text_when_the_value_is_published(self):
        report = _check(self.TEXT, items=[{"employerReputation": 20.4, "isEstimated": False}])
        self.assertTrue(report.sound)


class TestAbsenceVersusRefusal(unittest.TestCase):
    """A null rank means we did not ingest it, not that the source declined."""

    TEXT = "THE does not rank this university."

    def test_fires_when_the_source_rank_is_null(self):
        report = _check(self.TEXT, items=[{"sourceRanks": {"QS": 68, "THE": None}}])
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["absence_reported_as_refusal"])

    def test_silent_on_identical_text_when_the_source_has_a_rank(self):
        report = _check(self.TEXT, items=[{"sourceRanks": {"QS": 68, "THE": 91}}])
        self.assertTrue(report.sound)

    def test_a_caveat_saying_the_same_thing_is_not_a_violation(self):
        """Caveats are supplied text disclosing the gap, not a model claim."""
        report = _check(
            "It sits at rank 68.\n\n" + _CAVEATS[0],
            items=[{"sourceRanks": {"QS": 68, "THE": None, "ARWU": None}}],
            caveats=_CAVEATS,
        )
        self.assertTrue(report.sound)


class TestCoverageGapAttribution(unittest.TestCase):
    """Our missing sources are ours. They are not the university withholding."""

    TEXT = "This university reports less data than its peers."

    def test_fires_when_a_coverage_caveat_is_present(self):
        report = _check(self.TEXT, items=[{"aggregatedRank": 68}], caveats=_CAVEATS)
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["coverage_gap_blamed_on_institution"])

    def test_silent_on_identical_text_with_no_coverage_caveat(self):
        report = _check(self.TEXT, items=[{"aggregatedRank": 68}], caveats=[])
        self.assertTrue(report.sound)


class TestStalenessClaim(unittest.TestCase):
    """An ingestion point is when we read it, not what is true now."""

    TEXT = "It is currently ranked 68 worldwide."

    def test_fires_when_the_evidence_carries_an_ingestion_timestamp(self):
        report = _check(
            self.TEXT, items=[{"aggregatedRank": 68, "ingestedAt": "2026-03-27T04:00:00Z"}]
        )
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["stale_data_claimed_current"])

    def test_silent_on_identical_text_with_no_ingestion_marker(self):
        report = _check(self.TEXT, items=[{"aggregatedRank": 68}])
        self.assertTrue(report.sound)


class TestCompletenessClaim(unittest.TestCase):
    """Unlike the others this has no structured gate, and that is deliberate.

    The evidence handed to an explainer is the rows it was given -- a page. A
    claim about what lies outside those rows is never supportable, whatever the
    fields say. What must not happen is catching the *scoped* version, which is
    both common and true.
    """

    def test_fires_on_a_claim_about_what_lies_outside_the_evidence(self):
        report = _check(
            "These are the only universities that match your criteria.",
            items=[{"universityName": "A"}, {"universityName": "B"}],
        )
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["unsupported_completeness_claim"])

    def test_silent_on_a_claim_scoped_to_the_rows_supplied(self):
        report = _check(
            "All 3 universities on this page are ranked in the top 100.",
            items=[{"universityName": "A"}, {"universityName": "B"}, {"universityName": "C"}],
        )
        self.assertTrue(report.sound)


class TestOrderingCriterion(unittest.TestCase):
    """A ranking claim over a dimension the evidence does not carry.

    This is the check with the widest false-positive surface, because ordinary
    comparative prose is common and legitimate. The golden set contains exactly
    one faithful comparative case, so it cannot support a precision claim on its
    own -- most of these negatives are written here rather than drawn from it.
    """

    RANK_ONLY = [
        {"universityName": "NTU", "aggregatedRank": 68},
        {"universityName": "NCKU", "aggregatedRank": 220},
    ]

    def test_fires_when_the_criterion_is_in_no_field(self):
        report = _check(
            "NTU at rank 68 is the better choice for international students.",
            items=self.RANK_ONLY,
        )
        self.assertFalse(report.sound)
        self.assertEqual(report.kinds, ["unsupported_ordering_criterion"])

    def test_silent_on_identical_text_when_the_field_is_present(self):
        with_ratio = [dict(i, internationalStudentRatio=41.2) for i in self.RANK_ONLY]
        report = _check(
            "NTU at rank 68 is the better choice for international students.",
            items=with_ratio,
        )
        self.assertTrue(report.sound)

    def test_a_field_explicitly_null_does_not_ground_the_claim(self):
        """A key set to null is the same absence sourceRanks nulls describe."""
        report = _check(
            "NTU is the better choice for international students.",
            items=[{"universityName": "NTU", "internationalStudentRatio": None}],
        )
        self.assertFalse(report.sound)

    def test_a_bare_rank_comparison_is_not_a_criterion_claim(self):
        report = _check(
            "NTU at aggregated rank 68 places ahead of NCKU at 220.", items=self.RANK_ONLY
        )
        self.assertTrue(report.sound)

    def test_a_superlative_with_no_criterion_is_left_alone(self):
        report = _check("NTU at rank 68 is the strongest match.", items=self.RANK_ONLY)
        self.assertTrue(report.sound)

    def test_top_n_is_not_an_ordering_criterion(self):
        report = _check(
            "All 3 universities here are ranked in the top 100.", items=self.RANK_ONLY
        )
        self.assertTrue(report.sound)

    def test_naming_a_dimension_without_ranking_on_it_is_fine(self):
        report = _check(
            "NTU is at rank 68. The evidence does not cover international students.",
            items=self.RANK_ONLY,
        )
        self.assertTrue(report.sound)

    def test_the_ordering_window_does_not_reach_across_a_sentence(self):
        """The defect this covers: an unrelated superlative one clause earlier."""
        report = _check(
            "NTU is the best on rank. A separate note: policies for international "
            "students vary by country and are outside this data set.",
            items=self.RANK_ONLY,
        )
        self.assertTrue(report.sound)

    def test_an_unrecognised_criterion_is_not_guessed_at(self):
        """Outside the closed QS vocabulary there is nothing to check against."""
        report = _check("NTU is the better choice for campus nightlife.", items=self.RANK_ONLY)
        self.assertTrue(report.sound)


class TestDimensionVocabularyMatchesTheQsContract(unittest.TestCase):
    """The vocabulary is restated, not imported, so it can drift. This is the alarm.

    ``crawlernest-ml`` is not on the agent's import path, so ``provenance.py``
    cannot import ``QS_INDICATORS``. Loading the schema by file path here keeps
    the duplication honest: a renamed or added indicator fails this test instead
    of silently leaving a dimension unwatched.
    """

    def _load_schema(self):
        import importlib.util
        from pathlib import Path

        path = (Path(__file__).resolve().parents[1]
                / "crawlernest-ml" / "ranking_ml" / "features" / "schema.py")
        if not path.exists():  # pragma: no cover - depends on checkout layout
            self.skipTest(f"ML schema not present at {path}")
        spec = importlib.util.spec_from_file_location("_qs_schema", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_every_qs_indicator_has_a_dimension_entry(self):
        from crawlernest.agent.web_agent.generation.provenance import _DIMENSIONS

        indicators = set(self._load_schema().QS_INDICATORS)
        self.assertEqual(
            indicators - set(_DIMENSIONS),
            set(),
            "a QS indicator has no entry in provenance._DIMENSIONS, so ordering claims "
            "about it cannot be checked",
        )

    def test_no_dimension_entry_invents_an_indicator(self):
        from crawlernest.agent.web_agent.generation.provenance import _DIMENSIONS

        indicators = set(self._load_schema().QS_INDICATORS)
        self.assertEqual(set(_DIMENSIONS) - indicators, set())


class TestWiredIntoVerification(unittest.TestCase):
    """Firing in isolation is not the same as changing what the caller gets."""

    def setUp(self) -> None:
        reset_verification_stats()

    def test_a_provenance_violation_discards_the_generated_text(self):
        outcome = verify_explanation(
            explanation="QS scores it at 20.4 on employer reputation.\n\n" + _CAVEATS[0],
            items=[{"employerReputation": 20.4, "isEstimated": True}],
            caveats=_CAVEATS,
        )
        self.assertEqual(outcome.action, USE_FALLBACK)
        self.assertEqual(outcome.provenance_violations, ["estimate_credited_to_source"])
        self.assertIn("estimate_credited_to_source", outcome.warning)

    def test_the_two_mechanical_signals_are_counted_apart(self):
        """Which one fired matters: a signal that never fires is worth noticing."""
        verify_explanation(
            explanation="It is currently ranked 68.\n\n" + _CAVEATS[0],
            items=[{"aggregatedRank": 68, "ingestedAt": "2026-03-27T04:00:00Z"}],
            caveats=_CAVEATS,
        )
        stats = verification_stats()
        self.assertEqual(stats["provenance_flagged"], 1)
        self.assertEqual(stats["rules_flagged"], 0)
        self.assertEqual(stats["use_fallback"], 1)

    def test_a_clean_explanation_still_passes(self):
        outcome = verify_explanation(
            explanation="National Taiwan University sits at aggregated rank 68.\n\n" + _CAVEATS[0],
            items=[{"universityName": "National Taiwan University", "aggregatedRank": 68}],
            caveats=_CAVEATS,
        )
        self.assertNotEqual(outcome.action, USE_FALLBACK)
        self.assertEqual(verification_stats()["provenance_flagged"], 0)


if __name__ == "__main__":
    unittest.main()
