"""The agent's ML read path, and the property that makes it safe to have.

An estimate is the easiest thing in this system to state dishonestly: once
``20.4`` is in a sentence it looks exactly like a published score. Golden case
faith-105 is that failure recorded -- "QS scores University of Kragujevac at
20.4" over evidence where the 20.4 is a model output. Every number in it is
supported and the caveat is reproduced verbatim, so the faithfulness rules pass
it. ``provenance.check_provenance`` catches it, and only because the evidence
rows carry ``isEstimated``.

That is the load-bearing fact these tests exist for. The caveat matters, but a
caveat is text a model can reproduce and then contradict in the previous
sentence (faith-105 does exactly that). ``isEstimated`` is structured, so the
mechanical checker can act on it. Both travel with the value here, and
``test_stripping_is_estimated_disarms_the_guard`` demonstrates what is lost if
one stops.

Offline throughout: MlService is stubbed, so nothing here needs PostgreSQL.
"""

from __future__ import annotations

import unittest
from typing import Any

from crawlernest.agent.tools.ml_tools import EstimateEvidence, MlTools
from crawlernest.agent.web_agent.generation.provenance import check_provenance
from crawlernest.core.caveats import (
    DISAGREEMENT_ESTIMATE_CAVEAT,
    ESTIMATED_VALUE_CAVEAT,
    MODEL_NEVER_RUN_CAVEAT,
    UNSUPPORTED_ESTIMATE_CAVEAT,
    model_edition_caveats,
)
from crawlernest.core.dataset import DATASET_YEAR
from crawlernest.core.services.ml_service import (
    TARGET_DISAGREEMENT,
    TARGET_OVERALL_SCORE,
    TARGETS,
    MlPredictionQuery,
    MlService,
)

_SCORE_ROW = {
    "canonicalUniversityId": 4211,
    "universityName": "University of Kragujevac",
    "slug": "university-of-kragujevac",
    "country": "Serbia",
    "rankingYear": DATASET_YEAR,
    "target": TARGET_OVERALL_SCORE,
    "estimatedOverallScore": 20.4,
    "supportDistance": 0.31,
    "isSupported": True,
    "isEstimated": True,
    "modelName": "qs_overall_score_estimator",
    "modelVersion": "qs2026-64cd5521db7b",
}

_RISK_ROW = {
    "canonicalUniversityId": 4211,
    "universityName": "University of Kragujevac",
    "slug": "university-of-kragujevac",
    "country": "Serbia",
    "rankingYear": DATASET_YEAR,
    "target": TARGET_DISAGREEMENT,
    "disagreementProbability": 0.83,
    "supportDistance": 0.12,
    "isSupported": True,
    "isEstimated": True,
    "modelName": "qs_the_disagreement_classifier",
    "modelVersion": "qs2026-64cd5521db7b",
}


class StubService:
    """Stands in for MlService, recording the queries it was asked for.

    ``covered_years`` defaults to the one edition the real scoring job has been
    run over, so a stub built for any other test behaves like the deployment.
    """

    def __init__(
        self,
        rows_by_target: dict[str, list[dict[str, Any]]] | None = None,
        covered: tuple[int, ...] = (DATASET_YEAR,),
    ) -> None:
        self.rows_by_target = rows_by_target if rows_by_target is not None else {
            TARGET_OVERALL_SCORE: [dict(_SCORE_ROW)],
            TARGET_DISAGREEMENT: [dict(_RISK_ROW)],
        }
        self.queries: list[MlPredictionQuery] = []
        self.coverage_lookups = 0
        self._covered = covered

    def fetch(self, query: MlPredictionQuery) -> list[dict[str, Any]]:
        self.queries.append(query)
        return [dict(row) for row in self.rows_by_target.get(query.target, [])]

    def covered_years(self) -> tuple[int, ...]:
        self.coverage_lookups += 1
        return self._covered


