"""Cross-edition forecast: the pair construction, the publication-timing rule, and the committed experiment.

Fast, no database, no MATLAB. The construction is tested on small frames whose answers can be worked
out by hand; the committed export and the committed MATLAB artifacts are tested against each other.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from ranking_ml.evaluation.check_cross_edition_parity import DEFAULT_MATLAB_DIR, compare
from ranking_ml.features.cross_edition import (
    AVAILABLE,
    DEFAULT_CSV,
    OPEN_FACTOR,
    band_midpoint,
    build_pairs,
    deterministic_metrics,
    feature_matrix,
    interval_error,
    load_ranks,
    ols_predict,
)


def ranks(rows: list[tuple]) -> pd.DataFrame:
    """(uid, year, source, lo, hi) -> the export's columns."""
    return pd.DataFrame(
        [{"canonical_university_id": u, "canonical_slug": f"u{u}", "year": y, "source": s, "rank_lo": lo,
          "rank_hi": hi, "printed": "", "source_kind": "live"} for u, y, s, lo, hi in rows]
    )


class TestBandMidpoint:
    def test_an_exact_rank_is_its_own_midpoint(self):
        assert band_midpoint([85], [85])[0] == 85

    def test_a_band_uses_the_geometric_midpoint(self):
        assert band_midpoint([201], [800])[0] == pytest.approx(np.sqrt(201 * 800))

    def test_an_open_ended_band_uses_the_stated_convention(self):
        assert band_midpoint([1401], [np.nan])[0] == pytest.approx(1401 * OPEN_FACTOR)


class TestIntervalError:
    def test_a_prediction_inside_the_printed_band_has_no_error(self):
        assert interval_error(np.log10([250.0]), np.array([201.0]), np.array([300.0]))[0] == 0

    def test_outside_it_the_error_is_the_log_distance_to_the_nearest_edge(self):
        e = interval_error(np.log10([100.0, 600.0]), np.array([201.0, 201.0]), np.array([300.0, 300.0]))
        assert e[0] == pytest.approx(np.log10(201 / 100))
        assert e[1] == pytest.approx(np.log10(600 / 300))

    def test_an_open_ended_band_is_hit_by_anything_beyond_its_lower_bound(self):
        assert interval_error(np.log10([5000.0]), np.array([1401.0]), np.array([np.nan]))[0] == 0
        assert interval_error(np.log10([700.0]), np.array([1401.0]), np.array([np.nan]))[0] > 0


class TestPairs:
    def test_only_consecutive_editions_make_a_pair(self):
        pairs = build_pairs(ranks([
            (1, 2018, "THE", 10, 10), (1, 2019, "THE", 12, 12),   # consecutive
            (2, 2018, "THE", 50, 50), (2, 2020, "THE", 60, 60),   # a gap: no pair
        ]))
        assert len(pairs) == 1
        assert pairs.iloc[0]["uid"] == 1 and pairs.iloc[0]["yearT"] == 2018 and pairs.iloc[0]["yearTarget"] == 2019

    def test_a_university_ranked_in_only_one_of_two_editions_has_no_pair(self):
        assert len(build_pairs(ranks([(1, 2018, "ARWU", 30, 30)]))) == 0

    def test_features_come_from_edition_t_and_the_target_from_t_plus_one(self):
        pairs = build_pairs(ranks([(1, 2018, "ARWU", 101, 150), (1, 2019, "ARWU", 151, 200)]))
        row = pairs.iloc[0]
        assert (row["ownLo"], row["ownHi"]) == (101, 150)
        assert (row["tgtLo"], row["tgtHi"]) == (151, 200)

    def test_the_previous_edition_is_the_one_before_t(self):
        pairs = build_pairs(ranks([
            (1, 2017, "THE", 40, 40), (1, 2018, "THE", 45, 45), (1, 2019, "THE", 50, 50),
        ]))
        first, second = pairs.sort_values("yearT").iloc[0], pairs.sort_values("yearT").iloc[1]
        assert np.isnan(first["prevLo"])      # nothing before 2017
        assert second["prevLo"] == 40         # 2017, for the 2018 -> 2019 pair

    def test_an_open_ended_band_is_flagged_and_gets_the_convention_midpoint(self):
        row = build_pairs(ranks([(1, 2018, "QS", 1401, np.nan), (1, 2019, "QS", 1401, np.nan)])).iloc[0]
        assert bool(row["ownOpen"]) and bool(row["tgtOpen"])
        assert row["ownMid"] == pytest.approx(1401 * OPEN_FACTOR)


