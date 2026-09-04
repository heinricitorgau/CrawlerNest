"""Feature-layer tests: fast, no database, no training.

These guard the assumptions every model in the module rests on. If the snapshot
is re-crawled and one of these fails, the metrics gate downstream is measuring
something other than what it measured last time -- so these run first.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ranking_ml.evaluation.baselines import normalised_coefficients, published_weight_prediction
from ranking_ml.features.build_features import (
    _to_float,
    _to_rank,
    build_feature_matrix,
    load_feature_matrix,
    missingness_report,
)
from ranking_ml.features.cross_source import normalise_name
from ranking_ml.features.regions import REGION_ORDER, region_for, unmapped_countries
from ranking_ml.features.schema import (
    QS_INDICATORS,
    QS_PUBLISHED_WEIGHTS,
    TARGET_LABEL,
    validate_contract,
)
from ranking_ml.models.support import SupportFlagger


@pytest.fixture(scope="module")
def matrix():
    return load_feature_matrix()


# ── the contract itself ──────────────────────────────────────────────────────

def test_published_weights_agree_with_the_indicator_list():
    validate_contract()
    assert set(QS_PUBLISHED_WEIGHTS) == set(QS_INDICATORS)
    assert math.isclose(sum(QS_PUBLISHED_WEIGHTS.values()), 1.0, abs_tol=1e-9)


# ── value parsing ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("68", 68.0),
        ("68.5", 68.5),
        (68, 68.0),
        ("1,000", None),      # out of the 0-100 scale once the comma is stripped
        ("n/a", None),
        ("N/A", None),
        ("", None),
        (None, None),
        (True, None),         # a bool is not a score
        ("-5", None),         # below the published scale
        ("101", None),        # above it
        ("abc", None),
    ],
)
def test_to_float_rejects_everything_off_the_published_scale(raw, expected):
    result = _to_float(raw)
    if expected is None:
        assert math.isnan(result), f"{raw!r} should be missing, got {result}"
    else:
        assert result == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", 1.0),
        ("601", 601.0),
        ("801-850", 825.5),   # bands take their midpoint
        ("801–850", 825.5),   # en dash, as published
        ("=12", 12.0),        # tie marker
        ("1,501", 1501.0),
        ("", None),
        (None, None),
    ],
)
def test_to_rank_handles_the_published_formats(raw, expected):
    result = _to_rank(raw)
    if expected is None:
        assert math.isnan(result)
    else:
        assert result == expected


# ── region grouping ──────────────────────────────────────────────────────────

def test_every_country_in_the_snapshot_maps_to_an_explicit_region(matrix):
    stray = unmapped_countries(list(matrix.country))
    assert stray == [], (
        f"{len(stray)} country values have no region mapping and silently fell into "
        f"Unknown: {stray}. Add them to REGION_BY_COUNTRY."
    )


def test_unknown_region_is_the_fallback_not_a_crash():
    assert region_for("Atlantis") == "Unknown"
    assert region_for("") == "Unknown"
    assert region_for(None) == "Unknown"


def test_region_columns_are_stable_and_mutually_exclusive(matrix):
    region_columns = [c for c in matrix.X.columns if c.startswith("region=")]
    assert len(region_columns) == len(REGION_ORDER)
    # Exactly one region per row, or the one-hot block is not a one-hot block.
    assert (matrix.X[region_columns].sum(axis=1) == 1.0).all()


# ── the matrix ───────────────────────────────────────────────────────────────

def test_matrix_shape_and_label_split(matrix):
    # Counts for the 2026 snapshot re-crawled on 2026-09-02. The crawl before it
    # was taken with the pre-TLS-fix client and resolved a stale ranking id, so
    # it returned a different edition: 1,503 rows with the score published to
    # rank 600. These numbers move whenever the snapshot is refreshed, and are
    # asserted exactly so that a refresh has to be noticed and explained.
    assert len(matrix.X) == 1504
    assert list(matrix.X.columns[: len(QS_INDICATORS)]) == list(QS_INDICATORS)

    labelled = int(matrix.labelled_mask.sum())
    assert labelled == 700
    assert len(matrix.X) - labelled == 804

    # The split is exactly QS's publication cut-off, not an arbitrary threshold.
    assert matrix.rank[matrix.labelled_mask].max() == 700
    assert matrix.rank[~matrix.labelled_mask].min() == 701


def test_rank_is_not_among_the_features(matrix):
    """QS derives rank from the score, so a rank column would leak the target."""
    assert "rank" not in matrix.X.columns
    assert not any("rank" in column.lower() for column in matrix.X.columns)


def test_labelled_target_has_no_missing_values(matrix):
    _, y = matrix.labelled()
    assert y.notna().all()
    assert (y >= 0).all() and (y <= 100).all()


def test_missingness_is_reported_for_every_indicator(matrix):
    report = missingness_report(matrix)
    assert set(report.index) == set(QS_INDICATORS)
    # Known state of the 2026 snapshot: some gaps, but nothing close to unusable.
    assert report["missing_pct"].max() < 10.0


def test_empty_input_gives_an_empty_matrix_not_an_error():
    empty = build_feature_matrix([])
    assert len(empty.X) == 0
    assert list(empty.X.columns[: len(QS_INDICATORS)]) == list(QS_INDICATORS)


# ── baseline behaviour ───────────────────────────────────────────────────────

def test_published_weight_baseline_renormalises_instead_of_imputing():
    """A row missing an indicator is scored on what was published for it.

    Both rows below score 50 on every indicator they have. The second is missing
    one. Imputation would drag it toward some other institution's median;
    renormalisation leaves it at 50, which is what the published numbers say.
    """
    complete = {name: 50.0 for name in QS_INDICATORS}
    partial = dict(complete)
    partial["Sustainability Score"] = float("nan")

    frame = pd.DataFrame([complete, partial])
    predictions = published_weight_prediction(frame)

    assert predictions[0] == pytest.approx(50.0)
    assert predictions[1] == pytest.approx(50.0)


def test_published_weight_baseline_yields_nan_when_nothing_is_available():
    frame = pd.DataFrame([{name: float("nan") for name in QS_INDICATORS}])
    assert math.isnan(published_weight_prediction(frame)[0])


def test_normalised_coefficients_sum_to_one():
    coefficients = np.array([0.3, 0.15, 0.10, 0.20, 0.05, 0.05, 0.05, 0.05, 0.05]) * 7.0
    recovered = normalised_coefficients(coefficients)
    assert math.isclose(sum(recovered.values()), 1.0, abs_tol=1e-9)
    assert recovered["Academic Reputation"] == pytest.approx(0.30)


# ── support flag ─────────────────────────────────────────────────────────────

def test_support_threshold_covers_the_stated_share_of_training_data(matrix):
    X_lab, _ = matrix.labelled()
    flagger = SupportFlagger().fit(X_lab)

    supported = flagger.is_supported(X_lab)
    # The threshold is the 95th percentile of the training set's own distances,
    # so roughly that share of training rows must sit inside it.
    assert 0.93 <= supported.mean() <= 1.0


def test_unlabelled_rows_are_less_supported_than_training_rows(matrix):
    """The covariate shift found in the EDA must still be visible here.

    If this ever fails, either the snapshot changed or the support flag stopped
    measuring what it claims to.
    """
    X_lab, _ = matrix.labelled()
    flagger = SupportFlagger().fit(X_lab)
    assert flagger.report(X_lab, "train")["supported_pct"] > flagger.report(
        matrix.unlabelled(), "infer"
    )["supported_pct"]


# ── cross-source join key ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "left, right",
    [
        ("University of Oxford", "university of oxford"),
        ("Sun Yat-sen University", "Sun Yat sen University"),
        ("Massachusetts Institute of Technology (MIT)", "Massachusetts Institute of Technology MIT"),
    ],
)
def test_name_normalisation_collapses_punctuation_and_case(left, right):
    assert normalise_name(left) == normalise_name(right)


def test_name_normalisation_does_not_collapse_different_institutions():
    assert normalise_name("National Taiwan University") != normalise_name(
        "National Taiwan Normal University"
    )