class TestTargetsStaySeparate(unittest.TestCase):
    """A 0-100 score and a 0-1 probability must never share a field."""

    def test_unknown_target_is_rejected_before_any_query(self) -> None:
        with self.assertRaises(ValueError) as caught:
            MlService().fetch(MlPredictionQuery(target="qs_something_else"))
        self.assertIn("unknown modelling target", str(caught.exception))

    def test_each_target_surfaces_under_its_own_key(self) -> None:
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        scores = tools.estimated_overall_scores()
        risks = tools.disagreement_probabilities()

        self.assertIn("estimatedOverallScore", scores.items[0])
        self.assertNotIn("disagreementProbability", scores.items[0])
        self.assertIn("disagreementProbability", risks.items[0])
        self.assertNotIn("estimatedOverallScore", risks.items[0])

    def test_every_fetch_filters_on_a_target(self) -> None:
        stub = StubService()
        tools = MlTools(service=stub)  # type: ignore[arg-type]
        tools.estimated_overall_scores()
        tools.disagreement_probabilities()
        tools.annotate([{"canonicalUniversityId": 4211}])

        self.assertTrue(stub.queries)
        for query in stub.queries:
            self.assertIn(query.target, TARGETS)

    def test_python_and_java_agree_on_the_target_names(self) -> None:
        from pathlib import Path

        java = (
            Path(__file__).resolve().parents[2]
            / "crawlernest" / "servise_for_java" / "src" / "main" / "java" / "clawer"
            / "service" / "AnalyticsService.java"
        ).read_text(encoding="utf-8")
        for target in TARGETS:
            with self.subTest(target=target):
                self.assertIn(f'"{target}"', java)


class TestDisclosureTravelsWithTheValue(unittest.TestCase):
    def test_scores_always_carry_the_estimate_caveat(self) -> None:
        evidence = MlTools(service=StubService()).estimated_overall_scores()  # type: ignore[arg-type]
        self.assertIn(ESTIMATED_VALUE_CAVEAT, evidence.caveats)

    def test_disagreement_carries_both_caveats(self) -> None:
        # The general one does not cover the specific misreading: a probability
        # read as an observed conflict.
        evidence = MlTools(service=StubService()).disagreement_probabilities()  # type: ignore[arg-type]
        self.assertIn(ESTIMATED_VALUE_CAVEAT, evidence.caveats)
        self.assertIn(DISAGREEMENT_ESTIMATE_CAVEAT, evidence.caveats)

    def test_no_rows_means_no_caveat(self) -> None:
        # Conditional, not always-on: a disclosure that fires when it does not
        # apply teaches readers to skip the array.
        empty = StubService(rows_by_target={})
        evidence = MlTools(service=empty).estimated_overall_scores()  # type: ignore[arg-type]
        self.assertTrue(evidence.is_empty)
        self.assertEqual(evidence.caveats, [])

    def test_every_returned_row_declares_itself_an_estimate(self) -> None:
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        for evidence in (tools.estimated_overall_scores(), tools.disagreement_probabilities()):
            for item in evidence.items:
                self.assertIs(item["isEstimated"], True)
                self.assertIn("isSupported", item)

    def test_there_is_no_way_to_get_items_without_caveats(self) -> None:
        # Every public method returns the pair. A method handing back a bare
        # list is how the caveat gets left behind at the call site.
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        for method in (
            tools.estimated_overall_scores,
            tools.disagreement_probabilities,
        ):
            with self.subTest(method=method.__name__):
                self.assertIsInstance(method(), EstimateEvidence)
        self.assertIsInstance(tools.annotate([]), EstimateEvidence)


class TestSupportIsDisclosedNotJustCarried(unittest.TestCase):
    """The support flag reaches the reader, not only the row.

    ESTIMATED_VALUE_CAVEAT promises a support flag. On the live overall-score
    model that flag is false for 351 of 787 rows, and those rows sit
    systematically lower than the supported ones -- so describing the mechanism
    without ever saying it fired disclosed half of it.
    """

    @staticmethod
    def _unsupported_stub() -> "StubService":
        row = dict(_SCORE_ROW)
        row["isSupported"] = False
        return StubService(rows_by_target={TARGET_OVERALL_SCORE: [row]})

    def test_an_unsupported_estimate_says_so(self) -> None:
        tools = MlTools(service=self._unsupported_stub())  # type: ignore[arg-type]
        evidence = tools.estimated_overall_scores()
        self.assertIn(UNSUPPORTED_ESTIMATE_CAVEAT, evidence.caveats)
        self.assertIn(ESTIMATED_VALUE_CAVEAT, evidence.caveats)

    def test_supported_estimates_claim_no_limitation_they_lack(self) -> None:
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        self.assertNotIn(
            UNSUPPORTED_ESTIMATE_CAVEAT, tools.estimated_overall_scores().caveats
        )

    def test_one_unsupported_row_discloses_for_the_whole_response(self) -> None:
        supported = dict(_SCORE_ROW)
        unsupported = dict(_SCORE_ROW, canonicalUniversityId=99, isSupported=False)
        stub = StubService(rows_by_target={TARGET_OVERALL_SCORE: [supported, unsupported]})
        evidence = MlTools(service=stub).estimated_overall_scores()  # type: ignore[arg-type]
        self.assertIn(UNSUPPORTED_ESTIMATE_CAVEAT, evidence.caveats)

    def test_annotate_discloses_support_too(self) -> None:
        row = dict(_SCORE_ROW, isSupported=False)
        stub = StubService(rows_by_target={TARGET_OVERALL_SCORE: [row]})
        evidence = MlTools(service=stub).annotate(  # type: ignore[arg-type]
            [{"canonicalUniversityId": 4211, "aggregatedRank": 1201}]
        )
        self.assertIn(UNSUPPORTED_ESTIMATE_CAVEAT, evidence.caveats)
        self.assertIs(evidence.items[0]["isSupported"], False)

    def test_no_duplicate_estimate_caveat_when_both_targets_land(self) -> None:
        evidence = MlTools(service=StubService()).annotate(  # type: ignore[arg-type]
            [{"canonicalUniversityId": 4211}]
        )
        self.assertEqual(evidence.caveats.count(ESTIMATED_VALUE_CAVEAT), 1)


