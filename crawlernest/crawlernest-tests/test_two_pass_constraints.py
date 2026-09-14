"""The two constraints a caller running its own generation pass needs.

The chat route asks the engine for rows and disclosures and then writes the
prose itself. Two things had to become sayable for that to be affordable and
safe:

``constraints["generation"] = "disabled"``
    Without it the engine writes an explanation nobody reads. On a local ds4
    that is a 60-second model call attached to every turn, on top of the one the
    caller is about to make itself.

``constraints["route"] = "web"``
    Without it the routing keyword scan decides: an ordinary question carrying
    "error" or "壞" is handed to the dev agent, which plans file changes and
    returns through ``format_dev_handoff_result`` -- a path that never reaches
    ``_respond`` and so carries no response-level disclosures at all. A data
    pass that silently becomes a repo-planning pass is the wrong thing twice.

Both are opt-in. The default request must behave exactly as it did, which is
what half of these tests are for.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from typing import Any

from crawlernest.agent.orchestration.routing_policy import RoutingPolicy
from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.web_agent.engine.web_agent_engine import WebAgentEngine
from crawlernest.agent.web_agent.generation.models import GenerationResult, PromptPayload
from crawlernest.core.dataset import DATASET_YEARS


def _request(**kwargs: Any) -> TaskRequest:
    payload: dict[str, Any] = {
        "task_id": "t-1",
        "mode": "web",
        "kind": "data_query",
        "user_input": "list rankings",
    }
    payload.update(kwargs)
    return TaskRequest(**payload)


class TestWebRoutePin(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RoutingPolicy()

    def test_dev_keywords_still_hand_off_by_default(self) -> None:
        # The behaviour the pin exists to opt out of, asserted first so a
        # regression in it cannot hide behind the pin's tests.
        decision = self.policy.decide(_request(user_input="the ranking parser has a bug"))

        self.assertEqual(decision.route, "web_to_dev")
        self.assertTrue(decision.signals.has_code_keywords)

    def test_pin_keeps_a_dev_sounding_question_on_the_web_engine(self) -> None:
        decision = self.policy.decide(
            _request(
                user_input="the ranking parser has a bug",
                constraints={"route": "web"},
            )
        )

        self.assertEqual(decision.route, "web")
        # The signals still report what the text looks like. The pin changes
        # where the request goes, not what we noticed about it.
        self.assertTrue(decision.signals.has_code_keywords)
        self.assertTrue(decision.signals.is_dev_intent)
        self.assertIn("pinned", decision.reason)

    def test_pin_is_a_no_op_for_an_ordinary_question(self) -> None:
        pinned = self.policy.decide(_request(constraints={"route": "web"}))
        unpinned = self.policy.decide(_request())

        self.assertEqual(pinned.route, "web")
        self.assertEqual(unpinned.route, "web")

    def test_pin_cannot_smuggle_a_dev_refinement_onto_the_web_engine(self) -> None:
        # An explicit dev kind is a request for the dev agent, not a phrasing
        # accident, so the pin does not override it.
        decision = self.policy.decide(
            _request(kind="dev_refinement", constraints={"route": "web"})
        )

        self.assertNotEqual(decision.route, "web")

    def test_pin_does_not_apply_to_non_web_sources(self) -> None:
        decision = self.policy.decide(
            _request(source="cli", constraints={"route": "web"})
        )

        self.assertEqual(decision.route, "dev")

    def test_only_the_web_value_pins(self) -> None:
        for value in ("dev", "", "WEB_TO_DEV", None, 1):
            with self.subTest(value=value):
                decision = self.policy.decide(
                    _request(
                        user_input="the ranking parser has a bug",
                        constraints={"route": value},
                    )
                )
                self.assertEqual(decision.route, "web_to_dev")


class _SpyGenerator:
    """Records whether the engine asked for prose."""

    def __init__(self) -> None:
        self.calls = 0

    def generate_response(self, *, prompt: PromptPayload, fallback_text: str) -> GenerationResult:
        self.calls += 1
        return GenerationResult(
            reply_text=fallback_text or "generated",
            paragraphs=[fallback_text or "generated"],
            source="llm",
            model_name="spy",
        )


class _StubRankingTools:
    def list_rankings(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        return {"items": [], "summary": "0 rows", "metadata": {"total": 0}}


class _StubToolRouter:
    def __init__(self) -> None:
        self.ranking_tools = _StubRankingTools()
        self.recommendation_tools = None
        self.university_tools = None


class TestGenerationDisabledConstraint(unittest.TestCase):
    """The engine's own stores default to /tmp; point them somewhere disposable."""

    _STORE_ENV = (
        "CRAWLERNEST_EXPERIENCE_STORE_PATH",
        "CRAWLERNEST_STRATEGY_STORE_PATH",
        "CRAWLERNEST_LONG_TERM_MEMORY_PATH",
    )

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = {key: os.environ.get(key) for key in self._STORE_ENV}
        for index, key in enumerate(self._STORE_ENV):
            os.environ[key] = os.path.join(self._tmp.name, f"store-{index}.json")

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _engine(self) -> tuple[WebAgentEngine, _SpyGenerator]:
        generator = _SpyGenerator()
        engine = WebAgentEngine(
            tool_router=_StubToolRouter(),
            generator=generator,  # type: ignore[arg-type]
        )
        return engine, generator

    def test_generation_runs_by_default(self) -> None:
        # The control. Generation always stamps generationSource onto the data,
        # whichever mode it picked, and the query formatter lifts it into meta.
        engine, _ = self._engine()

        response = engine.execute(_request())

        self.assertEqual(response.status, "success")
        self.assertIn("generationSource", response.data.get("meta", {}))

    def test_disabled_skips_generation_entirely(self) -> None:
        engine, generator = self._engine()

        response = engine.execute(_request(constraints={"generation": "disabled"}))

        self.assertEqual(response.status, "success")
        self.assertEqual(generator.calls, 0)
        self.assertNotIn("generationSource", response.data.get("meta", {}))

    def test_disabled_still_returns_the_rows_and_the_disclosures(self) -> None:
        # The whole point of the pass: data and warnings, minus the prose.
        engine, _ = self._engine()

        response = engine.execute(
            _request(
                # A year the warehouse does not hold, so a disclosure is due.
                context={"year": min(DATASET_YEARS) - 1},
                constraints={"generation": "disabled"},
            )
        )

        self.assertEqual(response.data.get("type"), "query")
        self.assertTrue(
            any("UnsupportedYearWarning" in warning for warning in response.warnings),
            f"no disclosure survived the data-only pass: {response.warnings!r}",
        )

    def test_an_unrecognised_value_leaves_generation_on(self) -> None:
        # Failing open matters more than failing closed here: a typo that
        # silently removed the explanation would look like a model outage.
        engine, _ = self._engine()

        response = engine.execute(_request(constraints={"generation": "off"}))

        self.assertIn("generationSource", response.data.get("meta", {}))


if __name__ == "__main__":
    unittest.main()
