"""The caveat strings say the same thing in all four places, or this fails.

The root ``CLAUDE.md`` warns that caveat text lives in more than one place and
that changing one copy usually means changing all of them. That warning was
accurate and insufficient: two of the strings drifted anyway, and nothing
complained for as long as it took to notice by hand.

- The stale caveat named a fixed age ("RC-1 packaging", and "approximately 354
  hours ago" in Java). All three sources were re-ingested on 2026-09-04, so it
  was overstating the data's age by about two weeks.
- THE and ARWU were described as "not available at RC-1" while the warehouse
  held 1,637 THE and 838 ARWU ranks for 2026 and the API was serving them.

Java already anchored its estimate caveat to the explainability document
(``AnalyticsCaveatContractTest``). This does the same across all four copies at
once -- Python, Java, TypeScript, prose -- because a contract enforced on one
string and trusted on four others is how the four drifted.

Matching is exact substring, not fuzzy. A caveat that has been reworded in one
language is a different disclosure, which is the thing being guarded against.

A year-bearing caveat is a template, so for it the contract is on the template,
on the list of editions each language fills it from, and on the rule for joining
that list -- which ANALYTICS_EXPLAINABILITY.md states as a table every renderer
is tested against. What it renders for today's warehouse is pinned to the exact
sentence the constant used to hold.
"""

from __future__ import annotations


import re
import unittest
from pathlib import Path

