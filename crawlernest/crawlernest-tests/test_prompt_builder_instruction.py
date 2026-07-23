"""Characterization tests for WebPromptBuilder system-instruction / constraints.

These pin behavior so the per-task if/elif ladders can be made table-driven
without changing output. Golden values captured from the pre-refactor code.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.prompt_builder import WebPromptBuilder
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy

_BASE_PREFIX = "You are CrawlerNest Web Agent."
_HYBRID_HINT = "Use the retrieved context as the primary basis for the answer."
_LLM_HINT = "You may answer more freely, but stay conservative"
_EN_HINT = "Respond in English."
_ZH_HINT = "Respond in Traditional Chinese unless the user clearly asks in another language."


class TestSystemInstruction(unittest.TestCase):
    def setUp(self) -> None:
        self.pb = WebPromptBuilder()

    def _sys(self, task_kind, *, lookup=None, ranking=None, mode="hybrid", language="en"):
        return self.pb._build_system_instruction(
            task_kind=task_kind,
            language=language,
            lookup_intents=lookup or [],
            ranking_intents=ranking or [],
            generation_mode=mode,
        )

    def test_ranking_compare(self) -> None:
        s = self._sys("ranking_explain", ranking=["compare"])
        self.assertTrue(s.startswith(_BASE_PREFIX))
        self.assertIn("Prioritize comparison.", s)
        self.assertIn(_HYBRID_HINT, s)
        self.assertIn(_EN_HINT, s)

    def test_ranking_first_match_wins(self) -> None:
        # rank_position precedes why_high in priority; only its override applies.
        s = self._sys("ranking_explain", ranking=["rank_position", "why_high"], mode="llm")
        self.assertIn("Prioritize rank position.", s)
        self.assertNotIn("Prioritize why-this-school-ranks-high", s)
        self.assertIn(_LLM_HINT, s)

    def test_ranking_default(self) -> None:
        s = self._sys("ranking_explain", ranking=["general_explain"])
        self.assertIn("Prioritize explaining what the current ranking evidence says", s)

    def test_lookup_location_zh(self) -> None:
        s = self._sys("university_lookup", lookup=["location"], language="zh")
        self.assertIn("Prioritize locating the university", s)
        self.assertIn(_ZH_HINT, s)

    def test_lookup_default(self) -> None:
        s = self._sys("university_lookup", lookup=["identity"])
        self.assertIn("Prioritize giving a compact university profile", s)

    def test_data_query_and_recommendation_static(self) -> None:
        self.assertIn("Prioritize helping the user understand the returned slice", self._sys("data_query"))
        self.assertIn("Prioritize decision guidance.", self._sys("recommendation", mode="llm"))


class TestResponseConstraints(unittest.TestCase):
    def setUp(self) -> None:
        self.pb = WebPromptBuilder()
        self.pol = WebAgentPolicy()

    def _con(self, task_kind, *, lookup=None, ranking=None, mode="hybrid", language="en", patches=None):
        return self.pb._build_response_constraints(
            task_kind=task_kind,
            language=language,
            policy=self.pol,
            lookup_intents=lookup or [],
            ranking_intents=ranking or [],
            generation_mode=mode,
            prompt_patches=patches or [],
        )

    def test_ranking_additive_intents(self) -> None:
        self.assertEqual(
            self._con("ranking_explain", ranking=["compare", "rank_position"]),
            [
                "Prefer concise natural language over rigid templates.",
                "Stay grounded in the retrieved context.",
                "Do not mention internal tool names, traces, or implementation details.",
                "Do not simply restate the top rows. Explain what the ranking data implies for the user's question.",
                "If the user is really asking about admissions, location, or identity rather than rank quality, say that explicitly.",
                "Keep the answer focused on the comparison the user is implicitly asking for.",
                "Do not pretend you have a full side-by-side dataset if the current retrieval only shows one page or partial matches.",
                "State the strongest supported rank signal clearly before adding caveats.",
                "If the current result is only page-level evidence, say so instead of overstating certainty.",
                "Write as a user-facing assistant, not as an engineering report.",
                "Anchor the answer to the retrieved context whenever possible.",
            ],
        )

    def test_lookup_all_intents_with_mode_llm(self) -> None:
        self.assertEqual(
            self._con("university_lookup", lookup=["location", "admission", "ranking"]),
            [
                "Prefer concise natural language over rigid templates.",
                "Stay grounded in the retrieved context.",
                "Do not mention internal tool names, traces, or implementation details.",
                "Start with the school identity before moving into supporting details.",
                "If ranking or admission data is missing, say so plainly instead of filling gaps.",
                "Answer the location question directly before giving extra background.",
                "If the current preview only provides partial location evidence, say that the answer is based on current preview signals.",
                "Do not treat preview admissions hints as definitive policy unless the data clearly says so.",
                "If the user asks for thresholds and the context is thin, say that the current preview is only a hint.",
                "Keep the explanation focused on the university in question, not the whole ranking page.",
                "Mention missing ranking evidence if the preview does not provide enough support.",
                "Write as a user-facing assistant, not as an engineering report.",
                "Anchor the answer to the retrieved context whenever possible.",
            ],
        )

    def test_recommendation_with_patches_zh(self) -> None:
        self.assertEqual(
            self._con("recommendation", mode="hybrid", language="zh", patches=["patch a", "patch b"]),
            [
                "Prefer concise natural language over rigid templates.",
                "Stay grounded in the retrieved context.",
                "Do not mention internal tool names, traces, or implementation details.",
                "Explain the fit, not just the names.",
                "Be explicit about uncertainty, tradeoffs, and missing evidence.",
                "Write as a user-facing assistant, not as an engineering report.",
                "Anchor the answer to the retrieved context whenever possible.",
                "Prompt patch: patch a",
                "Prompt patch: patch b",
                "Keep the tone natural in Traditional Chinese.",
            ],
        )

    def test_data_query_llm_mode(self) -> None:
        self.assertEqual(
            self._con("data_query", mode="llm"),
            [
                "Prefer concise natural language over rigid templates.",
                "Stay grounded in the retrieved context.",
                "Do not mention internal tool names, traces, or implementation details.",
                "Summarize the most relevant rows rather than dumping all records.",
                "Mention pagination or total count only when it helps answer the question.",
                "Write as a user-facing assistant, not as an engineering report.",
                "Do not present speculation as confirmed fact when retrieval support is weak.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
