"""Rank delta: the arithmetic, and the cases where the arithmetic may not be done.

The warehouse holds one year, so the most important test here is the dullest:
with today's dataset, every delta is withheld as ``single_year_dataset``, and
that follows from ``DATASET_YEAR`` rather than from a literal.

Institution lineage is pinned against the two mergers the warehouse actually
holds, with the canonical ids they resolve to.

The rest pins the rules a second year will need on the day it arrives. The
band cases are drawn from the rank strings actually stored in
``metadata.raw_row.rank`` -- ARWU's "101-150", THE's "1001–1200" with an en dash
and its "=98" ties, and the open "1501+" -- because 743 of 838 ARWU rows and
nearly all THE rows are one of those, not a plain position.
"""

from __future__ import annotations

import unittest

import re
from pathlib import Path

from crawlernest.core import institution_lineage as il
from crawlernest.core import rank_delta as rd
from crawlernest.core.dataset import DATASET_YEAR
from crawlernest.core.institution_lineage import LineageEvent, lineage_boundary
from crawlernest.core.rank_delta import (
    DIRECTION_DOWN,
    DIRECTION_INDETERMINATE,
    DIRECTION_UNCHANGED,
    DIRECTION_UP,
    REASON_BANDED,
    REASON_ENTITY_CHANGED,
    REASON_NO_CURRENT_ROW,
    REASON_NO_PRIOR_ROW,
    REASON_SINGLE_YEAR_DATASET,
    REASON_SUSPICIOUS_MERGE,
    RankBand,
    RankObservation,
    compute_rank_delta,
    parse_rank_band,
    stable_source_identity,
)

BOTH_YEARS = (2025, 2026)


def _obs(year: int, rank: str | int | None, *, source: str = "QS", **kwargs) -> RankObservation:
    return RankObservation(year=year, source=source, band=parse_rank_band(rank), **kwargs)


def _compute(current, prior, *, canonical_university_id: int = 1, lineage=(), **kwargs):
    """compute_rank_delta for a university with no lineage events, unless told otherwise."""
    return compute_rank_delta(
        current,
        prior,
        canonical_university_id=canonical_university_id,
        lineage=lineage,
        **kwargs,
    )


def _delta(current_rank, prior_rank, *, source: str = "QS", **kwargs):
    return _compute(
        _obs(2026, current_rank, source=source),
        _obs(2025, prior_rank, source=source),
        prior_year=2025,
        ingested_years=BOTH_YEARS,
        **kwargs,
    )


class TestParseRankBand(unittest.TestCase):
    def test_exact_positions_and_ties(self) -> None:
        self.assertEqual(parse_rank_band("14"), RankBand(14, 14))
        self.assertEqual(parse_rank_band(14), RankBand(14, 14))
        # THE writes ties with a leading "=". It is still one position.
        self.assertEqual(parse_rank_band("=98"), RankBand(98, 98))

    def test_bands_with_either_dash(self) -> None:
        self.assertEqual(parse_rank_band("101-150"), RankBand(101, 150))
        # THE's stored strings use an en dash, which a hyphen-only parser misses.
        self.assertEqual(parse_rank_band("1001–1200"), RankBand(1001, 1200))

    def test_open_ended_band(self) -> None:
        band = parse_rank_band("1501+")
        self.assertEqual(band, RankBand(1501, None))
        self.assertFalse(band.is_exact)

    def test_unparseable_input_is_none_not_an_error(self) -> None:
        for value in (None, "", "n/a", "0", 0, -3, "150-101", True, "rank 12"):
            with self.subTest(value=value):
                self.assertIsNone(parse_rank_band(value))


class TestStableSourceIdentity(unittest.TestCase):
    def test_arwu_ids_survive_the_year_boundary(self) -> None:
        # The real format: every one of the 867 ARWU ids embeds the year.
        self.assertEqual(
            stable_source_identity("arwu:2026:aalto-university"),
            stable_source_identity("arwu:2025:aalto-university"),
        )

    def test_subject_ids_lose_only_the_year(self) -> None:
        self.assertEqual(
            stable_source_identity("qs:subject:computer-science:2026:mit"),
            "qs:subject:computer-science:mit",
        )

    def test_year_free_ids_pass_through(self) -> None:
        self.assertEqual(
            stable_source_identity("/universities/massachusetts-institute-technology-mit"),
            "/universities/massachusetts-institute-technology-mit",
        )
        self.assertEqual(stable_source_identity("468"), "468")
        self.assertIsNone(stable_source_identity(None))


