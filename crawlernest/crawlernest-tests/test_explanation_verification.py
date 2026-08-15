"""The verification layer between generation and the caller.

Until this existed the faithfulness checker was scored in CI and never consulted
at generation time, so an explanation that broke the honesty contract was
measured rather than stopped. These tests cover the two signals and, more
importantly, the different weight each is given: the rules discard the model's
text, the judge only annotates it.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.judge import JudgeVerdict, LlmJudge
from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)
from crawlernest.agent.web_agent.generation.verification import (
    KEEP,
    KEEP_WITH_WARNING,
    USE_FALLBACK,
    verify_explanation,
)

_ITEMS = [{"universityName": "National Taiwan University", "aggregatedRank": 68}]
_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]
_FAITHFUL = (
    "National Taiwan University sits at aggregated rank 68.\n\n"
    "Only the QS source is available; THE and ARWU ranks are null."
)
_INVENTS_A_RANK = (
    "National Taiwan University is ranked 12.\n\n"
    "Only the QS source is available; THE and ARWU ranks are null."
)


class StubGenerator:
    def __init__(self, reply: str, source: str = "llm") -> None:
        self._reply, self._source = reply, source

    def generate_response(self, *, prompt: PromptPayload, fallback_text: str) -> GenerationResult:
        text = fallback_text if self._source == "fallback" else self._reply
        return GenerationResult(
            reply_text=text,
            paragraphs=[p for p in text.split("\n\n") if p.strip()] or [text],
            source=self._source,
            model_name="stub" if self._source == "llm" else None,
        )


class StubJudge(LlmJudge):
    """A judge whose verdict is decided by the test, not by a network call."""

    def __init__(self, verdict: JudgeVerdict | None, configured: bool = True) -> None:
        super().__init__(base_url="http://stub" if configured else "", model_name="stub")
        self._verdict = verdict
        self.calls = 0

    def review(self, **kwargs):  # type: ignore[override]
        self.calls += 1
        return self._verdict


class TestVerificationDecision(unittest.TestCase):
    def test_rules_violation_wins_and_the_judge_is_not_consulted(self):
        """The rules have perfect precision on the golden set; a second opinion
        cannot improve a verdict that is already reliable, only delay it."""
        judge = StubJudge(JudgeVerdict(faithful=True, reason="looks fine", model_name="stub"))
        outcome = verify_explanation(
            explanation=_INVENTS_A_RANK, items=_ITEMS, caveats=_CAVEATS, judge=judge
        )
        self.assertEqual(outcome.action, USE_FALLBACK)
        self.assertIn("unsupported_number", outcome.rule_violations)
        self.assertEqual(judge.calls, 0)

    def test_judge_only_concern_keeps_the_text_and_warns(self):
        """Judge precision is 0.952, so one clean answer in twenty is flagged.
        Discarding good text on that is the wrong trade."""
        judge = StubJudge(JudgeVerdict(faithful=False, reason="undercuts the caveat", model_name="stub"))
        outcome = verify_explanation(
            explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge
        )
        self.assertEqual(outcome.action, KEEP_WITH_WARNING)
        self.assertIn("undercuts the caveat", outcome.warning or "")

    def test_no_opinion_is_not_approval_but_changes_nothing(self):
        """None means unreachable, timed out or unparseable. The outcome must be
        exactly what the rules alone would have produced."""
        judge = StubJudge(None)
        outcome = verify_explanation(
            explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS, judge=judge
        )
        self.assertEqual(outcome.action, KEEP)
        self.assertIsNone(outcome.warning)

    def test_clean_text_with_no_judge_is_kept(self):
        outcome = verify_explanation(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS)
        self.assertEqual(outcome.action, KEEP)


class TestExplainerWiring(unittest.TestCase):
    def test_unfaithful_model_output_is_replaced_by_the_deterministic_reply(self):
        result = RecommendationExplainer(
            generator=StubGenerator(_INVENTS_A_RANK), verify=True  # type: ignore[arg-type]
        ).explain(items=_ITEMS, caveats=_CAVEATS, deterministic_reply="Rule-based reply.")

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Rule-based reply.")
        self.assertIn("faithfulness check", result.warning or "")

    def test_faithful_model_output_survives(self):
        result = RecommendationExplainer(
            generator=StubGenerator(_FAITHFUL), verify=True  # type: ignore[arg-type]
        ).explain(items=_ITEMS, caveats=_CAVEATS, deterministic_reply="Rule-based reply.")

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, _FAITHFUL)
        self.assertIsNone(result.warning)

    def test_a_fallback_reply_is_not_verified_against_itself(self):
        """The fallback is the text this layer would substitute anyway."""
        result = RecommendationExplainer(
            generator=StubGenerator("", source="fallback"), verify=True  # type: ignore[arg-type]
        ).explain(items=_ITEMS, caveats=_CAVEATS, deterministic_reply="Rule-based reply.")

        self.assertEqual(result.source, "fallback")
        self.assertIsNone(result.warning)

    def test_verification_can_be_switched_off(self):
        result = RecommendationExplainer(
            generator=StubGenerator(_INVENTS_A_RANK), verify=False  # type: ignore[arg-type]
        ).explain(items=_ITEMS, caveats=_CAVEATS, deterministic_reply="Rule-based reply.")

        self.assertEqual(result.source, "llm")


class TestJudgeClient(unittest.TestCase):
    def test_an_unconfigured_judge_is_absent_rather_than_permissive(self):
        judge = LlmJudge(base_url="")
        self.assertFalse(judge.is_configured)
        self.assertIsNone(judge.review(explanation="anything", items=_ITEMS))

    def test_an_unreachable_endpoint_yields_no_opinion(self):
        """A network failure must not degrade an explanation that may be fine."""
        judge = LlmJudge(base_url="http://127.0.0.1:1", timeout=0.3)
        self.assertTrue(judge.is_configured)
        self.assertIsNone(judge.review(explanation=_FAITHFUL, items=_ITEMS, caveats=_CAVEATS))


if __name__ == "__main__":
    unittest.main()