class TestAnnotateMergesOntoRankingRows(unittest.TestCase):
    def test_estimates_merge_and_keep_their_flags(self) -> None:
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        evidence = tools.annotate(
            [{"canonicalUniversityId": 4211, "universityName": "University of Kragujevac",
              "aggregatedRank": 1201}]
        )
        row = evidence.items[0]
        self.assertEqual(row["aggregatedRank"], 1201)
        self.assertEqual(row["estimatedOverallScore"], 20.4)
        self.assertEqual(row["disagreementProbability"], 0.83)
        self.assertIs(row["isEstimated"], True)
        self.assertIn(ESTIMATED_VALUE_CAVEAT, evidence.caveats)
        self.assertIn(DISAGREEMENT_ESTIMATE_CAVEAT, evidence.caveats)

    def test_rows_without_estimates_get_no_disclosure(self) -> None:
        empty = StubService(rows_by_target={})
        evidence = MlTools(service=empty).annotate(  # type: ignore[arg-type]
            [{"canonicalUniversityId": 99, "aggregatedRank": 12}]
        )
        self.assertEqual(evidence.caveats, [])
        self.assertNotIn("isEstimated", evidence.items[0])

    def test_rows_without_an_id_are_returned_untouched(self) -> None:
        tools = MlTools(service=StubService())  # type: ignore[arg-type]
        evidence = tools.annotate([{"universityName": "Somewhere", "aggregatedRank": 5}])
        self.assertEqual(evidence.items, [{"universityName": "Somewhere", "aggregatedRank": 5}])


class TestFaith105Guard(unittest.TestCase):
    """The estimate must stay catchable when a model credits it to QS.

    This is the whole point of the module, exercised through the real
    provenance rule rather than a restatement of it.
    """

    _CREDITED_TO_QS = (
        "QS scores University of Kragujevac at 20.4.\n\n" + ESTIMATED_VALUE_CAVEAT
    )

    def test_crediting_the_estimate_to_qs_is_flagged(self) -> None:
        evidence = MlTools(service=StubService()).estimated_overall_scores()  # type: ignore[arg-type]
        report = check_provenance(
            explanation=self._CREDITED_TO_QS,
            items=evidence.items,
            caveats=evidence.caveats,
        )
        self.assertFalse(report.sound)
        self.assertIn("estimate_credited_to_source", report.kinds)

    def test_stripping_is_estimated_disarms_the_guard(self) -> None:
        # Not a behaviour anyone wants -- a demonstration that the flag, not the
        # caveat, is what makes the sentence catchable. The caveat is present in
        # both cases; only this one goes unnoticed.
        evidence = MlTools(service=StubService()).estimated_overall_scores()  # type: ignore[arg-type]
        stripped = [
            {k: v for k, v in item.items() if k != "isEstimated"} for item in evidence.items
        ]
        report = check_provenance(
            explanation=self._CREDITED_TO_QS,
            items=stripped,
            caveats=evidence.caveats,
        )
        self.assertTrue(report.sound)

    def test_attributing_the_estimate_to_the_model_is_not_flagged(self) -> None:
        evidence = MlTools(service=StubService()).estimated_overall_scores()  # type: ignore[arg-type]
        report = check_provenance(
            explanation=(
                "CrawlerNest estimates an overall score of 20.4 for University of "
                "Kragujevac; QS publishes none.\n\n" + ESTIMATED_VALUE_CAVEAT
            ),
            items=evidence.items,
            caveats=evidence.caveats,
        )
        self.assertTrue(report.sound, f"false alarm: {report.kinds}")