class TestPublicationTiming:
    """QS edition T+1 appears in June of year T; ARWU edition T in August of year T, after it."""

    ROWS = [
        (1, 2018, "QS", 100, 100), (1, 2019, "QS", 110, 110),
        (1, 2018, "THE", 90, 90), (1, 2018, "ARWU", 80, 80),
    ]

    def test_a_qs_target_does_not_see_arwu_published_after_it(self):
        row = build_pairs(ranks(self.ROWS)).query("source == 'QS'").iloc[0]
        seen = {row["other1"]: row["other1Lo"], row["other2"]: row["other2Lo"]}
        assert seen["THE"] == 90
        assert np.isnan(seen["ARWU"])

    def test_a_the_or_arwu_target_sees_both_other_sources(self):
        rows = [(1, 2018, "THE", 90, 90), (1, 2019, "THE", 95, 95), (1, 2018, "QS", 100, 100),
                (1, 2018, "ARWU", 80, 80), (1, 2019, "ARWU", 85, 85)]
        pairs = build_pairs(ranks(rows))
        the = pairs.query("source == 'THE'").iloc[0]
        assert {the["other1Lo"], the["other2Lo"]} == {100, 80}
        arwu = pairs.query("source == 'ARWU'").iloc[0]
        assert {arwu["other1Lo"], arwu["other2Lo"]} == {100, 90}

    def test_the_table_says_what_the_docstring_says(self):
        assert AVAILABLE["QS"] == frozenset({"THE"})
        assert "QS" in AVAILABLE["THE"] and "ARWU" in AVAILABLE["THE"]


class TestLeastSquares:
    def test_it_recovers_an_exact_linear_relationship(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(200, 3))
        y = 2.0 + x @ np.array([1.0, -0.5, 0.25])
        assert ols_predict(x, y, x[:5]) == pytest.approx(y[:5], abs=1e-9)

    def test_a_constant_column_is_dropped_not_extrapolated(self):
        rng = np.random.default_rng(1)
        x = np.column_stack([rng.normal(size=100), np.zeros(100)])
        y = 1.0 + 3.0 * x[:, 0]
        test = np.array([[0.5, 100.0]])
        assert ols_predict(x, y, test)[0] == pytest.approx(1.0 + 3.0 * 0.5)

    def test_of_two_identical_columns_only_the_first_is_used(self):
        # The QS-2020 case: the imputed "previous rank" equals the own rank for every training pair.
        rng = np.random.default_rng(2)
        a = rng.normal(size=100)
        x = np.column_stack([a, a])
        y = 4.0 * a
        test = np.array([[1.0, 5.0]])            # the second column differs at test time
        assert ols_predict(x, y, test)[0] == pytest.approx(4.0)

    def test_features_are_finite_and_flag_what_was_imputed(self):
        pairs = build_pairs(ranks([(1, 2018, "THE", 40, 40), (1, 2019, "THE", 45, 45)]))
        x = feature_matrix(pairs)
        assert np.isfinite(x).all()
        assert x[0, 4] == 0.0                    # no previous edition
        assert x[0, 6] == 0.0 and x[0, 8] == 0.0 # no QS, no ARWU


class TestTheCommittedExperiment:
    def test_the_export_is_the_one_its_metadata_describes(self):
        meta = json.loads(DEFAULT_CSV.with_suffix(".meta.json").read_text(encoding="utf-8"))
        assert hashlib.sha256(DEFAULT_CSV.read_bytes()).hexdigest() == meta["csv_sha256"]
        assert meta["rows"] == len(load_ranks())

    def test_matlab_and_python_agree_on_the_committed_artifacts(self):
        assert compare(DEFAULT_MATLAB_DIR, DEFAULT_CSV) == []

    def test_the_matlab_run_used_the_committed_export(self):
        run = json.loads((DEFAULT_MATLAB_DIR / "forecast_run.json").read_text(encoding="utf-8"))
        meta = json.loads(DEFAULT_CSV.with_suffix(".meta.json").read_text(encoding="utf-8"))
        assert run["data_sha256"] == meta["csv_sha256"]

    def test_every_model_is_scored_on_the_same_rows(self):
        metrics = pd.read_csv(DEFAULT_MATLAB_DIR / "forecast_metrics.csv", dtype={"test": str})
        assert (metrics.groupby(["source", "test", "stratum"])["n"].nunique() == 1).all()

    def test_no_test_edition_precedes_the_training_data_it_needs(self):
        splits = pd.read_csv(DEFAULT_MATLAB_DIR / "forecast_splits.csv")
        assert (splits["nTrain"] >= 200).all()
        assert (splits["testYear"] >= 2020).all()

    def test_the_deterministic_rows_are_reproducible(self):
        pairs = build_pairs(load_ranks())
        a = deterministic_metrics(pairs)
        b = deterministic_metrics(pairs)
        pd.testing.assert_frame_equal(a, b)
