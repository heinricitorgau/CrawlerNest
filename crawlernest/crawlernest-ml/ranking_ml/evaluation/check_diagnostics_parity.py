"""Hold ``plot_disagreement_diagnostics.m`` against scikit-learn.

This port draws three panels and its whole reason for existing is that they are
the same three panels ``plot_diagnostics`` draws in
``ranking_ml/training/train_disagreement.py``. It reimplements, by hand,
``roc_auc_score``, ``average_precision_score``, ``brier_score_loss`` and
``calibration_curve(strategy="quantile")`` -- two of them as local helpers whose
docstrings make specific claims about matching sklearn down to the tie handling
and the quantile convention. Nothing checked those claims.

``check_matlab_parity`` cannot: it diffs a committed artifact against a fresh
Python run, and this port's only output is a PNG. So the port emits the numbers
behind the panels (``StatsCSV=``) and this module recomputes them with sklearn.

The obstacle that keeps ``train_disagreement_classifier.m`` out of CI -- a fold
split whose RNG cannot be aligned with scikit-learn's -- does not apply here.
Given a fixed ``(y, proba)`` there is no model and no RNG, so the two
implementations must agree exactly, and 1e-9 is a real assertion rather than a
negotiated tolerance.

The fixture
-----------
``tests/fixtures/diagnostics_fixture.csv`` is 112 rows built to break the
parts most likely to be wrong:

* 80 distinct probabilities spread over (0, 1) -- the ordinary path;
* three blocks of ten tied probabilities, at 0.15, 0.42 and 0.73. Ties are not
  exotic: any boosted model emits them, and the QS disagreement model is
  boosted. All three landed exactly on an interior quantile edge, which is
  precisely where a binning convention shows;
* the endpoints 0.0 and 1.0 exactly, which are where an off-by-one in the edge
  handling drops a row on the floor.

That fixture earned its keep immediately. The calibration helper binned
``[lower, upper)`` where sklearn's ``np.searchsorted(edges[1:-1], proba)`` bins
``(lower, upper]``; on production data the edges are interpolated between order
statistics and sit on no observation, so the difference was invisible, but on
the fixture it moved six of ten bins and one observed frequency by 0.28.

    python -m ranking_ml.evaluation.check_diagnostics_parity \\
        --stats /tmp/matlab_fresh/cross_source_matlab/diagnostics_stats.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ARTIFACTS = (
    _REPO_ROOT / "crawlernest" / "crawlernest-ml" / "artifacts" / "cross_source_matlab"
)
DEFAULT_FIXTURE = (
    _REPO_ROOT
    / "crawlernest"
    / "crawlernest-ml"
    / "tests"
    / "fixtures"
    / "diagnostics_fixture.csv"
)
DEFAULT_STATS = _ARTIFACTS / "diagnostics_stats.csv"

#: The panel-3 bin count, fixed in the .m call and in the Python plotter.
N_BINS = 10

#: Both sides read the same doubles from the same CSV and do arithmetic no
#: deeper than a few hundred flops, so anything above float noise is a genuine
#: difference in method.
DEFAULT_TOLERANCE = 1e-9


def read_fixture(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or "y" not in rows[0] or "proba" not in rows[0]:
        raise SystemExit(f"{path}: expected columns 'y' and 'proba'")
    y = np.array([float(row["y"]) for row in rows])
    proba = np.array([float(row["proba"]) for row in rows])
    return y, proba


def read_stats(path: Path) -> dict[str, np.ndarray]:
    """The long-form CSV the port writes, back into scalars and curves.

    Index 0 marks a scalar; 1..k are the k-th point of a curve, in bin order.
    """
    collected: dict[str, list[tuple[int, float]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"metric", "index", "value"}
        if reader.fieldnames is None or not expected.issubset(reader.fieldnames):
            raise SystemExit(
                f"{path}: expected columns {sorted(expected)}, found {reader.fieldnames}"
            )
        for row in reader:
            collected.setdefault(row["metric"], []).append(
                (int(row["index"]), float(row["value"]))
            )
    return {
        name: np.array([value for _, value in sorted(points)])
        for name, points in collected.items()
    }


def fixture_still_bites(proba: np.ndarray) -> Optional[str]:
    """Is the fixture still exercising the edge cases it was built for?

    Regenerating it would change both sides at once, so parity would keep
    passing while quietly testing less. This asserts the three properties the
    fixture exists to provide.
    """
    edges = np.percentile(proba, np.linspace(0, 1, N_BINS + 1) * 100)
    on_edge = int(np.isin(proba, edges[1:-1]).sum())
    problems = []
    if on_edge == 0:
        problems.append(
            "no row sits exactly on an interior quantile edge, so the binning "
            "convention is no longer being tested"
        )
    if len(np.unique(proba)) == len(proba):
        problems.append("no tied probabilities, so tie collapsing is not being tested")
    if not (proba == 0.0).any() or not (proba == 1.0).any():
        problems.append("the exact endpoints 0.0 and 1.0 are not both present")
    return "; ".join(problems) if problems else None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare plot_disagreement_diagnostics.m's numbers against scikit-learn.",
    )
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = parser.parse_args(argv)

    for path, what in ((args.fixture, "fixture"), (args.stats, "stats")):
        if not path.is_file():
            raise SystemExit(
                f"{path}: {what} not found. Run plot_disagreement_diagnostics with "
                "StatsCSV= pointed here first."
            )

    y, proba = read_fixture(args.fixture)
    matlab = read_stats(args.stats)

    weakened = fixture_still_bites(proba)
    if weakened:
        print(f"FAIL -- the fixture no longer covers what it was built for: {weakened}")
        print()
        print(
            "A fixture regenerated without these properties makes this check pass "
            "on data that cannot fail it. Restore the committed fixture, or extend "
            "it rather than replacing it."
        )
        return 1

    observed, predicted = calibration_curve(
        y, proba, n_bins=N_BINS, strategy="quantile"
    )
    expected = {
        "n": np.array([float(len(y))]),
        "positive_rate": np.array([float(y.mean())]),
        "roc_auc": np.array([float(roc_auc_score(y, proba))]),
        "average_precision": np.array([float(average_precision_score(y, proba))]),
        "brier": np.array([float(brier_score_loss(y, proba))]),
        "calibration_predicted": predicted,
        "calibration_observed": observed,
    }

    print(f"fixture  {args.fixture}")
    print(f"stats    {args.stats}")
    print(
        f"{len(y)} rows, {int(y.sum())} positive, "
        f"{len(np.unique(proba))} distinct probabilities"
    )
    print()
    print(f"{'metric':<24}{'MATLAB':>14}{'sklearn':>14}{'max |diff|':>14}")

    problems: list[str] = []
    for name, want in expected.items():
        got = matlab.get(name)
        if got is None:
            problems.append(f"{name}: the port wrote no such metric")
            print(f"{name:<24}{'--':>14}{'--':>14}{'missing':>14}")
            continue
        if got.shape != want.shape:
            problems.append(
                f"{name}: the port wrote {got.size} value(s), sklearn has {want.size} "
                "-- a different number of populated bins is a binning difference, "
                "not a rounding one"
            )
            print(f"{name:<24}{got.size:>14}{want.size:>14}{'length':>14}")
            continue
        diff = float(np.max(np.abs(got - want)))
        lead = f"{got[0]:.9f}" if got.size == 1 else f"[{got.size} pts]"
        rhs = f"{want[0]:.9f}" if want.size == 1 else f"[{want.size} pts]"
        print(f"{name:<24}{lead:>14}{rhs:>14}{diff:>14.2e}")
        if diff > args.tolerance:
            problems.append(f"{name}: differs by {diff:.3e}, above {args.tolerance:.0e}")

    print()
    if problems:
        print(f"FAIL -- {len(problems)} disagreement(s):")
        for problem in problems:
            print(f"  - {problem}")
        print()
        print(
            "The port and sklearn were given identical (y, proba), so there is no "
            "RNG and no fold split to blame. One of the two implementations is "
            "wrong about how the metric is defined."
        )
        return 1

    print(f"PASS -- all {len(expected)} agree with scikit-learn within {args.tolerance:.0e}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
