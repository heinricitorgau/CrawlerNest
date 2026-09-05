"""The single-year dataset declaration, and that every layer actually honours it.

Three separate things can drift apart here, and each has its own failure:

- the declaration itself (``dataset_context``),
- whether the explainers put it in front of the model at all, and
- whether the query defaults still agree with the year the warehouse holds.

The middle one is why these are prompt assertions rather than constant
assertions. A trend claim invents no figure, drops no caveat and names no
institution, so ``faithfulness.py`` cannot reach it (golden case faith-122
records exactly that). The only place it is stopped is before generation, which
means a subclass that stopped routing through ``GroundedExplainer._explain``
would lose the constraint with nothing downstream noticing.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from crawlernest.agent.web_agent.generation.comparison_explainer import ComparisonExplainer
from crawlernest.agent.web_agent.generation.data_query_explainer import DataQueryExplainer
from crawlernest.agent.web_agent.generation.dataset_context import (
    DATASET_CONSTRAINTS,
    DATASET_SOURCES,
    DATASET_YEAR,
    build_dataset_header,
)
from crawlernest.agent.web_agent.generation.models import (
    GenerationResult,
    PromptPayload,
    RetrievedContext,
)
from crawlernest.agent.web_agent.generation.prompt_builder import WebPromptBuilder
from crawlernest.agent.web_agent.generation.ranking_explainer import RankingExplainer
from crawlernest.agent.web_agent.generation.recommendation_explainer import (
    RecommendationExplainer,
)
from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy

GOLDEN_FILE = (
    Path(__file__).resolve().parents[1]
    / "crawlernest-autoeval"
    / "datasets"
    / "faithfulness"
    / "golden.json"
)


class CapturingGenerator:
    """Records the prompt instead of calling a provider."""

    def __init__(self) -> None:
        self.prompt: PromptPayload | None = None

    def generate_response(self, *, prompt: PromptPayload, fallback_text: str) -> GenerationResult:
        self.prompt = prompt
        return GenerationResult(
            reply_text="Generated explanation.",
            paragraphs=["Generated explanation."],
            source="llm",
            model_name="deepseek-v4-flash",
        )


_ITEMS = [
    {
        "universityName": "National Taiwan University",
        "country": "Taiwan",
        "aggregatedRank": 68,
        "matchingScore": 0.82,
        "rankingYear": DATASET_YEAR,
    },
    {
        "universityName": "National Cheng Kung University",
        "country": "Taiwan",
        "aggregatedRank": 220,
        "matchingScore": 0.61,
        "rankingYear": DATASET_YEAR,
    },
]


class TestDatasetDeclaration(unittest.TestCase):
    def test_the_facts_are_owned_by_core_and_re_exported(self) -> None:
        # The year and the sources are warehouse facts, so they live in core and
        # the generation layer reads them from there. Two copies would let the
        # query defaults and the corpus description the model reads disagree.
        from crawlernest.core import dataset as core_dataset

        self.assertIs(DATASET_YEAR, core_dataset.DATASET_YEAR)
        self.assertIs(DATASET_SOURCES, core_dataset.DATASET_SOURCES)

    def test_core_does_not_import_the_agent_layer(self) -> None:
        # agent imports core, never the reverse. This is the rule the constants
        # were moved to restore, and an import is all it takes to break it.
        core_root = Path(__file__).resolve().parents[1] / "core"
        offenders = [
            path.name
            for path in core_root.rglob("*.py")
            if "crawlernest.agent" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])

    def test_header_states_year_sources_and_the_snapshot_rule(self) -> None:
        lines = build_dataset_header().split("\n")
        self.assertEqual(len(lines), 3)
        self.assertIn(str(DATASET_YEAR), lines[0])
        for source in DATASET_SOURCES:
            self.assertIn(source, lines[1])
        self.assertIn("single-year snapshot", lines[2])

    def test_header_is_derived_from_the_constants(self) -> None:
        # A header written out by hand is one a dataset migration can leave
        # describing a year the warehouse no longer holds.
        import crawlernest.agent.web_agent.generation.dataset_context as ctx

        original = ctx.DATASET_YEAR
        try:
            ctx.DATASET_YEAR = 2031
            self.assertIn("2031", ctx.build_dataset_header())
        finally:
            ctx.DATASET_YEAR = original

    def test_constraints_forbid_other_years_and_trend_wording(self) -> None:
        joined = " ".join(DATASET_CONSTRAINTS)
        self.assertIn(str(DATASET_YEAR), joined)
        for phrase in ("currently", "latest", "year after year"):
            self.assertIn(phrase, joined)


class TestExplainersCarryTheDeclaration(unittest.TestCase):
    """Every grounded explainer, not just the one that happened to be edited."""

    def _capture(self, explainer_cls, **kwargs) -> PromptPayload:
        gen = CapturingGenerator()
        explainer = explainer_cls(generator=gen, verify=False)  # type: ignore[arg-type]
        explainer.explain(items=_ITEMS, **kwargs)
        assert gen.prompt is not None
        return gen.prompt

    def test_every_explainer_prepends_the_header_and_appends_the_constraints(self) -> None:
        header = build_dataset_header()
        for explainer_cls in (
            RecommendationExplainer,
            RankingExplainer,
            DataQueryExplainer,
            ComparisonExplainer,
        ):
            with self.subTest(explainer=explainer_cls.__name__):
                prompt = self._capture(explainer_cls)
                self.assertTrue(
                    prompt.context_block.startswith(header),
                    f"{explainer_cls.__name__} does not lead with the dataset header",
                )
                for constraint in DATASET_CONSTRAINTS:
                    self.assertIn(constraint, prompt.response_constraints)

    def test_the_declaration_does_not_displace_the_task_constraints(self) -> None:
        prompt = self._capture(RecommendationExplainer)
        for constraint in RecommendationExplainer.constraints:
            self.assertIn(constraint, prompt.response_constraints)

    def test_evidence_rows_carry_the_ranking_year(self) -> None:
        # Without this the model is handed a dated corpus description and
        # undated rows, which is the shape that invites a re-dated figure.
        for explainer_cls in (DataQueryExplainer, ComparisonExplainer):
            with self.subTest(explainer=explainer_cls.__name__):
                prompt = self._capture(explainer_cls)
                self.assertIn(f"ranking_year={DATASET_YEAR}", prompt.context_block)

    def test_recommendation_profile_carries_the_ranking_year(self) -> None:
        gen = CapturingGenerator()
        RecommendationExplainer(generator=gen, verify=False).explain(  # type: ignore[arg-type]
            items=_ITEMS,
            profile={"country": "Taiwan", "rankingYear": DATASET_YEAR},
        )
        assert gen.prompt is not None
        self.assertIn(f"ranking_year={DATASET_YEAR}", gen.prompt.context_block)


class TestQueryDefaultsAgreeWithTheDataset(unittest.TestCase):
    """The defaults that decide which year is actually queried.

    ``recommendation_service`` used ``datetime.now().year`` here, which agrees
    with the warehouse only until the wall clock leaves the snapshot behind, and
    then returns nothing at all.
    """

    def test_ranking_query_defaults_to_the_dataset_year(self) -> None:
        from crawlernest.core.services.ranking_service import RankingQuery

        self.assertEqual(RankingQuery().year, DATASET_YEAR)

    def test_recommendation_query_defaults_to_the_dataset_year(self) -> None:
        from crawlernest.core.services.recommendation_service import RecommendationService

        self.assertEqual(RecommendationService()._build_query({}).ranking_year, DATASET_YEAR)

    def test_ranking_tools_default_matches_the_dataset_year(self) -> None:
        import crawlernest.agent.tools.ranking_tools as ranking_tools

        self.assertIs(ranking_tools.DATASET_YEAR, DATASET_YEAR)


class TestTemporalGoldenCases(unittest.TestCase):
    """The two negative cases guarding this behaviour stay in the golden set.

    The eval runner scores them; this asserts they are still there to be scored,
    which a dataset edit can otherwise remove without failing anything.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.by_id = {
            entry["id"]: entry
            for entry in json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
        }

    def test_trend_extrapolation_case_is_unfaithful_but_beyond_the_rules(self) -> None:
        case = self.by_id["faith-122"]
        self.assertFalse(case["ground_truth"]["faithful"])
        # The rules are expected to pass it: that gap is the finding, and
        # recording it is what keeps the recall figures honest.
        self.assertTrue(case["expect"]["faithful"])
        self.assertEqual(case["expect"]["violation_kinds"], [])

    def test_temporal_misalignment_case_is_caught_by_the_number_rule(self) -> None:
        case = self.by_id["faith-123"]
        self.assertFalse(case["ground_truth"]["faithful"])
        self.assertFalse(case["expect"]["faithful"])
        self.assertEqual(case["expect"]["violation_kinds"], ["unsupported_number"])

    def test_temporal_cases_are_grounded_in_the_dataset_year(self) -> None:
        for case_id in ("faith-122", "faith-123"):
            with self.subTest(case=case_id):
                years = {
                    item.get("rankingYear")
                    for item in self.by_id[case_id]["evidence"]["items"]
                }
                self.assertEqual(years, {DATASET_YEAR})


