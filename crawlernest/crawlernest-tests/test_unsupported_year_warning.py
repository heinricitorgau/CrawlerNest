"""A request for a year the warehouse does not hold has to say so.

The warehouse holds one ranking year. Until now a request naming 2025 was
answered from the 2026 snapshot under HTTP 200 ``success`` with nothing in the
payload recording the substitution -- honest about every number it showed and
silent about which year those numbers described.

These tests pin both halves of the fix: the warning appears, in wording that
attributes the absence to the snapshot rather than to a lookup that failed, and
a request naming 2026 -- or no year at all, which is nearly all of them -- comes
back exactly as it did before.
"""

from __future__ import annotations

import unittest
from typing import Any

from crawlernest.agent.shared.models.task_request import TaskRequest
from crawlernest.agent.web_agent.engine.web_agent_engine import WebAgentEngine
from crawlernest.agent.web_agent.policy import unsupported_year as uy
from crawlernest.agent.web_agent.policy.unsupported_year import (
    UNSUPPORTED_YEAR_WARNING_CODE,
    build_unsupported_year_warning,
    detect_requested_years,
    unsupported_year_warnings,
)
from crawlernest.agent.web_agent.policy.web_agent_policy import WebAgentPolicy
from crawlernest.core.dataset import DATASET_YEAR


class TestYearDetection(unittest.TestCase):
    def test_context_year_keys_are_all_read(self) -> None:
        # Each key is the one some real caller uses: `year` from ranking_tools,
        # the other two from RecommendationService._build_query.
        for key in ("year", "rankingYear", "ranking_year"):
            with self.subTest(key=key):
                self.assertEqual(detect_requested_years(context={key: 2025}), (2025,))

    def test_year_arriving_as_a_string_is_still_a_year(self) -> None:
        # Context comes off an HTTP payload, where "2025" and 2025 are the same
        # request.
        self.assertEqual(detect_requested_years(context={"year": "2025"}), (2025,))
        self.assertEqual(detect_requested_years(context={"year": " 2025 "}), (2025,))

    def test_non_year_context_values_are_ignored(self) -> None:
        for value in (None, "", "latest", True, [2025], {"year": 2025}):
            with self.subTest(value=value):
                self.assertEqual(detect_requested_years(context={"year": value}), ())

    def test_year_typed_into_the_prompt_is_detected(self) -> None:
        # The channel nothing else reads: no tool parses a year out of the
        # prompt, so such a request is answered from the snapshot in silence.
        self.assertEqual(
            detect_requested_years(user_input="Show me the QS 2025 rankings"),
            (2025,),
        )
        self.assertEqual(detect_requested_years(user_input="2024 rankings, please"), (2024,))

    def test_rank_thresholds_are_not_mistaken_for_years(self) -> None:
        # "top 2000" is answerable and in-year. Warning about it would be a
        # false alarm on one of the most common phrasings there is.
        for text in (
            "top 2000 universities",
            "rank under 2000",
            "ranked below 1950",
            "rankings within 2000",
        ):
            with self.subTest(text=text):
                self.assertEqual(detect_requested_years(user_input=text), ())

    def test_digits_that_are_not_years_are_ignored(self) -> None:
        for text in ("GPA 3.2025", "student id 20250413", "TOEFL 105"):
            with self.subTest(text=text):
                self.assertEqual(detect_requested_years(user_input=text), ())

    def test_years_are_deduplicated_and_context_comes_first(self) -> None:
        self.assertEqual(
            detect_requested_years(
                context={"year": 2025},
                user_input="compare 2025 with 2024",
            ),
            (2025, 2024),
        )


#: Years the warehouse does not hold, derived so the examples stay unheld when an
#: edition is released. They were the literal 2025 until 2025 was ingested.
UNHELD = min(uy.DATASET_YEARS) - 1
UNHELD_EARLIER = UNHELD - 1


