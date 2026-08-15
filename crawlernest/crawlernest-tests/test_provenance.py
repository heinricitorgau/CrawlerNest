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
