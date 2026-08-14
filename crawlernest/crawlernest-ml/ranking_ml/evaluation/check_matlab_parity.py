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
- It cannot itself catch someone editing the ``.m`` files and never re-running
  them, because stale CSVs still match. :func:`check_artifacts_are_current`
  covers that separately, by asking git whether the sources moved after the
  artifacts did. That is a weaker guarantee than re-executing the sources --
  which needs MATLAB on the runner, and MathWorks' free GitHub-hosted MATLAB
  covers public repositories only -- but it catches the failure that actually
  happens.

The tolerance is 1e-9. These are the same formulas over the same inputs, so
agreement should be near machine precision; anything looser would let a genuine
methodological difference pass as rounding.
"""

from __future__ import annotations

import argparse
import subprocess
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


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO_ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def check_artifacts_are_current() -> list[str]:
    """Did the ``.m`` sources move after the artifacts they produce?

    The parity check reads committed CSVs, so editing a source and forgetting to
    re-run it leaves a check that passes on stale files. Git can answer the
    narrower question of ordering without MATLAB being installed:

    - in history, is the newest commit touching ``matlab/*.m`` newer than the
      newest commit touching ``artifacts/eda_matlab/``?
    - in the working tree, is a source modified while the artifacts are not?

    Neither proves the numbers still agree -- only re-running does that -- but
    both catch the sequence that produces a silently stale artifact.
    """
    failures: list[str] = []
    # Only the .m files produce artifacts. Watching the whole directory would
    # fire on a README edit, and a check that cries wolf gets switched off.
    sources = "crawlernest/crawlernest-ml/matlab/*.m"
    artifacts = "crawlernest/crawlernest-ml/artifacts/eda_matlab"

    # A shallow clone reports the grafted commit's timestamp for *every* path, so
    # the two timestamps come back equal and the ordering test can never fire.
    # That is worse than an error: the guard would pass on a stale artifact and
    # look like it had checked. actions/checkout defaults to fetch-depth 1, so
    # this is the normal state in CI unless fetch-depth: 0 is set.
    if _git("rev-parse", "--is-shallow-repository") == "true":
        failures.append(
            "cannot determine whether the artifacts are current: this is a shallow "
            "clone, where git reports one timestamp for every path and the ordering "
            "test is meaningless. Set fetch-depth: 0 on actions/checkout."
        )
        return failures

    source_time = _git("log", "-1", "--format=%ct", "--", sources)
    artifact_time = _git("log", "-1", "--format=%ct", "--", artifacts)

    if not source_time or not artifact_time:
        failures.append(
            "cannot determine whether the artifacts are current: no commit touches "
            f"{'matlab/*.m' if not source_time else 'artifacts/eda_matlab/'} in this checkout."
        )
        return failures

    if int(source_time) > int(artifact_time):
        changed = _git("log", "-1", "--format=%h %s", "--", sources)
        failures.append(
            f"matlab/ was committed after artifacts/eda_matlab/ ({changed}). "
            "Re-run run_qs_eda.m and commit the regenerated artifacts, or the "
            "parity check is comparing against output the sources no longer produce."
        )

    dirty = _git("status", "--porcelain", "--", sources, artifacts).splitlines()
    dirty_sources = [line for line in dirty if line[3:].endswith(".m")]
    dirty_artifacts = [line for line in dirty if line[3:].startswith(artifacts)]
    if dirty_sources and not dirty_artifacts:
        names = ", ".join(line[3:].split("/")[-1] for line in dirty_sources)
        failures.append(
            f"uncommitted changes in matlab/ ({names}) with no corresponding change "
            "in artifacts/eda_matlab/. Re-run run_qs_eda.m before committing."
        )

    return failures


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

    failures: list[str] = check_artifacts_are_current()
    print("### are the committed artifacts current with the .m sources?")
    print("    " + ("no -- see below" if failures else "yes"))
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
        print(f"FAIL -- {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nIf the numbers disagree, one implementation is wrong: check the "
            "missing-value handling first, since both sides must median-impute and the "
            "medians must come from the same rows -- the training set for the "
            "correlation table, all rows for the covariate shift. If the artifacts are "
            "stale, re-run run_qs_eda.m; nothing here re-executes MATLAB for you."
        )
        return 1

    print(f"PASS -- both implementations agree to within {TOLERANCE:.0e} on every compared number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