class TestUnsupportedYearWarnings(unittest.TestCase):
    def test_unsupported_year_produces_the_coded_warning(self) -> None:
        warnings = unsupported_year_warnings(context={"year": UNHELD})
        self.assertEqual(len(warnings), 1)
        self.assertIn(UNSUPPORTED_YEAR_WARNING_CODE, warnings[0])
        self.assertIn(str(UNHELD), warnings[0])
        self.assertIn(str(DATASET_YEAR), warnings[0])

    def test_warning_blames_the_snapshot_not_a_failed_lookup(self) -> None:
        # The whole point: an empty or substituted result must not read as "we
        # looked for that year and could not find it".
        warning = build_unsupported_year_warning(UNHELD)
        self.assertIn("not missing or incomplete data", warning)
        for year in uy.DATASET_YEARS:
            self.assertIn(str(year), warning)

    def test_dataset_year_is_the_only_supported_year(self) -> None:
        self.assertEqual(unsupported_year_warnings(context={"year": DATASET_YEAR}), [])
        self.assertEqual(
            unsupported_year_warnings(user_input=f"QS {DATASET_YEAR} rankings"),
            [],
        )

    def test_a_request_naming_no_year_is_untouched(self) -> None:
        self.assertEqual(
            unsupported_year_warnings(context={"country": "Taiwan"}, user_input="top schools"),
            [],
        )
        self.assertEqual(unsupported_year_warnings(), [])

    def test_one_warning_per_distinct_unsupported_year(self) -> None:
        warnings = unsupported_year_warnings(
            context={"year": UNHELD},
            user_input=f"and {UNHELD} versus {UNHELD_EARLIER}",
        )
        self.assertEqual(len(warnings), 2)
        self.assertIn(str(UNHELD), warnings[0])
        self.assertIn(str(UNHELD_EARLIER), warnings[1])

    def _with_editions(self, years: tuple[int, ...]):
        original = (uy.DATASET_YEARS, uy.DEFAULT_RANKING_YEAR)
        uy.DATASET_YEARS, uy.DEFAULT_RANKING_YEAR = years, max(years)
        self.addCleanup(setattr, uy, "DATASET_YEARS", original[0])
        self.addCleanup(setattr, uy, "DEFAULT_RANKING_YEAR", original[1])

    def test_warning_text_follows_the_dataset_year(self) -> None:
        # Re-pointing the warehouse at another year must not leave this naming
        # the old one.
        self._with_editions((2031,))
        self.assertIn("2031", uy.build_unsupported_year_warning(2026))
        self.assertEqual(uy.unsupported_year_warnings(context={"year": 2031}), [])
        self.assertEqual(len(uy.unsupported_year_warnings(context={"year": 2026})), 1)

    def test_single_edition_text_is_unchanged(self) -> None:
        self._with_editions((2026,))
        self.assertEqual(
            uy.build_unsupported_year_warning(2025),
            "UnsupportedYearWarning: Dataset is strictly locked to the 2026 snapshot. Year 2025 "
            "is not available. This is not missing or incomplete data: the warehouse holds a "
            "single-year 2026 snapshot and no rows for any other year, so any result shown here "
            "describes 2026 rather than 2025.",
        )

    def test_a_held_edition_is_not_warned_about_once_there_are_two(self) -> None:
        # The bug a `year != DEFAULT_RANKING_YEAR` check would ship: after a 2025
        # ingest it would tell a user the 2025 rows in front of them do not exist.
        self._with_editions((2026, 2025))
        self.assertEqual(uy.unsupported_year_warnings(context={"year": 2025}), [])
        self.assertEqual(uy.unsupported_year_warnings(user_input="QS 2025 rankings"), [])

        warning = uy.unsupported_year_warnings(context={"year": 2024})
        self.assertEqual(len(warning), 1)
        self.assertTrue(warning[0].startswith(uy.UNSUPPORTED_YEAR_WARNING_CODE))
        self.assertIn("2025 and 2026", warning[0])
        self.assertNotIn("single-year", warning[0])


class _StubRankingTools:
    """Returns a fixed page without touching PostgreSQL."""

    def __init__(self) -> None:
        self.seen_context: dict[str, Any] | None = None

    def list_rankings(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        self.seen_context = context
        return {"items": [], "summary": "0 rows", "metadata": {"total": 0}}


class _StubToolRouter:
    def __init__(self) -> None:
        self.ranking_tools = _StubRankingTools()
        self.recommendation_tools = None
        self.university_tools = None


class _NoGenerationPolicy(WebAgentPolicy):
    """Keeps the engine test offline: no LLM call, no retrieval, no stores."""

    allow_generation = False


def _engine() -> WebAgentEngine:
    return WebAgentEngine(tool_router=_StubToolRouter(), policy=_NoGenerationPolicy())


def _request(**kwargs: Any) -> TaskRequest:
    payload: dict[str, Any] = {
        "task_id": "t-1",
        "mode": "web",
        "kind": "data_query",
        "user_input": "list rankings",
    }
    payload.update(kwargs)
    return TaskRequest(**payload)


class TestEngineAttachesTheWarning(unittest.TestCase):
    def test_an_unheld_context_year_warns_without_failing_the_task(self) -> None:
        response = _engine().execute(_request(context={"year": UNHELD}))

        # Still a successful read: the rows shown are real, they simply
        # describe a different year from the one asked for -- and now say so.
        self.assertEqual(response.status, "success")
        self.assertTrue(
            any(UNSUPPORTED_YEAR_WARNING_CODE in w for w in response.warnings),
            f"no unsupported-year warning in {response.warnings!r}",
        )

    def test_year_in_the_prompt_warns_too(self) -> None:
        response = _engine().execute(_request(user_input=f"QS {UNHELD} rankings please"))
        self.assertTrue(any(UNSUPPORTED_YEAR_WARNING_CODE in w for w in response.warnings))

    def test_dataset_year_request_is_unchanged(self) -> None:
        response = _engine().execute(
            _request(
                context={"year": DATASET_YEAR},
                user_input=f"list the {DATASET_YEAR} rankings",
            )
        )
        self.assertEqual(response.status, "success")
        self.assertEqual(response.warnings, [])
        self.assertEqual(response.data.get("type"), "query")

    def test_request_without_a_year_is_unchanged(self) -> None:
        response = _engine().execute(_request(context={"country": "Taiwan"}))
        self.assertEqual(response.status, "success")
        self.assertEqual(response.warnings, [])

    def test_every_branch_goes_through_the_same_funnel(self) -> None:
        # _respond is the one place every branch of execute() lands, the
        # rejected one included, so an unknown kind still discloses the year.
        response = _engine().execute(
            _request(kind="dev_refinement", context={"rankingYear": UNHELD})
        )
        self.assertEqual(response.status, "rejected")
        self.assertTrue(any(UNSUPPORTED_YEAR_WARNING_CODE in w for w in response.warnings))

    def test_warning_is_not_repeated(self) -> None:
        request = _request(context={"year": UNHELD}, user_input=f"and what about {UNHELD}?")
        response = _engine().execute(request)
        coded = [w for w in response.warnings if UNSUPPORTED_YEAR_WARNING_CODE in w]
        self.assertEqual(len(coded), 1)


if __name__ == "__main__":
    unittest.main()
