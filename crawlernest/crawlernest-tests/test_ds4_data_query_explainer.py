"""Offline tests for the ds4 data-query explanation generator."""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.data_query_explainer import DataQueryExplainer
from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload


class CapturingGenerator:
    def __init__(self, *, source: str = "llm", reply: str = "LLM data explanation.") -> None:
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
        "compositeScore": 81.4,
        "primarySource": "QS",
        "sourceCount": 1,
    },
    {
        "universityName": "National Cheng Kung University",
        "country": "Taiwan",
        "aggregatedRank": 220,
        "compositeScore": 70.1,
        "primarySource": "QS",
        "sourceCount": 1,
    },
]

_METADATA = {"totalCount": 40, "page": 1, "pageSize": 2}
_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]


class TestDataQueryExplainer(unittest.TestCase):
    def test_grounded_prompt_carries_slice_metadata_and_rows(self) -> None:
        gen = CapturingGenerator()
        explainer = DataQueryExplainer(generator=gen, verify=False)  # type: ignore[arg-type]

        result = explainer.explain(
            items=_ITEMS,
            metadata=_METADATA,
            query="Show me Taiwan universities",
            caveats=_CAVEATS,
        )

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        self.assertIn("one page of a larger result set", system)
        self.assertIn("Never change them", system)

        self.assertIn("total_count=40", context)
        self.assertIn("page=1", context)
        self.assertIn("National Taiwan University", context)
        self.assertIn("aggregated_rank=68", context)
        self.assertIn("Rows on this page (2)", context)
        self.assertIn(_CAVEATS[0], context)

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "LLM data explanation.")

    def test_falls_back_on_provider_failure(self) -> None:
        gen = CapturingGenerator(source="fallback")
        explainer = DataQueryExplainer(generator=gen, verify=False)  # type: ignore[arg-type]
        result = explainer.explain(items=_ITEMS, metadata=_METADATA, deterministic_reply="Deterministic data reply.")
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Deterministic data reply.")

    def test_empty_items_stays_deterministic_without_calling_model(self) -> None:
        gen = CapturingGenerator()
        explainer = DataQueryExplainer(generator=gen, verify=False)  # type: ignore[arg-type]
        result = explainer.explain(items=[], metadata={}, deterministic_reply="No rows.")
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "No rows.")
        self.assertIsNone(gen.prompt)


if __name__ == "__main__":
    unittest.main()