class TestChatPathCarriesTheDeclaration(unittest.TestCase):
    """The multi-turn path, which is the one the year lock most needs.

    ``WebPromptBuilder`` is the only production builder that fills
    ``conversation_turns``, and those turns are inserted between the system
    message and the current user message. A rule stated only in the user turn
    therefore gets further from the model's attention with every round, and
    reads more like one turn's request than a standing constraint. It carried
    no dataset declaration at all until now, which is the gap these cover.
    """

    def _build(self, *, history: list | None = None) -> PromptPayload:
        return WebPromptBuilder().build(
            user_input="Which universities should I look at?",
            retrieved=RetrievedContext(
                task_kind="ranking_explain",
                user_input="Which universities should I look at?",
                summary_facts=["National Taiwan University is ranked 68."],
            ),
            policy=WebAgentPolicy(),
            conversation_history=history,
        )

    def test_the_declaration_and_rules_reach_the_system_turn(self) -> None:
        prompt = self._build()

        self.assertEqual(prompt.system_context, build_dataset_header())
        for constraint in DATASET_CONSTRAINTS:
            with self.subTest(constraint=constraint[:40]):
                self.assertIn(constraint, prompt.system_constraints)

    def test_rules_are_stated_in_the_user_turn_as_well(self) -> None:
        # Same double statement GroundedExplainer makes. The header itself is
        # deliberately not duplicated into context_block here -- that block is
        # truncated to policy.max_context_chars, so adding to it would compete
        # with the retrieved evidence for the same budget.
        prompt = self._build()

        for constraint in DATASET_CONSTRAINTS:
            with self.subTest(constraint=constraint[:40]):
                self.assertIn(constraint, prompt.response_constraints)

    def test_task_constraints_are_not_displaced(self) -> None:
        prompt = self._build()

        self.assertIn("Stay grounded in the retrieved context.", prompt.response_constraints)
        self.assertIn(
            "Do not mention internal tool names, traces, or implementation details.",
            prompt.response_constraints,
        )

    def test_rendered_system_message_states_the_year_however_long_the_history(self) -> None:
        # The assertion that matters: what messages[0] actually says. Ten prior
        # turns are exactly the case where a user-turn-only rule would be
        # diluted, so the declaration has to survive them unchanged.
        history = [
            type("_Turn", (), {"role": role, "content": f"turn {i}"})()
            for i, role in enumerate(["user", "assistant"] * 5)
        ]
        generator = WebResponseGenerator()

        short = generator._compose_system_content(self._build())
        long = generator._compose_system_content(self._build(history=history))

        self.assertEqual(short, long)
        for rendered in (short, long):
            self.assertIn(str(DATASET_YEAR), rendered)
            for line in build_dataset_header().split("\n"):
                self.assertIn(line, rendered)
            for constraint in DATASET_CONSTRAINTS:
                self.assertIn(constraint, rendered)

    def test_the_system_turn_still_leads_with_the_role_instruction(self) -> None:
        # The declaration is appended, not prepended: an instruction that no
        # longer starts by saying what the agent is would be a different prompt.
        prompt = self._build()
        rendered = WebResponseGenerator()._compose_system_content(prompt)

        self.assertTrue(rendered.startswith("You are CrawlerNest Web Agent."))


if __name__ == "__main__":
    unittest.main()