class TestAnUnmodelledEditionSaysSo(unittest.TestCase):
    """An empty read for an edition nobody modelled must not answer with silence.

    Before the 2015-2024 ARWU release, ``resolve_ranking_year`` rejected 2018 and
    an agent asking for 2018 estimates got a refusal it could repeat to a user.
    Those editions are now held, so the request is valid, reaches the query and
    comes back with zero rows. Nothing about the response distinguishes it from
    "the model has no estimate for these universities" -- which is the honest
    answer for 2026 and a false one for 2018, where the scoring job never ran.

    So the disclosure is conditional on the edition rather than on the emptiness:
    the tests below assert both directions, because an always-on version would be
    claiming a limitation that 2026 does not have.
    """

    _UNHELD = 2018

    def test_an_unmodelled_edition_is_disclosed_as_a_platform_gap(self) -> None:
        stub = StubService(rows_by_target={})
        evidence = MlTools(service=stub).estimated_overall_scores(  # type: ignore[arg-type]
            year=self._UNHELD
        )

        self.assertTrue(evidence.is_empty)
        self.assertEqual(model_edition_caveats(self._UNHELD, [DATASET_YEAR]), evidence.caveats)
        sentence = evidence.caveats[0]
        self.assertIn(f"{self._UNHELD} edition", sentence)
        self.assertIn(str(DATASET_YEAR), sentence)
        # Our gap, never the model declining: the same attribution rule the
        # source-coverage caveats follow.
        self.assertIn("gap in what this platform modelled", sentence)

    def test_the_year_asked_for_is_the_year_queried(self) -> None:
        # Year isolation at the tool boundary: an unmodelled edition must not
        # quietly fall back to the modelled one and return 2026 rows.
        stub = StubService()
        MlTools(service=stub).estimated_overall_scores(year=self._UNHELD)  # type: ignore[arg-type]
        self.assertEqual([self._UNHELD], [query.year for query in stub.queries])

    def test_no_estimate_rows_are_invented_for_an_unmodelled_edition(self) -> None:
        stub = StubService(rows_by_target={})
        for evidence in (
            MlTools(service=stub).estimated_overall_scores(year=self._UNHELD),  # type: ignore[arg-type]
            MlTools(service=stub).disagreement_probabilities(year=self._UNHELD),  # type: ignore[arg-type]
        ):
            self.assertEqual([], evidence.items)
            # The value disclosures describe values in the response. There are
            # none, so they stay off and only the reason is carried.
            self.assertNotIn(ESTIMATED_VALUE_CAVEAT, evidence.caveats)
            self.assertNotIn(DISAGREEMENT_ESTIMATE_CAVEAT, evidence.caveats)
            self.assertNotIn(UNSUPPORTED_ESTIMATE_CAVEAT, evidence.caveats)

    def test_a_modelled_edition_with_no_estimate_still_says_nothing(self) -> None:
        # The other direction, and the reason this is not an always-on caveat: at
        # 2026 an empty result is a fact about these universities, not a gap in
        # what was modelled.
        stub = StubService(rows_by_target={})
        evidence = MlTools(service=stub).estimated_overall_scores(  # type: ignore[arg-type]
            year=DATASET_YEAR
        )
        self.assertTrue(evidence.is_empty)
        self.assertEqual([], evidence.caveats)

    def test_annotated_ranking_rows_carry_the_same_reason(self) -> None:
        # The path a 2018 rankings page takes: rows come back unannotated either
        # way, so silence here would read as "no estimate for these".
        stub = StubService(rows_by_target={})
        evidence = MlTools(service=stub).annotate(  # type: ignore[arg-type]
            [{"canonicalUniversityId": 4211, "aggregatedRank": 12}], year=self._UNHELD
        )
        self.assertEqual(model_edition_caveats(self._UNHELD, [DATASET_YEAR]), evidence.caveats)
        self.assertNotIn("isEstimated", evidence.items[0])
        # Asked once, not once per target: annotate forwards what the two
        # fetches already established about the edition.
        self.assertEqual(2, stub.coverage_lookups)

    def test_a_database_without_the_modelling_tables_says_that_instead(self) -> None:
        stub = StubService(rows_by_target={}, covered=())
        evidence = MlTools(service=stub).estimated_overall_scores(  # type: ignore[arg-type]
            year=DATASET_YEAR
        )
        self.assertEqual([MODEL_NEVER_RUN_CAVEAT], evidence.caveats)

    def test_a_populated_read_never_asks_about_coverage(self) -> None:
        # The staleness guard: the coverage lookup only happens where there is
        # nothing else to report, so a memoised answer could not go wrong -- and
        # the happy path pays for no extra query.
        stub = StubService()
        evidence = MlTools(service=stub).estimated_overall_scores()  # type: ignore[arg-type]
        self.assertFalse(evidence.is_empty)
        self.assertEqual(0, stub.coverage_lookups)


if __name__ == "__main__":
    unittest.main()
