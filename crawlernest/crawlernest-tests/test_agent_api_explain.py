"""Tests for the Agent API explain-only route.

The route exists so the product UI can get prose about rows it is *already
displaying*. It must never recompute or query the warehouse — otherwise the
explanation could describe a different result set than the user sees.
"""

from __future__ import annotations

import unittest
from unittest import mock

from crawlernest.interfaces.api.agent_api.dto import AgentExplainPayload
from crawlernest.interfaces.api.agent_api.handler import AgentApiHandler

_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "category": "target",
        "aggregatedRank": 68,
        "matchingScore": 0.82,
    }
]


class _ExplodingService:
    """AgentService stand-in that fails if the explain path ever touches it."""

    def run(self, request):  # pragma: no cover - must never be called
        raise AssertionError("explain must not go through the task pipeline")


class TestExplainPayload(unittest.TestCase):
    def test_unknown_task_kind_falls_back_to_recommendation(self) -> None:
        payload = AgentExplainPayload.from_dict({"taskKind": "sql_injection", "items": _ITEMS})
        self.assertEqual(payload.task_kind, "recommendation")

    def test_items_and_caveats_are_bounded(self) -> None:
        payload = AgentExplainPayload.from_dict(
            {
                "taskKind": "recommendation",
                "items": [{"universityName": f"U{i}"} for i in range(50)],
                "caveats": [f"c{i}" for i in range(50)],
            }
        )
        self.assertEqual(len(payload.items), 20)
        self.assertEqual(len(payload.caveats), 10)

    def test_non_dict_items_are_dropped(self) -> None:
        payload = AgentExplainPayload.from_dict({"items": [{"a": 1}, "junk", None, 5]})
        self.assertEqual(payload.items, [{"a": 1}])

    def test_snake_and_camel_case_keys_both_accepted(self) -> None:
        payload = AgentExplainPayload.from_dict(
            {"task_kind": "ranking_explain", "deterministic_reply": "d"}
        )
        self.assertEqual(payload.task_kind, "ranking_explain")
        self.assertEqual(payload.deterministic_reply, "d")


class TestExplainHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.handler = AgentApiHandler(service=_ExplodingService())  # type: ignore[arg-type]

    def test_explain_never_uses_the_task_pipeline(self) -> None:
        # _ExplodingService asserts if the task path is used.
        status, body = self.handler.handle_explain(
            {"taskKind": "recommendation", "items": _ITEMS, "deterministicReply": "Rule-based."}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])

    def test_no_provider_configured_returns_deterministic_reply(self) -> None:
        with mock.patch.dict("os.environ", {"WEB_AGENT_GENERATION_DISABLED": "1"}, clear=False):
            status, body = self.handler.handle_explain(
                {
                    "taskKind": "recommendation",
                    "items": _ITEMS,
                    "caveats": ["Only QS is available."],
                    "deterministicReply": "Rule-based reply.",
                }
            )
        self.assertEqual(status, 200)
        data = body["data"]
        self.assertEqual(data["source"], "fallback")
        self.assertEqual(data["explanation"], "Rule-based reply.")
        self.assertEqual(data["taskKind"], "recommendation")

    def test_empty_items_rejected_for_row_based_kinds(self) -> None:
        status, body = self.handler.handle_explain({"taskKind": "recommendation", "items": []})
        self.assertEqual(status, 400)
        self.assertFalse(body["success"])

    def test_university_lookup_allows_empty_items(self) -> None:
        with mock.patch.dict("os.environ", {"WEB_AGENT_GENERATION_DISABLED": "1"}, clear=False):
            status, body = self.handler.handle_explain(
                {
                    "taskKind": "university_lookup",
                    "items": [],
                    "profile": {"university_display_name": "National Taiwan University"},
                    "deterministicReply": "Preview.",
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["source"], "fallback")

    def test_comparison_kind_is_routed(self) -> None:
        with mock.patch.dict("os.environ", {"WEB_AGENT_GENERATION_DISABLED": "1"}, clear=False):
            status, body = self.handler.handle_explain(
                {
                    "taskKind": "comparison",
                    "items": [
                        {"universityName": "A University", "aggregatedRank": 68},
                        {"universityName": "B University", "aggregatedRank": 220},
                    ],
                    "criterion": "lowest rank",
                    "deterministicReply": "Comparing two schools.",
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["taskKind"], "comparison")
        self.assertEqual(body["data"]["source"], "fallback")

    def test_application_plan_kind_uses_plan_not_items(self) -> None:
        with mock.patch.dict("os.environ", {"WEB_AGENT_GENERATION_DISABLED": "1"}, clear=False):
            status, body = self.handler.handle_explain(
                {
                    "taskKind": "application_plan",
                    "items": [],  # plan-based kinds carry no rows
                    "plan": {
                        "planName": "balanced",
                        "reach": [{"universityName": "A University", "risk": "high"}],
                        "target": [],
                        "safety": [],
                    },
                    "deterministicReply": "Plan overview.",
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["taskKind"], "application_plan")
        self.assertEqual(body["data"]["explanation"], "Plan overview.")

    def test_generation_failure_degrades_instead_of_500(self) -> None:
        target = (
            "crawlernest.agent.web_agent.generation.recommendation_explainer"
            ".RecommendationExplainer.explain"
        )
        with mock.patch(target, side_effect=RuntimeError("boom")):
            status, body = self.handler.handle_explain(
                {"items": _ITEMS, "deterministicReply": "Rule-based reply."}
            )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["source"], "fallback")
        self.assertEqual(body["data"]["explanation"], "Rule-based reply.")
        self.assertIn("boom", body["data"]["warning"])


if __name__ == "__main__":
    unittest.main()
