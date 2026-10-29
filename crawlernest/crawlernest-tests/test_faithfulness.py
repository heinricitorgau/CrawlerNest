"""Unit tests for the mechanical faithfulness checker."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

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


def _load_eval_runner():
    path = (
        Path(__file__).resolve().parents[1]
        / "crawlernest-autoeval" / "runners" / "run_faithfulness_eval.py"
    )
    spec = importlib.util.spec_from_file_location("run_faithfulness_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEvalRunnerEvidence(unittest.TestCase):
    """Live mode checks against what the model was shown; fixture mode does not."""

    _ENTRY = {
        "id": "t-1",
        "description": "names the editions the dataset header lists",
        "task_kind": "recommendation",
        "evidence": {"items": _ITEMS, "caveats": [_CAVEAT]},
        "explanation": (
            "The warehouse holds 2015 to 2026 data; National Taiwan University "
            "sits at aggregated rank 68.\n\n" + _CAVEAT
        ),
        "expect": {"faithful": False, "violation_kinds": ["unsupported_number"]},
    }

    def test_live_mode_accepts_years_from_the_dataset_header(self) -> None:
        runner = _load_eval_runner()
        with mock.patch.object(
            runner, "generate_live", return_value=(self._ENTRY["explanation"], "llm")
        ):
            summary = runner.evaluate([self._ENTRY], live=True, verbose=False)
        self.assertEqual(summary["entries"][0]["violations"], [])
        self.assertEqual(summary["result"], "PASS")

    def test_live_mode_still_flags_a_year_the_header_does_not_list(self) -> None:
        runner = _load_eval_runner()
        text = self._ENTRY["explanation"].replace("2026", "2027")
        with mock.patch.object(runner, "generate_live", return_value=(text, "llm")):
            summary = runner.evaluate([self._ENTRY], live=True, verbose=False)
        details = [v["detail"] for v in summary["entries"][0]["violations"]]
        self.assertEqual(details, ["2027 does not appear in the evidence"])

    def test_fixture_mode_does_not_add_the_header(self) -> None:
        summary = _load_eval_runner().evaluate([self._ENTRY], live=False, verbose=False)
        self.assertFalse(summary["entries"][0]["faithful"])
        self.assertEqual(summary["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