from crawlernest.core.caveats import (
    ADMISSION_STALE_FETCHED_TEMPLATE,
    ADMISSION_STALE_UNDATED_TEMPLATE,
    CAVEAT_ARWU_PARTIAL,
    CAVEAT_IELTS_MISSING,
    admission_caveats,
    admission_stale_caveat,
    COMPOSITE_RANK_NOT_COMPARED_CAVEAT,
    CAVEAT_QS_STALE,
    CAVEAT_THE_PARTIAL,
    DISAGREEMENT_ESTIMATE_CAVEAT,
    ESTIMATED_VALUE_CAVEAT,
    RANK_CHANGE_CAVEAT,
    EDITION_SOURCE_COVERAGE_TEMPLATE,
    SNAPSHOT_CAVEAT_TEMPLATE,
    STANDARD_CAVEATS,
    MODEL_EDITION_MISSING_TEMPLATE,
    MODEL_NEVER_RUN_CAVEAT,
    UNSUPPORTED_ESTIMATE_CAVEAT,
    edition_caveats,
    edition_snapshot_caveat,
    edition_source_coverage_caveat,
    format_edition_years,
    model_edition_caveats,
    format_sources,
    snapshot_caveat,
)
from crawlernest.core.dataset import (
    DATASET_COVERAGE,
    DATASET_SOURCES,
    DATASET_YEAR,
    DATASET_YEARS,
    DEFAULT_RANKING_YEAR,
    sources_for_year,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPLAINABILITY_DOC = REPO_ROOT / "docs" / "analytics" / "ANALYTICS_EXPLAINABILITY.md"
ANALYTICS_SERVICE = (
    REPO_ROOT
    / "crawlernest" / "servise_for_java" / "src" / "main" / "java" / "clawer" / "service"
    / "AnalyticsService.java"
)
CAVEAT_MESSAGES_TS = (
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src" / "lib" / "caveatMessages.ts"
)
AGENT_SYSTEM_PROMPT_TS = (
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src" / "lib" / "agentSystemPrompt.ts"
)
DATASET_SCOPE_JAVA = ANALYTICS_SERVICE.with_name("DatasetScope.java")
DATASET_SCOPE_TS = (
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src" / "lib" / "datasetScope.ts"
)

#: The sentence CAVEAT_QS_STALE held as a literal before it became a template.
#: Rendering the template for the 2026-only warehouse must reproduce it byte for
#: byte, in every language; a template refactor that changes what users read is
#: not a refactor.
SNAPSHOT_CAVEAT_2026 = (
    "QS ranking data is a point-in-time snapshot of the 2026 published tables. "
    "Figures may not reflect rankings republished since this snapshot was ingested."
)

#: Every caveat that is still a constant in all four places.
CONSTANT_CAVEATS = (
    CAVEAT_THE_PARTIAL,
    CAVEAT_ARWU_PARTIAL,
    ESTIMATED_VALUE_CAVEAT,
    DISAGREEMENT_ESTIMATE_CAVEAT,
    UNSUPPORTED_ESTIMATE_CAVEAT,
    RANK_CHANGE_CAVEAT,
    COMPOSITE_RANK_NOT_COMPARED_CAVEAT,
    CAVEAT_IELTS_MISSING,
)

#: Templates that must be byte-identical in every language and in the doc.
TEMPLATE_CAVEATS = (
    SNAPSHOT_CAVEAT_TEMPLATE,
    EDITION_SOURCE_COVERAGE_TEMPLATE,
    ADMISSION_STALE_FETCHED_TEMPLATE,
    ADMISSION_STALE_UNDATED_TEMPLATE,
)


def documented_year_renderings(doc: str) -> list[tuple[tuple[int, ...], str]]:
    """The ``(editions, rendered)`` rows between the year-list-rendering markers."""
    block = doc.split("<!-- year-list-rendering:start -->", 1)[1].split(
        "<!-- year-list-rendering:end -->", 1
    )[0]
    rows: list[tuple[tuple[int, ...], str]] = []
    for line in block.strip().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or not cells[0][:1].isdigit():
            continue  # header and separator
        rows.append((tuple(int(y) for y in cells[0].split(",")), cells[1]))
    return rows

#: Live code paths only. `releases/` and `docs/demo/` describe the state of a
#: packaged demo at a point in the past, and "RC-1 packaging" is the correct
#: thing for a historical record to say.
#:
#: Python is absent deliberately: its caveats are checked as *values* below
#: rather than by reading source. Scanning prose for a phrase cannot tell a
#: disclosure from a comment explaining why that disclosure changed, and the
#: comments naming the old wording are the fix rather than the bug.
LIVE_CODE_ROOTS = (
    REPO_ROOT / "crawlernest" / "servise_for_java" / "src" / "main",
    REPO_ROOT / "crawlernest" / "crawlernest-web" / "src",
)

#: Claims that were true once and are now false. Matched case-insensitively
#: against live source, excluding the comments that explain the correction.
STALE_CLAIMS = (
    "last ingested at RC-1 packaging",
    "not available at RC-1",
    "354 hours",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestCaveatsAgreeAcrossLanguages(unittest.TestCase):
    def test_java_carries_every_python_caveat_verbatim(self) -> None:
        java = _read(ANALYTICS_SERVICE)
        for caveat in (*CONSTANT_CAVEATS, *TEMPLATE_CAVEATS):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(
                    caveat,
                    java,
                    "AnalyticsService.java and crawlernest/core/caveats.py disclose "
                    "different things; update whichever is wrong so they agree.",
                )

    def test_frontend_carries_every_python_caveat_verbatim(self) -> None:
        typescript = _read(CAVEAT_MESSAGES_TS)
        for caveat in (*CONSTANT_CAVEATS, *TEMPLATE_CAVEATS):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(caveat, typescript)

    def test_no_copy_still_writes_the_snapshot_year_out_as_a_constant(self) -> None:
        # The template is the only definition. A second, hand-rendered copy of
        # the sentence would be the drift this refactor removes.
        for path in (ANALYTICS_SERVICE, CAVEAT_MESSAGES_TS):
            with self.subTest(path=path.name):
                self.assertNotIn(SNAPSHOT_CAVEAT_2026, _read(path))

    def test_dataset_years_agree_across_languages(self) -> None:
        java = re.search(r"DATASET_YEARS\s*=\s*List\.of\(([^)]*)\)", _read(DATASET_SCOPE_JAVA))
        typescript = re.search(
            r"DATASET_YEARS\s*:\s*readonly number\[\]\s*=\s*\[([^\]]*)\]", _read(DATASET_SCOPE_TS)
        )
        self.assertIsNotNone(java, "DatasetScope.DATASET_YEARS not found")
        self.assertIsNotNone(typescript, "datasetScope.ts DATASET_YEARS not found")
        for label, match in (("Java", java), ("TypeScript", typescript)):
            with self.subTest(language=label):
                years = tuple(int(y) for y in match.group(1).split(",") if y.strip())
                self.assertEqual(DATASET_YEARS, years)


class TestYearBearingCaveatTemplates(unittest.TestCase):
    def test_2026_renders_the_sentence_the_constant_used_to_hold(self) -> None:
        self.assertEqual(SNAPSHOT_CAVEAT_2026, snapshot_caveat("QS", (2026,)))

    def test_todays_constant_renders_from_the_editions_qs_covers(self) -> None:
        # This asserted snapshot_caveat(DATASET_YEARS) until the 2015-2024 ARWU
        # release. The two lists were the same one then; they are not now, and
        # rendering QS over the union would name ten editions holding no QS row.
        # The sentence itself is unchanged -- the release made it true rather
        # than rewriting it, which is what the equality below pins.
        self.assertEqual(snapshot_caveat("QS", DATASET_COVERAGE["QS"]), CAVEAT_QS_STALE)
        self.assertNotIn("2024", CAVEAT_QS_STALE)

    def test_a_source_cannot_be_named_over_an_edition_it_does_not_cover(self) -> None:
        # The check that makes the false disclosure unwritable rather than merely
        # discouraged. Java and TypeScript raise on the same inputs.
        for source, years in (("QS", (2018,)), ("THE", (2015, 2026)), ("ARWU", (2014,))):
            with self.subTest(source=source, years=years):
                with self.assertRaises(ValueError):
                    snapshot_caveat(source, years)

    def test_an_edition_is_disclosed_with_the_sources_it_actually_holds(self) -> None:
        self.assertEqual(sources_for_year(2018), ("ARWU",))
        self.assertEqual(sources_for_year(2026), ("QS", "THE", "ARWU"))

        arwu_only = edition_snapshot_caveat(2018)
        self.assertTrue(arwu_only.startswith("ARWU ranking data"), arwu_only)
        self.assertNotIn("QS", arwu_only)

        # And an edition missing a source says so, in the negative ("or"), rather
        # than leaving a reader to infer it from an empty column.
        coverage = edition_source_coverage_caveat(2018)
        self.assertIn("The 2018 edition holds ARWU ranks only", coverage)
        self.assertIn("No QS or THE rank exists", coverage)
        self.assertIsNone(edition_source_coverage_caveat(2026))

    def test_source_lists_join_like_year_lists(self) -> None:
        self.assertEqual(format_sources(("ARWU",)), "ARWU")
        self.assertEqual(format_sources(("THE", "QS")), "QS and THE")
        self.assertEqual(format_sources(DATASET_SOURCES), "QS, THE and ARWU")
        self.assertEqual(format_sources(("THE", "QS"), "or"), "QS or THE")

    def test_dataset_coverage_agrees_across_languages(self) -> None:
        java = _read(DATASET_SCOPE_JAVA)
        typescript = _read(DATASET_SCOPE_TS)
        for source, years in DATASET_COVERAGE.items():
            rendered = ", ".join(str(year) for year in years)
            with self.subTest(language="Java", source=source):
                self.assertIn(f'"{source}", List.of({rendered})', java)
            with self.subTest(language="TypeScript", source=source):
                self.assertIn(f"{source}: [{rendered}]", typescript)

    def test_dataset_years_are_the_union_of_the_coverage_map(self) -> None:
        union = sorted({year for years in DATASET_COVERAGE.values() for year in years}, reverse=True)
        self.assertEqual(tuple(union), DATASET_YEARS)

    def test_the_doc_states_the_template_verbatim(self) -> None:
        self.assertIn(SNAPSHOT_CAVEAT_TEMPLATE, _read(EXPLAINABILITY_DOC))

    def test_year_lists_render_as_the_doc_specifies(self) -> None:
        rows = documented_year_renderings(_read(EXPLAINABILITY_DOC))
        self.assertGreaterEqual(len(rows), 3, "the rendering table lost its rows")
        for editions, rendered in rows:
            with self.subTest(editions=editions):
                self.assertEqual(rendered, format_edition_years(editions))

    def test_an_empty_edition_list_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            format_edition_years(())

    def test_dataset_years_are_well_formed(self) -> None:
        self.assertTrue(DATASET_YEARS, "the warehouse must hold at least one edition")
        self.assertEqual(len(set(DATASET_YEARS)), len(DATASET_YEARS))
        self.assertEqual(tuple(sorted(DATASET_YEARS, reverse=True)), DATASET_YEARS, "newest first")
        self.assertEqual(max(DATASET_YEARS), DEFAULT_RANKING_YEAR)
        self.assertEqual(DEFAULT_RANKING_YEAR, DATASET_YEAR, "the compatibility alias drifted")

    def test_frontend_agent_system_prompt_carries_dataset_constraints(self) -> None:
        """The rules a model is given about editions.

        This asserted the opposite until the 2015-2024 ARWU release: that the
        warehouse held one year, that the data was a "single-year snapshot", and
        that inferring any "cross-year trend" was forbidden. Each was correct for
        one edition and false for twelve, and the trend ban would have forbidden
        the capability this release exists to unlock.

        What replaces it is not permission to narrate movement. The repo already
        computes cross-edition movement under constraints -- rank_delta.py and
        SourceRankDelta compare one source's published ranks and decline when the
        rank is banded or the institution changed -- so the prompt states those
        same constraints rather than routing around them.
        """
        prompt = _read(AGENT_SYSTEM_PROMPT_TS)

        # Derived, not written: a year literal here could drift from the release.
        self.assertIn("export const DATASET_YEAR = DEFAULT_RANKING_YEAR;", prompt)
        self.assertNotIn(f"DATASET_YEAR = {DATASET_YEAR};", prompt)

        # The editions, and that coverage differs by source.
        self.assertIn("Dataset editions: the warehouse holds ${editions(DATASET_YEARS)}", prompt)
        self.assertIn("Coverage differs by source", prompt)
        self.assertIn("name no source for a year it does not cover", prompt)

        # Movement is reportable, but only the way the repo computes it.
        self.assertIn("only one source at a time", prompt)
        self.assertIn("Never compare composite or aggregated ranks between editions", prompt)
        self.assertIn("banded rank is a range, not a number", prompt)
        self.assertIn("merged, split or was renamed", prompt)

        # The claim a missing rank must never be turned into.
        self.assertIn("never means the source declines to rank it", prompt)

        # The old single-year rules must be gone, not merely outnumbered.
        for retired in ("single-year snapshot", "year after year", "has risen"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, prompt)

    def test_explainability_doc_carries_the_estimate_caveats(self) -> None:
        # The doc is the anchor AnalyticsCaveatContractTest already reads, so a
        # caveat that reaches a user must be documented in the same words.
        doc = _read(EXPLAINABILITY_DOC)
        for caveat in (
            CAVEAT_QS_STALE,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
            RANK_CHANGE_CAVEAT,
            COMPOSITE_RANK_NOT_COMPARED_CAVEAT,
        ):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(caveat, doc)

    def test_explainability_doc_carries_the_model_coverage_disclosure(self) -> None:
        """The doc's worked example is rendered by the code it documents.

        Asserted against ``model_edition_caveats`` rather than against the raw
        template, because the doc shows a reader the finished sentence. That
        makes a reworded template fail here, which is the point: the doc is the
        anchor the Java contract test reads.
        """
        doc = _read(EXPLAINABILITY_DOC)
        self.assertIn(model_edition_caveats(2018, [2026])[0], doc)
        self.assertIn(MODEL_NEVER_RUN_CAVEAT, doc)

    def test_model_never_run_caveat_matches_the_java_wording(self) -> None:
        # AnalyticsService answers an absent modelling layer inline rather than
        # from a constant. One wording either way -- the agent path and the API
        # must not describe the same empty database differently.
        self.assertIn(MODEL_NEVER_RUN_CAVEAT, _read(ANALYTICS_SERVICE))

    def test_model_coverage_disclosure_names_the_edition_asked_for(self) -> None:
        """Both halves of the conditional, and what makes the sentence honest.

        The template blames this platform for the gap, never the model: an
        unmodelled edition is a job nobody ran, not a finding that the edition
        resists estimation. Same rule the source-coverage caveats follow.
        """
        self.assertEqual([], model_edition_caveats(2026, [2026]))
        self.assertEqual([MODEL_NEVER_RUN_CAVEAT], model_edition_caveats(2026, []))

        sentence = model_edition_caveats(2018, [2026])[0]
        self.assertIn("2018 edition", sentence)
        self.assertIn("only been run over 2026", sentence)
        self.assertIn("gap in what this platform modelled", sentence)
        self.assertNotIn("{year}", sentence)
        self.assertNotIn("{editions}", sentence)

        # Newest first in prose is format_edition_years' job, not this one's.
        self.assertIn("2025 and 2026", model_edition_caveats(2018, [2026, 2025])[0])

    def test_explainability_doc_carries_the_admission_caveats(self) -> None:
        doc = _read(EXPLAINABILITY_DOC)
        for caveat in (CAVEAT_IELTS_MISSING, ADMISSION_STALE_FETCHED_TEMPLATE, ADMISSION_STALE_UNDATED_TEMPLATE):
            with self.subTest(caveat=caveat[:40]):
                self.assertIn(caveat, doc)

    def test_standard_set_is_the_three_source_caveats(self) -> None:
        self.assertEqual(
            list(STANDARD_CAVEATS),
            [CAVEAT_QS_STALE, CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL],
        )

    def test_a_single_edition_carries_only_what_that_edition_holds(self) -> None:
        # The release scope and the edition scope differ now, and a response about
        # one edition must use the second: STANDARD_CAVEATS opens with QS's
        # snapshot, which beside a 2018 table holding no QS rank is true of the
        # warehouse and useless to the reader.
        arwu_only = edition_caveats(2018)
        self.assertEqual(arwu_only[0], edition_snapshot_caveat(2018))
        self.assertIn(edition_source_coverage_caveat(2018), arwu_only)
        self.assertIn(CAVEAT_ARWU_PARTIAL, arwu_only)
        # No THE line: there is no THE row in 2018 for its coverage to be partial about.
        self.assertNotIn(CAVEAT_THE_PARTIAL, arwu_only)
        self.assertNotIn(CAVEAT_QS_STALE, arwu_only)

        every_source = edition_caveats(2026)
        self.assertEqual(
            list(every_source),
            [edition_snapshot_caveat(2026), CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL],
        )

    def test_java_and_typescript_compose_edition_caveats_the_same_way(self) -> None:
        # Each language composes the list from the same pieces; the pieces
        # themselves are already compared byte for byte above.
        java = _read(ANALYTICS_SERVICE)
        typescript = _read(CAVEAT_MESSAGES_TS)
        self.assertIn("public static List<String> editionCaveats(int year)", java)
        self.assertIn("export function editionCaveats(year: number): string[]", typescript)
        for source, guard in (("THE", "THE_PARTIAL_CAVEAT"), ("ARWU", "ARWU_PARTIAL_CAVEAT")):
            with self.subTest(source=source):
                self.assertIn(f'sources.contains("{source}")', java)
                self.assertIn(guard, java)
                self.assertIn(f'sources.includes("{source}")', typescript)


class TestAdmissionCaveats(unittest.TestCase):
    """The rule each language's renderer follows; the Java and TS ones are tested on the same cases."""

    def test_a_recorded_fetch_date_is_named_as_the_fetch_date(self) -> None:
        from datetime import date

        self.assertEqual(
            ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", "2026-03-01"),
            admission_stale_caveat(
                fetch_dates_recorded=True, oldest_fetched_on=date(2026, 3, 1), oldest_extracted_on=date(2026, 8, 22)
            ),
        )

    def test_an_unrecorded_fetch_is_never_passed_off_as_the_extraction_date(self) -> None:
        from datetime import date

        caveat = admission_stale_caveat(
            fetch_dates_recorded=False, oldest_fetched_on=date(2026, 3, 1), oldest_extracted_on=date(2026, 8, 22)
        )
        self.assertEqual(ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", "2026-08-22"), caveat)
        self.assertIn("fetch date was not recorded", caveat)
        self.assertNotIn("fetched on", caveat)

    def test_no_admission_data_means_no_staleness_claim(self) -> None:
        self.assertIsNone(
            admission_stale_caveat(fetch_dates_recorded=True, oldest_fetched_on=None, oldest_extracted_on=None)
        )

    def test_a_timestamp_is_refused_so_every_language_names_the_same_utc_day(self) -> None:
        from datetime import datetime, timezone

        with self.assertRaises(TypeError):
            admission_stale_caveat(
                fetch_dates_recorded=True,
                oldest_fetched_on=datetime(2026, 3, 1, 23, 30, tzinfo=timezone.utc),
                oldest_extracted_on=None,
            )

    def test_admission_caveats_follow_the_summary_row(self) -> None:
        from datetime import date

        self.assertEqual([CAVEAT_IELTS_MISSING], admission_caveats(None))
        row = {"ielts_missing": True, "fetch_dates_recorded": False, "oldest_fetched_on": None,
               "oldest_extracted_on": date(2026, 8, 22)}
        caveats = admission_caveats(row)
        self.assertEqual(CAVEAT_IELTS_MISSING, caveats[0])
        self.assertIn("extracted on 2026-08-22", caveats[1])
        self.assertEqual(1, len(admission_caveats({**row, "ielts_missing": False})))

    def test_java_and_typescript_renderers_use_the_same_rule(self) -> None:
        # Source-level check that each renderer picks the fetched template only
        # when every date is recorded -- the behaviour is unit-tested in Java
        # (AdmissionCaveatsTest) and TypeScript (admissionCaveats.test.ts).
        self.assertIn("if (fetchDatesRecorded && oldestFetchedOn != null)", _read(ANALYTICS_SERVICE))
        self.assertIn("if (staleness.fetchDatesRecorded && staleness.oldestFetchedOn)", _read(CAVEAT_MESSAGES_TS))


class TestStaleClaimsAreGone(unittest.TestCase):
    """No live surface still asserts the things that stopped being true."""

    def test_no_python_caveat_value_repeats_a_stale_claim(self) -> None:
        # The values, not the source: what a user is shown is the only thing
        # that can be a false disclosure.
        for caveat in (
            *STANDARD_CAVEATS,
            ESTIMATED_VALUE_CAVEAT,
            DISAGREEMENT_ESTIMATE_CAVEAT,
            UNSUPPORTED_ESTIMATE_CAVEAT,
        ):
            for claim in STALE_CLAIMS:
                with self.subTest(caveat=caveat[:30], claim=claim):
                    self.assertNotIn(claim.lower(), caveat.lower())

    def test_no_java_or_frontend_surface_repeats_a_stale_claim(self) -> None:
        offenders: list[str] = []
        for root in LIVE_CODE_ROOTS:
            for path in root.rglob("*"):
                if path.suffix not in {".java", ".ts", ".tsx"} or not path.is_file():
                    continue
                for line in _read(path).splitlines():
                    # Javadoc and // comments recording *why* a string changed
                    # name the old wording on purpose.
                    if _is_comment(line):
                        continue
                    for claim in STALE_CLAIMS:
                        if claim.lower() in line.lower():
                            offenders.append(f"{path.relative_to(REPO_ROOT)}: {line.strip()[:90]}")
        self.assertEqual(
            offenders,
            [],
            "a live surface still claims data is unavailable or names a fixed data age",
        )

    def test_the_summary_generators_repeat_no_stale_claim(self) -> None:
        """The five report generators, which would re-emit into reports/.

        Each carried its own copy of the RC-1 posture, and every copy had gone
        false the same way. Worse, the copies were suppression lists -- their
        surrounding prose reads "expected, non-worsening, not an active
        incident" -- so a genuine THE outage would have been reported as an
        accepted condition. They now read from scripts/_release_posture.py.
        """
        generators = [
            REPO_ROOT / "scripts" / f"{name}.py"
            for name in (
                "build_maintenance_calm_summary",
                "build_maintenance_continuity_summary",
                "build_maintenance_steadiness_summary",
                "build_competition_demo_summary",
                "build_demo_readiness_summary",
            )
        ] + [REPO_ROOT / "scripts" / "build_demo_bundle.sh"]

        offenders: list[str] = []
        for path in generators:
            if not path.is_file():
                continue
            text = _read(path)
            for claim in (*STALE_CLAIMS, "unavailable (0)", "no ML model"):
                if claim.lower() in text.lower():
                    offenders.append(f"{path.name}: {claim}")
        self.assertEqual(offenders, [])

    def test_release_posture_values_carry_no_stale_claim(self) -> None:
        # The module the generators read from, checked as values -- its own
        # docstring quotes the old wording on purpose, to record what changed.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_release_posture", REPO_ROOT / "scripts" / "_release_posture.py"
        )
        assert spec and spec.loader
        posture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(posture)

        strings = [
            *posture.STABLE_CONDITIONS,
            *posture.SPOKEN_CAVEATS,
            *posture.WHAT_NOT_TO_CLAIM,
            *[f"{a} {b} {c}" for a, b, c in posture.DEGRADED_INDICATORS],
            *[f"{a} {b}" for a, b in posture.DEMO_CAVEATS],
        ]
        for value in strings:
            for claim in (*STALE_CLAIMS, "no ML model"):
                with self.subTest(value=value[:35], claim=claim):
                    self.assertNotIn(claim.lower(), value.lower())

        # The disclaimer that must survive: scoring is deterministic, and the
        # models do not rank anyone.
        self.assertTrue(
            any("deterministic" in c for c in posture.WHAT_NOT_TO_CLAIM),
            "the deterministic-scoring disclaimer was dropped",
        )

    def test_partial_coverage_caveats_do_not_claim_absence(self) -> None:
        for caveat in (CAVEAT_THE_PARTIAL, CAVEAT_ARWU_PARTIAL):
            with self.subTest(caveat=caveat[:30]):
                self.assertNotIn("is not available", caveat)
                self.assertIn("covers part of this dataset", caveat)
                # The distinction the whole caveat exists to make.
                self.assertIn("does not mean", caveat.lower())


def _is_comment(line: str) -> bool:
    """True for a Java/TS comment line, which may quote the old wording."""
    return line.strip().startswith(("*", "//", "/*"))


if __name__ == "__main__":
    unittest.main()
