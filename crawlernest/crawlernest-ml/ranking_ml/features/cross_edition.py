"""Consecutive-edition rank pairs, and the persistence baseline scored against the printed band.

The Python half of ``matlab/build_forecast_pairs.m`` and of the deterministic part of
``matlab/run_cross_edition_forecast.m``. The two are independent implementations of the same
definitions: this one exists so that the numbers the MATLAB experiment's conclusions are measured
against -- how many pairs there are, how well "no change" does, and what ordinary least squares on
the features gets -- are not the product of a single program that nobody has checked. The boosted
model is not reproduced here: an ensemble fitted by two different libraries agrees only to within
sampling noise, which is a real claim but not one a 1e-9 check can make. See
``ranking_ml.evaluation.check_cross_edition_parity``.

## What a rank is

A source prints an interval, not a number: "201-210", "=196", "1401+". ``rank_lo`` and ``rank_hi``
are that interval (``rank_hi`` is NaN for an open-ended band). Features keep the lower bound, the
geometric midpoint of the band, and whether it was open. The midpoint of an open-ended band is
``OPEN_FACTOR`` times its lower bound -- a convention, not a measurement.

## What may be a feature: publication timing

"Edition T" is not the same moment for every source (see ``AVAILABLE``). A feature published after the
target is not a forecast input, so a QS target does not see ARWU's edition T.

## Who is in it

Only universities the source ranks in both of two consecutive editions. A university that enters or
leaves a list has no pair, so this is about movement among universities that stay listed, and the
lists grow while it happens.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CSV = _REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases" / "cross_edition_ranks.csv"

SOURCES: tuple[str, ...] = ("QS", "THE", "ARWU")
OPEN_FACTOR = 1.25
TEST_FROM = 2020
MIN_TRAIN = 200
STRATA: tuple[str, ...] = ("all", "exact_at_t", "banded_at_t")
#: The models whose numbers are deterministic functions of the export, so two implementations can be held to
#: the same figures: persistence, persistence shifted by the training drift, and ordinary least squares.
MODELS: tuple[str, ...] = ("persist_mid", "persist_lo", "persist_drift", "linear_own", "linear")
OLS_MODELS: frozenset[str] = frozenset({"linear_own", "linear"})
OWN_COLUMNS = slice(0, 3)  # feature_matrix: own lower bound, own midpoint, open-ended flag


#: Which sources' edition T may be a feature for a source-s target at T+1. QS edition T appears in June of
#: year T-1 (from 2018), THE edition T in October of year T-1, ARWU edition T in August of year T. ARWU T is
#: published after QS T+1, so it cannot be an input for a QS forecast however it is labelled.
AVAILABLE: dict[str, frozenset[str]] = {
    "QS": frozenset({"THE"}),
    "THE": frozenset({"QS", "ARWU"}),
    "ARWU": frozenset({"QS", "THE"}),
}


def load_ranks(path: Path = DEFAULT_CSV) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"source": str, "printed": str})
    if frame[["canonical_university_id", "year", "source"]].duplicated().any():
        raise ValueError("more than one row for a university, source and edition")
    if (frame["rank_lo"] < 1).any() or frame["rank_lo"].isna().any():
        raise ValueError("rank_lo must be positive in every row")
    bounded = frame["rank_hi"].notna()
    if (frame.loc[bounded, "rank_hi"] < frame.loc[bounded, "rank_lo"]).any():
        raise ValueError("a row has rank_hi below rank_lo")
    return frame


def band_midpoint(lo: pd.Series | np.ndarray, hi: pd.Series | np.ndarray) -> np.ndarray:
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    mid = np.sqrt(lo * hi)
    open_ended = np.isnan(hi)
    mid[open_ended] = lo[open_ended] * OPEN_FACTOR
    return mid


def build_pairs(ranks: pd.DataFrame) -> pd.DataFrame:
    """One row per (university, source, edition T) ranked by the source at T and at T+1."""
    blocks = []
    by_source = {s: ranks[ranks["source"] == s].set_index(["canonical_university_id", "year"]) for s in SOURCES}
    for source in SOURCES:
        frame = by_source[source]
        others = [s for s in SOURCES if s != source]
        keys = frame.index.to_frame(index=False)
        nxt = frame.copy()
        nxt.index = pd.MultiIndex.from_arrays([nxt.index.get_level_values(0), nxt.index.get_level_values(1) - 1])
        both = frame.join(nxt[["rank_lo", "rank_hi"]], how="inner", rsuffix="_tgt")
        prev = frame["rank_lo"].copy()
        prev.index = pd.MultiIndex.from_arrays([prev.index.get_level_values(0), prev.index.get_level_values(1) + 1])
        out = pd.DataFrame(index=both.index)
        out["source"] = source
        out["uid"] = both.index.get_level_values(0)
        out["yearT"] = both.index.get_level_values(1)
        out["yearTarget"] = out["yearT"] + 1
        out["ownLo"] = both["rank_lo"].to_numpy()
        out["ownHi"] = both["rank_hi"].to_numpy()
        out["ownOpen"] = np.isnan(out["ownHi"].to_numpy())
        out["ownMid"] = band_midpoint(out["ownLo"], out["ownHi"])
        out["prevLo"] = prev.reindex(both.index).to_numpy()
        for slot, name in enumerate(others, start=1):
            out[f"other{slot}"] = name
            values = by_source[name]["rank_lo"].reindex(both.index).to_numpy()
            out[f"other{slot}Lo"] = values if name in AVAILABLE[source] else np.full(len(values), np.nan)
        out["tgtLo"] = both["rank_lo_tgt"].to_numpy()
        out["tgtHi"] = both["rank_hi_tgt"].to_numpy()
        out["tgtOpen"] = np.isnan(out["tgtHi"].to_numpy())
        out["tgtMid"] = band_midpoint(out["tgtLo"], out["tgtHi"])
        blocks.append(out.reset_index(drop=True))
    pairs = pd.concat(blocks, ignore_index=True)
    assert (pairs["yearTarget"] == pairs["yearT"] + 1).all()
    return pairs


def interval_error(pred_log10: np.ndarray, tgt_lo: np.ndarray, tgt_hi: np.ndarray) -> np.ndarray:
    """Distance in log10 rank from the prediction to the printed band; zero inside it."""
    lo = np.log10(tgt_lo)
    hi = np.log10(tgt_hi)  # NaN stays NaN
    hi = np.where(np.isnan(hi), np.inf, hi)
    return np.maximum(0.0, np.maximum(lo - pred_log10, pred_log10 - hi))


def feature_matrix(pairs: pd.DataFrame) -> np.ndarray:
    """Log-rank features known at edition T, missing values imputed and flagged (as ``feature_matrix`` in MATLAB)."""
    l_own_lo = np.log10(pairs["ownLo"].to_numpy())
    l_own_mid = np.log10(pairs["ownMid"].to_numpy())
    has_prev = np.isfinite(pairs["prevLo"].to_numpy())
    l_prev = np.where(has_prev, np.log10(np.where(has_prev, pairs["prevLo"].to_numpy(), 1.0)), l_own_lo)
    columns = [l_own_lo, l_own_mid, pairs["ownOpen"].to_numpy().astype(float), l_prev, has_prev.astype(float)]
    for slot in (1, 2):
        values = pairs[f"other{slot}Lo"].to_numpy()
        has = np.isfinite(values)
        columns.append(np.where(has, np.log10(np.where(has, values, 1.0)), l_own_mid))
        columns.append(has.astype(float))
    return np.column_stack(columns)


def ols_predict(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray) -> np.ndarray:
    """Ordinary least squares with an intercept, dropping columns the training data cannot identify.

    A column is kept only if it adds something to the intercept and the columns kept before it. Some are
    constant or collinear in a small training window (for QS in 2020 no training pair has an earlier edition,
    so the imputed "previous rank" column equals the own-rank column exactly), and which of two collinear
    columns a library drops is its own choice. The rule is the same one ``ols_fit_predict`` applies in MATLAB.
    """
    n = len(x_train)
    basis = np.ones((n, 1)) / np.sqrt(n)
    keep: list[int] = []
    for j in range(x_train.shape[1]):
        v = x_train[:, j]
        r = v - basis @ (basis.T @ v)
        if np.linalg.norm(r) > 1e-9 * max(1.0, np.linalg.norm(v)):
            keep.append(j)
            basis = np.column_stack([basis, r / np.linalg.norm(r)])
    design = np.column_stack([np.ones(n), x_train[:, keep]])
    beta, *_ = np.linalg.lstsq(design, y_train, rcond=None)
    return np.column_stack([np.ones(len(x_test)), x_test[:, keep]]) @ beta


def eligible_test_years(pairs: pd.DataFrame, source: str, test_from: int = TEST_FROM, min_train: int = MIN_TRAIN) -> list[int]:
    sub = pairs[pairs["source"] == source]
    years = sorted(int(y) for y in sub["yearTarget"].unique() if y >= test_from)
    return [y for y in years if (sub["yearTarget"] < y).sum() >= min_train and (sub["yearTarget"] == y).any()]


def _metric_row(source: str, test: str, model: str, stratum: str, err: np.ndarray, pred: np.ndarray, mid: np.ndarray) -> dict:
    return {
        "source": source, "test": test, "model": model, "stratum": stratum, "n": int(err.size),
        "meanIntervalErr": float(err.mean()), "hitRate": float((err < 1e-12).mean()),
        "meanAbsLogErrMid": float(np.abs(pred - np.log10(mid)).mean()),
    }


def deterministic_metrics(pairs: pd.DataFrame, test_from: int = TEST_FROM, min_train: int = MIN_TRAIN) -> pd.DataFrame:
    """The experiment's deterministic rows, per source, test edition (expanding window), stratum, and pooled."""
    rows: list[dict] = []
    for source in SOURCES:
        sub = pairs[pairs["source"] == source]
        pooled: dict[str, dict[str, list[np.ndarray]]] = {m: {"err": [], "pred": [], "mid": [], "exact": []} for m in MODELS}
        for year in eligible_test_years(pairs, source, test_from, min_train):
            train = sub[sub["yearTarget"] < year]
            test = sub[sub["yearTarget"] == year]
            assert (train["yearT"] < year).all() and (test["yearTarget"] == year).all()
            exact = (~test["ownOpen"].to_numpy()) & (test["ownLo"].to_numpy() == test["ownHi"].to_numpy())
            masks = {"all": np.ones(len(test), bool), "exact_at_t": exact, "banded_at_t": ~exact}
            y_train = np.log10(train["tgtMid"].to_numpy())
            drift = float(np.mean(y_train - np.log10(train["ownMid"].to_numpy())))
            x_train, x_test = feature_matrix(train), feature_matrix(test)
            preds = {
                "persist_mid": np.log10(test["ownMid"].to_numpy()),
                "persist_lo": np.log10(test["ownLo"].to_numpy()),
                "persist_drift": np.log10(test["ownMid"].to_numpy()) + drift,
                "linear_own": ols_predict(x_train[:, OWN_COLUMNS], y_train, x_test[:, OWN_COLUMNS]),
                "linear": ols_predict(x_train, y_train, x_test),
            }
            mid = test["tgtMid"].to_numpy()
            for model, pred in preds.items():
                err = interval_error(pred, test["tgtLo"].to_numpy(), test["tgtHi"].to_numpy())
                for stratum, mask in masks.items():
                    if mask.any():
                        rows.append(_metric_row(source, str(year), model, stratum, err[mask], pred[mask], mid[mask]))
                pooled[model]["err"].append(err)
                pooled[model]["pred"].append(pred)
                pooled[model]["mid"].append(mid)
                pooled[model]["exact"].append(exact)
        for model in MODELS:
            if not pooled[model]["err"]:
                continue
            err = np.concatenate(pooled[model]["err"])
            pred = np.concatenate(pooled[model]["pred"])
            mid = np.concatenate(pooled[model]["mid"])
            exact = np.concatenate(pooled[model]["exact"])
            for stratum, mask in {"all": np.ones(err.size, bool), "exact_at_t": exact, "banded_at_t": ~exact}.items():
                if mask.any():
                    rows.append(_metric_row(source, "pooled", model, stratum, err[mask], pred[mask], mid[mask]))
    return pd.DataFrame(rows)
