"""Offline tests for the ds4 university-lookup explanation generator."""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.agent.web_agent.generation.university_lookup_explainer import (
    UniversityLookupExplainer,
)


class CapturingGenerator:
    def __init__(self, *, source: str = "llm", reply: str = "LLM lookup explanation.") -> None:
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


_PREVIEW = {
    "university_display_name": "National Taiwan University",
    "aliases": ["NTU", "臺大"],
    "identity_summary": {"status": "active", "city_name": "Taipei", "website_url": "https://ntu.edu.tw"},
    "ranking_summary": {"row_count": 1, "source_count": 1, "sources": ["QS"], "best_rank": 68, "best_source": "QS"},
    "admission_summary": None,
    "data_availability": {"has_ranking_data": True, "has_admission_data": False, "missing_sections": ["admission"]},
}

_CAVEATS = ["Only the QS source is available; THE and ARWU ranks are null."]


class TestUniversityLookupExplainer(unittest.TestCase):
    def test_grounded_prompt_carries_preview_and_missing_sections(self) -> None:
        gen = CapturingGenerator()
        explainer = UniversityLookupExplainer(generator=gen, verify=False)  # type: ignore[arg-type]

        result = explainer.explain(preview=_PREVIEW, query="Tell me about NTU", caveats=_CAVEATS)

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        self.assertIn("do not fill a missing section", system)
        self.assertIn("Preserve every caveat", system)

        self.assertIn("National Taiwan University", context)
        self.assertIn("best_rank=68", context)
        self.assertIn("missing sections: admission", context)
        self.assertIn("admission: none available", context)
        self.assertIn(_CAVEATS[0], context)

        self.assertEqual(result.source, "llm")
        self.assertEqual(result.text, "LLM lookup explanation.")

    def test_falls_back_on_provider_failure(self) -> None:
        gen = CapturingGenerator(source="fallback")
        explainer = UniversityLookupExplainer(generator=gen, verify=False)  # type: ignore[arg-type]
        result = explainer.explain(preview=_PREVIEW, deterministic_reply="Deterministic lookup reply.")
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Deterministic lookup reply.")

    def test_empty_preview_stays_deterministic_without_calling_model(self) -> None:
        gen = CapturingGenerator()
        explainer = UniversityLookupExplainer(generator=gen, verify=False)  # type: ignore[arg-type]
        result = explainer.explain(preview={}, deterministic_reply="No university.")
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "No university.")
        self.assertIsNone(gen.prompt)


if __name__ == "__main__":
    unittest.main()
