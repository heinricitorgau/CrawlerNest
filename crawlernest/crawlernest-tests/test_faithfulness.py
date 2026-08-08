"""Unit tests for the mechanical faithfulness checker."""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.faithfulness import check_faithfulness

_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "aggregatedRank": 68,
        "matchingScore": 0.82,
        "recommendationConfidence": "medium",
    }
]
_CAVEAT = "Only the QS source is available; THE and ARWU ranks are null."


class TestFaithfulness(unittest.TestCase):
    def test_grounded_explanation_is_faithful(self) -> None:
        report = check_faithfulness(
            explanation=(
                "National Taiwan University sits at aggregated rank 68 with a "
                "matching score of 0.82.\n\n" + _CAVEAT
            ),
            items=_ITEMS,
            caveats=[_CAVEAT],
        )
        self.assertTrue(report.faithful)
        self.assertEqual(report.violations, [])

    def test_fabricated_number_is_flagged(self) -> None:
        report = check_faithfulness(
            explanation="National Taiwan University is ranked 12.\n\n" + _CAVEAT,
            items=_ITEMS,
            caveats=[_CAVEAT],
        )
        self.assertFalse(report.faithful)
        self.assertEqual(report.kinds, ["unsupported_number"])
        self.assertIn("12", report.violations[0].detail)

    def test_dropped_caveat_is_flagged(self) -> None:
        report = check_faithfulness(
            explanation="National Taiwan University sits at rank 68.",
            items=_ITEMS,
            caveats=[_CAVEAT],
        )
        self.assertFalse(report.faithful)
        self.assertEqual(report.kinds, ["missing_caveat"])

    def test_caveat_matching_ignores_whitespace_reflow(self) -> None:
        report = check_faithfulness(
            explanation="Rank 68.\n\nOnly the QS source is available;\n  THE and ARWU ranks are null.",
            items=_ITEMS,
            caveats=[_CAVEAT],
        )
        self.assertTrue(report.faithful)

    def test_invented_university_is_flagged(self) -> None:
        report = check_faithfulness(
            explanation="National Taiwan University (68) beats Pacific Rim University.",
            items=_ITEMS,
        )
        self.assertEqual(report.kinds, ["unsupported_university"])

    def test_positions_and_counts_are_allowed(self) -> None:
        # "2 rows" / "the 2nd" describe the given list, not new facts.
        items = [{"universityName": "A University", "aggregatedRank": 68},
                 {"universityName": "B University", "aggregatedRank": 220}]
        report = check_faithfulness(
            explanation="Across the 2 rows, A University leads at 68 and B University follows at 220.",
            items=items,
        )
        self.assertTrue(report.faithful)

    def test_rescaled_score_is_flagged_deliberately(self) -> None:
        report = check_faithfulness(
            explanation="National Taiwan University is an 82% match.",
            items=_ITEMS,
        )
        self.assertEqual(report.kinds, ["unsupported_number"])

    def test_numbers_from_extra_evidence_are_supported(self) -> None:
        report = check_faithfulness(
            explanation="With IELTS 6.5 in the profile, rank 68 is a target.",
            items=_ITEMS,
            evidence={"profile": {"ielts": 6.5}},
        )
        self.assertTrue(report.faithful)

    def test_report_serializes_for_the_runner(self) -> None:
        report = check_faithfulness(explanation="Ranked 12.", items=_ITEMS)
        payload = report.as_dict()
        self.assertFalse(payload["faithful"])
        self.assertEqual(payload["violations"][0]["kind"], "unsupported_number")


if __name__ == "__main__":
    unittest.main()
