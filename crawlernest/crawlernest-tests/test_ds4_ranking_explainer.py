"""Offline tests for the ds4 ranking-explain explanation generator.

No network: the LLM provider is replaced by a capturing fake.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer


class CapturingGenerator:
    def __init__(self, *, source: str = "llm", reply: str = "LLM ranking explanation.") -> None:
        self.prompt: PromptPayload | None = None
        self._source = source
        self._reply = reply

    def generate_response(self, *, prompt: PromptPayload, fallback_text: str) -> GenerationResult:
        self.prompt = prompt
        text = fallback_text if self._source == "fallback" else self._reply
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
        "aggregatedRank": 68,
        "globalRank": 68,
        "scopeRank": 3,
        "compositeScore": 81.4,
        "primarySource": "QS",
        "sourceCount": 1,
        "rankingYear": 2026,
    },
]

_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]


class TestRankingExplainer(unittest.TestCase):
    def test_grounded_prompt_carries_ranking_evidence_and_honesty_rules(self) -> None:
        gen = CapturingGenerator()
        explainer = RankingExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(
            items=_ITEMS,
            focus_entity="National Taiwan University",
            query="Where does NTU rank?",
            caveats=_CAVEATS,
        )

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        self.assertIn("come straight from the data", system)
        self.assertIn("Never change them", system)
        self.assertIn("Preserve every caveat", system)

        self.assertIn("National Taiwan University", context)
        self.assertIn("aggregated_rank=68", context)
        self.assertIn("primary_source=QS", context)
        self.assertIn("source_count=1", context)
        self.assertIn("Focus of the question: National Taiwan University", context)
        self.assertIn(_CAVEATS[0], context)

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "LLM ranking explanation.")
        self.assertEqual(result.model_name, "deepseek-v4-flash")

    def test_falls_back_on_provider_failure(self) -> None:
        gen = CapturingGenerator(source="fallback")
        explainer = RankingExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(items=_ITEMS, deterministic_reply="Deterministic ranking reply.")

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Deterministic ranking reply.")

    def test_empty_items_stays_deterministic_without_calling_model(self) -> None:
        gen = CapturingGenerator()
        explainer = RankingExplainer(generator=gen)  # type: ignore[arg-type]

        result = explainer.explain(items=[], deterministic_reply="No rows.")

        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "No rows.")
        self.assertIsNone(gen.prompt)


if __name__ == "__main__":
    unittest.main()