class TestTodaysSingleYearDataset(unittest.TestCase):
    def test_every_delta_is_withheld_today(self) -> None:
        delta = _compute(
            _obs(DATASET_YEAR, 10),
            _obs(DATASET_YEAR - 1, 12),
            prior_year=DATASET_YEAR - 1,
        )

        self.assertEqual(delta.reason, REASON_SINGLE_YEAR_DATASET)
        self.assertIsNone(delta.rank_delta)
        self.assertIsNone(delta.delta_min)
        self.assertIsNone(delta.delta_max)
        self.assertIsNone(delta.direction)

    def test_the_default_follows_the_dataset_constant(self) -> None:
        # Pinned to core.dataset, not to a literal, so ingesting a second year
        # is what turns deltas on -- nothing else has to remember to.
        original = rd.compute_rank_delta.__kwdefaults__["ingested_years"]
        self.assertEqual(tuple(original), (DATASET_YEAR,))


class TestExactDelta(unittest.TestCase):
    def test_sign_is_current_minus_prior(self) -> None:
        delta = _delta(15, 20)

        self.assertEqual(delta.rank_delta, -5)
        self.assertEqual((delta.delta_min, delta.delta_max), (-5, -5))
        self.assertIsNone(delta.reason)

    def test_a_smaller_rank_number_reads_as_up(self) -> None:
        # The inversion people get backwards: -5 is a move towards #1.
        self.assertEqual(_delta(15, 20).direction, DIRECTION_UP)
        self.assertEqual(_delta(25, 20).direction, DIRECTION_DOWN)
        self.assertEqual(_delta(20, 20).direction, DIRECTION_UNCHANGED)
        self.assertEqual(_delta(20, 20).rank_delta, 0)

    def test_ties_are_exact(self) -> None:
        delta = _delta("=98", "=101", source="THE")

        self.assertEqual(delta.rank_delta, -3)
        self.assertIsNone(delta.reason)


class TestBandedDelta(unittest.TestCase):
    def test_bands_give_an_interval_never_a_number(self) -> None:
        delta = _delta("151-200", "201-250", source="THE")

        self.assertIsNone(delta.rank_delta)
        self.assertEqual(delta.reason, REASON_BANDED)
        self.assertEqual((delta.delta_min, delta.delta_max), (-99, -1))
        # Every point in [-99, -1] is a move up, so the direction is known even
        # though the size is not.
        self.assertEqual(delta.direction, DIRECTION_UP)

    def test_same_band_both_years_says_nothing(self) -> None:
        # The case lower-bound subtraction reports as "unchanged".
        delta = _delta("201-250", "201-250", source="ARWU")

        self.assertEqual((delta.delta_min, delta.delta_max), (-49, 49))
        self.assertEqual(delta.direction, DIRECTION_INDETERMINATE)
        self.assertIsNone(delta.rank_delta)

    def test_exact_into_a_band_that_touches_it_is_indeterminate(self) -> None:
        # 200 -> "200-250": could be unchanged, could be 50 down.
        delta = _delta("200-250", 200)

        self.assertEqual((delta.delta_min, delta.delta_max), (0, 50))
        self.assertEqual(delta.direction, DIRECTION_INDETERMINATE)

    def test_open_ended_prior_band(self) -> None:
        # From "1501+" to "1201-1300": the low side is unbounded, but the high
        # side (1300 - 1501 = -201) already settles the direction.
        delta = _delta("1201-1300", "1501+", source="THE")

        self.assertIsNone(delta.delta_min)
        self.assertEqual(delta.delta_max, -201)
        self.assertEqual(delta.direction, DIRECTION_UP)

    def test_open_ended_current_band(self) -> None:
        delta = _delta("1501+", "1201-1300", source="THE")

        self.assertEqual(delta.delta_min, 201)
        self.assertIsNone(delta.delta_max)
        self.assertEqual(delta.direction, DIRECTION_DOWN)


