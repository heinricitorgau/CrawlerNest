"""Offline tests for the comparison and application-plan explainers."""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.application_plan_explainer import (
    ApplicationPlanExplainer,
)
from crawlernest.agent.web_agent.generation.comparison_explainer import ComparisonExplainer
from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload


class CapturingGenerator:
    def __init__(self, *, source: str = "llm", reply: str = "LLM prose.") -> None:
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


_COMPARE = [
    {"universityName": "National Taiwan University", "country": "Taiwan", "aggregatedRank": 68, "ieltsMin": 6.5},
    # No ieltsMin: the comparison must not silently treat this as equivalent.
    {"universityName": "National Cheng Kung University", "country": "Taiwan", "aggregatedRank": 220},
]

_PLAN = {
    "planName": "balanced",
    "planSummary": "Two target options and one safety.",
    "recommendedStrategy": "Apply early to the target group.",
    "riskDistribution": {"high": 1, "medium": 1, "low": 1},
    "reach": [{"universityName": "NTU", "decision": "apply", "risk": "high", "reason": "rank gap"}],
    "target": [{"universityName": "NCKU", "decision": "apply", "risk": "medium"}],
    "safety": [],
}


class TestComparisonExplainer(unittest.TestCase):
    def test_grounded_prompt_names_axes_and_missing_fields(self) -> None:
        gen = CapturingGenerator()
        result = ComparisonExplainer(generator=gen).explain(  # type: ignore[arg-type]
            items=_COMPARE,
            criterion="lowest IELTS",
            query="which is easier to get into",
            caveats=["Only QS is available."],
        )

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        self.assertIn("Compare ONLY on the fields provided", system)
        self.assertIn("not a verdict", system)
        self.assertIn("aggregated_rank=68", context)
        self.assertIn("aggregated_rank=220", context)
        self.assertIn("The user cares most about: lowest IELTS", context)
        # A field present for one school but not the other must be called out.
        self.assertIn("Fields not available for every school", context)
        self.assertIn("ielts_min", context.split("Fields not available for every school")[1])
        self.assertIn("Only QS is available.", context)
        self.assertEqual(result.source, "llm")

    def test_single_item_is_not_a_comparison(self) -> None:
        gen = CapturingGenerator()
        result = ComparisonExplainer(generator=gen).explain(  # type: ignore[arg-type]
            items=_COMPARE[:1], deterministic_reply="Only one school selected."
        )
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Only one school selected.")
        self.assertIsNone(gen.prompt)

    def test_falls_back_on_provider_failure(self) -> None:
        gen = CapturingGenerator(source="fallback")
        result = ComparisonExplainer(generator=gen).explain(  # type: ignore[arg-type]
            items=_COMPARE, deterministic_reply="Deterministic compare."
        )
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "Deterministic compare.")


class TestApplicationPlanExplainer(unittest.TestCase):
    def test_grounded_prompt_carries_plan_shape_and_empty_group(self) -> None:
        gen = CapturingGenerator()
        result = ApplicationPlanExplainer(generator=gen).explain(  # type: ignore[arg-type]
            plan=_PLAN, query="walk me through it", caveats=["Only QS is available."]
        )

        assert gen.prompt is not None
        system = gen.prompt.system_instruction
        context = gen.prompt.context_block

        # The plan must never become an admission prediction.
        self.assertIn("Never predict an admission outcome", system)
        self.assertIn("move a school between groups", system)

        self.assertIn("Plan: balanced", context)
        self.assertIn("Risk distribution: high=1; medium=1; low=1", context)
        self.assertIn("Reach group (1):", context)
        self.assertIn("risk=high", context)
        # An empty group is stated, not hidden.
        self.assertIn("Safety group: empty", context)
        self.assertIn("Only QS is available.", context)
        self.assertEqual(result.source, "llm")

    def test_empty_plan_stays_deterministic(self) -> None:
        gen = CapturingGenerator()
        result = ApplicationPlanExplainer(generator=gen).explain(  # type: ignore[arg-type]
            plan={"reach": [], "target": [], "safety": []},
            deterministic_reply="No plan yet.",
        )
        self.assertEqual(result.source, "fallback")
        self.assertEqual(result.text, "No plan yet.")
        self.assertIsNone(gen.prompt)

    def test_deterministic_fallback_describes_plan_shape(self) -> None:
        gen = CapturingGenerator(source="fallback")
        result = ApplicationPlanExplainer(generator=gen).explain(plan=_PLAN)  # type: ignore[arg-type]
        self.assertEqual(result.source, "fallback")
        self.assertIn("balanced", result.text)
        self.assertIn("1 reach", result.text)


if __name__ == "__main__":
    unittest.main()
