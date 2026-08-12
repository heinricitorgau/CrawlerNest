"""Check the MATLAB EDA port against the Python one, number by number.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.evaluation.check_matlab_parity

Both implementations claim to compute the same three tables from the same
snapshot: correlation with the target, covariate shift, and missingness. Until
something compares them, "ported to MATLAB" is an assertion. Two implementations
that disagree are not a redundancy, they are a bug in one of them, and nobody
knows which.

## What this proves, and what it does not

It compares the **committed** MATLAB artifacts in ``artifacts/eda_matlab/``
against a **fresh** Python run. So:

- It catches the Python side drifting away from a verified reference.
- It catches a MATLAB re-run that produces different numbers.
- It does **not** catch someone editing the ``.m`` files and never re-running
  them: the CSVs would simply go stale, and stale files still match. Guarding
  that needs MATLAB on the runner, which is not a dependency worth adding here.

The tolerance is 1e-9. These are the same formulas over the same inputs, so
agreement should be near machine precision; anything looser would let a genuine
methodological difference pass as rounding.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ranking_ml.eda.run_eda import correlation_with_target, covariate_shift
from ranking_ml.features.build_features import load_feature_matrix, missingness_report

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ML_ROOT = _REPO_ROOT / "crawlernest" / "crawlernest-ml"
DEFAULT_MATLAB_DIR = _ML_ROOT / "artifacts" / "eda_matlab"

TOLERANCE = 1e-9

#: filename -> numeric columns to compare, keyed on the "indicator" column.
COMPARISONS: dict[str, tuple[str, ...]] = {
    "correlation_with_target.csv": ("pearson_r",),
    "covariate_shift.csv": ("labelled_mean", "unlabelled_mean", "standardised_gap"),
    "missingness.csv": ("missing", "missing_pct"),
}


def python_tables() -> dict[str, pd.DataFrame]:
    """Recompute the three tables from the snapshot, at full precision."""
    matrix = load_feature_matrix()
    missing = missingness_report(matrix).reset_index(names="indicator")
    return {
        "correlation_with_target.csv": correlation_with_target(matrix),
        "covariate_shift.csv": covariate_shift(matrix),
        "missingness.csv": missing,
    }


def compare(name: str, python: pd.DataFrame, matlab: pd.DataFrame, columns: tuple[str, ...]) -> list[str]:
    """Compare one table, returning failure messages."""
    failures: list[str] = []

    python_keys = set(python["indicator"])
    matlab_keys = set(matlab["indicator"])
    if python_keys != matlab_keys:
        only_python = sorted(python_keys - matlab_keys)
        only_matlab = sorted(matlab_keys - python_keys)
        failures.append(
            f"{name}: the two implementations do not cover the same indicators. "
            f"Python only: {only_python}. MATLAB only: {only_matlab}."
        )
        return failures

    merged = python.merge(matlab, on="indicator", suffixes=("_py", "_ml"))
    print(f"\n{name}  ({len(merged)} indicators)")
    print(f"  {'column':<20} {'max abs difference':>20}   verdict")

    for column in columns:
        difference = (merged[f"{column}_py"].astype(float) - merged[f"{column}_ml"].astype(float)).abs()
        worst = float(difference.max())
        ok = worst <= TOLERANCE
        print(f"  {column:<20} {worst:>20.3e}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            row = merged.loc[difference.idxmax()]
            failures.append(
                f"{name}: {column} differs by {worst:.3e} (tolerance {TOLERANCE:.0e}). "
                f"Worst at {row['indicator']!r}: Python {row[f'{column}_py']}, "
                f"MATLAB {row[f'{column}_ml']}."
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the MATLAB EDA port to the Python one.")
    parser.add_argument("--matlab-dir", default=str(DEFAULT_MATLAB_DIR))
    args = parser.parse_args()

    matlab_dir = Path(args.matlab_dir)
    computed = python_tables()

    failures: list[str] = []
    for name, columns in COMPARISONS.items():
        matlab_path = matlab_dir / name
        if not matlab_path.is_file():
            failures.append(f"{name}: no MATLAB artifact at {matlab_path}")
            continue
        failures.extend(
            compare(name, computed[name], pd.read_csv(matlab_path), columns)
        )

    print()
    if failures:
        print(f"FAIL -- the two implementations disagree ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nOne of them is wrong. Check the missing-value handling first: both sides "
            "must median-impute, and the medians must come from the same rows -- the "
            "training set for the correlation table, all rows for the covariate shift."
        )
        return 1

    print(f"PASS -- both implementations agree to within {TOLERANCE:.0e} on every compared number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