class TestWithheldDeltas(unittest.TestCase):
    def test_no_prior_row_is_our_gap(self) -> None:
        delta = _compute(
            _obs(2026, 40), None, prior_year=2025, ingested_years=BOTH_YEARS
        )

        self.assertEqual(delta.reason, REASON_NO_PRIOR_ROW)
        self.assertIsNone(delta.direction)

    def test_no_current_row(self) -> None:
        delta = _delta(None, 40)

        self.assertEqual(delta.reason, REASON_NO_CURRENT_ROW)

    def test_a_different_source_entity_withholds(self) -> None:
        delta = _compute(
            _obs(2026, 30, source_entity_id="/universities/new-name"),
            _obs(2025, 35, source_entity_id="/universities/old-name"),
            prior_year=2025,
            ingested_years=BOTH_YEARS,
        )

        self.assertEqual(delta.reason, REASON_ENTITY_CHANGED)
        self.assertIsNone(delta.rank_delta)

    def test_arwu_year_in_the_id_is_not_an_entity_change(self) -> None:
        # Without stable_source_identity every ARWU delta would land here.
        delta = _compute(
            _obs(2026, 40, source="ARWU", source_entity_id="arwu:2026:aalto-university"),
            _obs(2025, 44, source="ARWU", source_entity_id="arwu:2025:aalto-university"),
            prior_year=2025,
            ingested_years=BOTH_YEARS,
        )

        self.assertEqual(delta.rank_delta, -4)
        self.assertIsNone(delta.reason)

    def test_suspicious_merge_in_either_year_withholds(self) -> None:
        for current_flag, prior_flag in ((True, False), (False, True)):
            with self.subTest(current=current_flag, prior=prior_flag):
                delta = _compute(
                    _obs(2026, 30, source="ARWU", suspicious_merge=current_flag),
                    _obs(2025, 35, source="ARWU", suspicious_merge=prior_flag),
                    prior_year=2025,
                    ingested_years=BOTH_YEARS,
                )
                self.assertEqual(delta.reason, REASON_SUSPICIOUS_MERGE)


class TestRefusedComparisons(unittest.TestCase):
    def test_cross_source_comparison_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            _compute(
                _obs(2026, 10, source="QS"),
                _obs(2025, 12, source="THE"),
                prior_year=2025,
                ingested_years=BOTH_YEARS,
            )

    def test_prior_must_precede_current(self) -> None:
        for prior_year in (2026, 2027):
            with self.subTest(prior_year=prior_year):
                with self.assertRaises(ValueError):
                    _compute(_obs(2026, 10), None, prior_year=prior_year)

    def test_prior_observation_must_match_prior_year(self) -> None:
        with self.assertRaises(ValueError):
            _compute(
                _obs(2026, 10),
                _obs(2024, 12),
                prior_year=2025,
                ingested_years=BOTH_YEARS,
            )


#: Canonical records as they are in the warehouse on 2026-09-13: the 2026
#: "Institute of Science Tokyo" rows resolve to the Tokyo Tech record, and the
#: 2026 "Adelaide University" rows to the University of Adelaide record.
TOKYO_TECH, TMDU = 85, 668
ADELAIDE, UNISA = 82, 339
SCIENCE_TOKYO_MERGER = LineageEvent(TMDU, TOKYO_TECH, 2024, "merger")
ADELAIDE_MERGER = LineageEvent(UNISA, ADELAIDE, 2026, "merger")
LINEAGE = (SCIENCE_TOKYO_MERGER, ADELAIDE_MERGER)


