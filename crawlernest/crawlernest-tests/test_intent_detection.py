"""Tests locking the shared lookup/ranking intent detection.

Extracted from prompt_builder / context_builder (which had drifted). These pin
the behavior that both builders now share.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.intent_detection import (
    detect_lookup_intents,
    detect_ranking_intents,
)


class TestLookupIntents(unittest.TestCase):
    def test_location_admission_ranking(self) -> None:
        self.assertIn("location", detect_lookup_intents("where is NTU located?"))
        self.assertIn("admission", detect_lookup_intents("what IELTS requirement for admission?"))
        self.assertIn("ranking", detect_lookup_intents("QS ranking of NTU"))
        self.assertIn("location", detect_lookup_intents("台大在哪個城市"))

    def test_default_is_identity(self) -> None:
        self.assertEqual(detect_lookup_intents("tell me about NTU"), ["identity"])

    def test_the_is_word_bounded(self) -> None:
        # Reconciled to \bthe\b: the standalone word "the" (THE ranking) matches.
        self.assertIn("ranking", detect_lookup_intents("where does it sit in the list"))
        # ...but "the" as a substring of another word must NOT match ranking.
        self.assertEqual(detect_lookup_intents("theory of computation"), ["identity"])

    def test_order_is_stable(self) -> None:
        # location, then admission, then ranking — declaration order.
        self.assertEqual(
            detect_lookup_intents("where is it and what admission ranking"),
            ["location", "admission", "ranking"],
        )


class TestRankingIntents(unittest.TestCase):
    def test_compare_position_why(self) -> None:
        self.assertIn("compare", detect_ranking_intents("compare NTU vs NCKU"))
        self.assertIn("rank_position", detect_ranking_intents("what is NTU's position"))
        self.assertIn("why_high", detect_ranking_intents("why does NTU rank so high"))

    def test_default_is_general_explain(self) -> None:
        self.assertEqual(detect_ranking_intents("explain this to me"), ["general_explain"])


if __name__ == "__main__":
    unittest.main()
