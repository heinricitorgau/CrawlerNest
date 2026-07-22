"""Offline tests for the ds4 recommendation explanation generator.

These tests never hit the network: the LLM provider is replaced by a capturing
fake, and the ds4 provider wiring is checked through config resolution only.
"""

from __future__ import annotations

import unittest
from unittest import mock

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator


class CapturingGenerator:
    """Stand-in for WebResponseGenerator that records the prompt it receives."""

    def __init__(self, *, source: str = "llm", reply: str = "LLM explanation.") -> None:
        self.prompt: PromptPayload | None = None
        self.fallback_text: str | None = None
        self._source = source
        self._reply = reply

    def generate_response(self, *, prompt: PromptPayload, fallback_text: str) -> GenerationResult:
        self.prompt = prompt
        self.fallback_text = fallback_text
        if self._source == "fallback":
            text = fallback_text
        else:
            text = self._reply
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text]
        return GenerationResult(
            reply_text=text,
            paragraphs=paragraphs,
            source=self._source,
            model_name="deepseek-v4-flash" if self._source == "llm" else None,
        )


_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "category": "target",
        "aggregatedRank": 68,
        "matchingScore": 0.82,
        "recommendationConfidence": "medium",
        "ieltsRequirement": 6.5,
    },
    {
        "universityName": "National Tsing Hua University",
        "country": "Taiwan",
        "category": "safety",
        "aggregatedRank": 220,
        "matchingScore": 0.74,
        "recommendationConfidence": "low",
    },
]

_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]


class TestRecommendationExplainer(unittest.TestCase):
    def test_grounded_prompt_carries_evidence_and_honesty_rules(self) -> None:
        gen = CapturingGenerator()
        explainer = RecommendationExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(
            items=_ITEMS,
            profile={"country": "Taiwan", "ielts": 6.5},
            query="Recommend Taiwan universities for me",
            caveats=_CAVEATS,
        )

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        # Honesty contract must be present in the system instruction.
        self.assertIn("computed mechanically", system)
        self.assertIn("Never change them", system)
        self.assertIn("Preserve every caveat", system)

        # Evidence must be grounded from the actual items.
        self.assertIn("National Taiwan University", context)
        self.assertIn("aggregated_rank=68", context)
        self.assertIn("matching_score=0.82", context)
        self.assertIn("confidence=medium", context)
        self.assertIn("category=target", context)

        # Caveats must be carried through verbatim.
        self.assertIn(_CAVEATS[0], context)

        # The model-produced prose flows back through the result.
        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "LLM explanation.")
        self.assertEqual(result.model_name, "deepseek-v4-flash")

    def test_prompt_never_asks_model_to_compute_scores(self) -> None:
        gen = CapturingGenerator()
        explainer = RecommendationExplainer(generator=gen)  # type: ignore[arg-type]
        explainer.explain(items=_ITEMS, profile={}, query="explain")

        assert gen.prompt is not None
        constraints = " ".join(gen.prompt.response_constraints).lower()
        # Constraints must forbid altering the numbers, not request new ones.
        self.assertIn("faithfully", constraints)
        self.assertNotIn("compute a score", constraints)
        self.assertNotIn("assign a confidence", constraints)

    def test_falls_back_to_deterministic_reply_on_provider_failure(self) -> None:
        gen = CapturingGenerator(source="fallback")
        explainer = RecommendationExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(
            items=_ITEMS,
            deterministic_reply="Deterministic engine reply.",
        )

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Deterministic engine reply.")

    def test_empty_items_stays_deterministic_without_calling_model(self) -> None:
        gen = CapturingGenerator()
        explainer = RecommendationExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(items=[], deterministic_reply="Nothing matched.")

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Nothing matched.")
        # The model must not be consulted when there is nothing to explain.
        self.assertIsNone(gen.prompt)


class TestDs4ProviderResolution(unittest.TestCase):
    def test_ds4_env_selects_named_ds4_provider(self) -> None:
        env = {
            "WEB_AGENT_DS4_BASE_URL": "http://localhost:8000",
            "WEB_AGENT_GENERATION_DISABLED": "",
            "WEB_AGENT_OPENAI_BASE_URL": "",
            "OPENAI_BASE_URL": "",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            status = WebResponseGenerator().inspect_provider_status()

        self.assertTrue(status["configured"])
        self.assertEqual(status["providerLabel"], "ds4")
        self.assertEqual(status["modelName"], "deepseek-v4-flash")
        # base_url must be normalized to the OpenAI-compatible /v1 root.
        self.assertEqual(status["baseUrl"], "http://localhost:8000/v1")

    def test_ds4_disabled_flag_wins(self) -> None:
        env = {
            "WEB_AGENT_DS4_BASE_URL": "http://localhost:8000",
            "WEB_AGENT_GENERATION_DISABLED": "1",
        }
        with mock.patch.dict("os.environ", env, clear=False):
            status = WebResponseGenerator().inspect_provider_status()
        self.assertFalse(status["configured"])


if __name__ == "__main__":
    unittest.main()