class TestInstitutionLineageWithholds(unittest.TestCase):
    """A merger that kept its source ids passes every identity check; lineage does not."""

    def _across(self, canonical_id: int, prior_year: int = 2025, current_year: int = 2026, **obs):
        return _compute(
            _obs(current_year, 40, source="ARWU", **obs),
            _obs(prior_year, 44, source="ARWU", **obs),
            prior_year=prior_year,
            canonical_university_id=canonical_id,
            lineage=LINEAGE,
            ingested_years=(prior_year, current_year),
        )

    def test_the_continuing_record_of_a_merger_is_withheld(self) -> None:
        # Same ARWU slug both years, so without lineage this would be "-4, up".
        delta = self._across(TOKYO_TECH, source_entity_id="arwu:tokyo-institute-of-technology")

        self.assertEqual(REASON_ENTITY_CHANGED, delta.reason)
        self.assertIsNone(delta.rank_delta)
        self.assertIsNone(delta.direction)
        self.assertIsNone(delta.delta_min)

    def test_the_absorbed_record_is_withheld_too(self) -> None:
        self.assertEqual(REASON_ENTITY_CHANGED, self._across(TMDU).reason)

    def test_an_unrelated_university_is_untouched(self) -> None:
        delta = self._across(12345)

        self.assertIsNone(delta.reason)
        self.assertEqual(-4, delta.rank_delta)

    def test_the_window_reaches_one_edition_label_back(self) -> None:
        # Science Tokyo took effect in 2024. The 2025 editions predate it in
        # practice, so 2025 -> 2026 crosses it; 2026 -> 2027 compares two
        # post-merger editions and does not.
        self.assertEqual(REASON_ENTITY_CHANGED, self._across(TOKYO_TECH, 2025, 2026).reason)
        self.assertIsNone(self._across(TOKYO_TECH, 2026, 2027).reason)
        # Adelaide took effect on 2026-01-01. A year cannot say whether an event
        # fell before or after an edition went to press, so both comparisons whose
        # widened window contains 2026 are withheld: 2026 -> 2027 and 2027 -> 2028.
        # The second is in fact sound. Over-withholding is the chosen error.
        self.assertEqual(REASON_ENTITY_CHANGED, self._across(ADELAIDE, 2026, 2027).reason)
        self.assertEqual(REASON_ENTITY_CHANGED, self._across(ADELAIDE, 2027, 2028).reason)
        self.assertIsNone(self._across(ADELAIDE, 2028, 2029).reason)

    def test_lineage_is_reported_before_a_missing_row(self) -> None:
        # "We hold no prior row" would blame our coverage for what is a merger.
        delta = _compute(
            _obs(2026, 40),
            None,
            prior_year=2025,
            canonical_university_id=TOKYO_TECH,
            lineage=LINEAGE,
            ingested_years=BOTH_YEARS,
        )
        self.assertEqual(REASON_ENTITY_CHANGED, delta.reason)

    def test_a_single_held_edition_still_reports_the_dataset_reason(self) -> None:
        delta = _compute(
            _obs(DATASET_YEAR, 40),
            _obs(DATASET_YEAR - 1, 44),
            prior_year=DATASET_YEAR - 1,
            canonical_university_id=TOKYO_TECH,
            lineage=LINEAGE,
        )
        self.assertEqual(REASON_SINGLE_YEAR_DATASET, delta.reason)

    def test_a_record_whose_institution_changed_in_place(self) -> None:
        rename = LineageEvent(TOKYO_TECH, TOKYO_TECH, 2024, "rename")
        self.assertIsNotNone(
            lineage_boundary(TOKYO_TECH, prior_year=2025, current_year=2026, lineage=(rename,))
        )

    def test_lineage_cannot_be_left_out(self) -> None:
        # No default: an omitted lineage check would look exactly like a
        # university that never merged.
        with self.assertRaises(TypeError):
            compute_rank_delta(_obs(2026, 10), _obs(2025, 12), prior_year=2025, ingested_years=BOTH_YEARS)

    def test_unknown_kinds_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            LineageEvent(1, 2, 2024, "acquisition")


class TestJavaAgreesOnTheRule(unittest.TestCase):
    """clawer.service.InstitutionLineage and RankComparisonPolicy restate this in Java."""

    JAVA = Path(__file__).resolve().parents[1] / "servise_for_java" / "src" / "main" / "java" / "clawer" / "service"

    def test_reason_codes_match(self) -> None:
        policy = (self.JAVA / "RankComparisonPolicy.java").read_text(encoding="utf-8")
        for name, value in (
            ("REASON_SINGLE_YEAR_DATASET", REASON_SINGLE_YEAR_DATASET),
            ("REASON_ENTITY_CHANGED", REASON_ENTITY_CHANGED),
        ):
            with self.subTest(name=name):
                self.assertIn(f'{name} = "{value}";', policy)

    def test_edition_lag_and_kinds_match(self) -> None:
        lineage = (self.JAVA / "InstitutionLineage.java").read_text(encoding="utf-8")
        self.assertIn(f"EDITION_LAG_YEARS = {il.EDITION_LAG_YEARS};", lineage)
        kinds = set(re.findall(r'"(\w+)"', re.search(r"KINDS = Set\.of\(([^)]*)\)", lineage).group(1)))
        self.assertEqual(set(il.KINDS), kinds)

    def test_schema_allows_exactly_these_kinds(self) -> None:
        ddl = (
            Path(__file__).resolve().parents[1] / "crawlernest-schema" / "institution_lineage_postgresql.sql"
        ).read_text(encoding="utf-8")
        kinds = set(re.findall(r"'(\w+)'", re.search(r"kind IN \(([^)]*)\)", ddl).group(1)))
        self.assertEqual(set(il.KINDS), kinds)


if __name__ == "__main__":
    unittest.main()
