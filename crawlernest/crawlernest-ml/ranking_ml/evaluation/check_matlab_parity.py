"""Check the MATLAB ports against the Python ones, number by number.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.evaluation.check_matlab_parity

Four MATLAB entry points claim to compute the same things as their Python
counterparts. Until something compares them, "ported to MATLAB" is an assertion.
Two implementations that disagree are not a redundancy, they are a bug in one of
them, and nobody knows which.

Each entry point is registered below as a :class:`Port`: the ``.m`` file, the
artifact directory it writes, the CSVs to compare, and the Python function that
recomputes them. Adding a port means adding one entry; the guard, the CLI and
the reporting all follow from the registry rather than from a hardcoded pair.

## What this proves, and what it does not

It compares the **committed** MATLAB artifacts against a **fresh** Python run.
So:

- It catches the Python side drifting away from a verified reference.
- It catches a MATLAB re-run that produces different numbers.
- It cannot itself catch someone editing a ``.m`` file and never re-running it,
  because stale CSVs still match. :func:`compare_artifact_dirs` covers that, by
  running the sources and comparing what they produce against what is committed.
  :func:`check_artifacts_are_current` asks git the weaker question of commit
  ordering; it is **reported as a warning, not enforced**, because it fails a
  source commit that provably does not change its artifact and such a commit has
  no regenerated output to commit in response. Should the ``matlab-reexecution``
  job ever be removed, those warnings must go back to being failures.

Since the repository became public, MathWorks' free GitHub-hosted MATLAB is
available to it, and the ``matlab-reexecution`` job in ``ml-tests.yml`` runs the
``.m`` sources on every push. It passes the fresh output root as
``--fresh-root``, so the comparison above is against sources that just executed
*and* the committed artifacts are asserted to be what those sources produce.
This module still never invokes MATLAB itself.

## What is deliberately not compared

The disagreement classifier's metrics. Its dataset is deterministic and is
checked here, but ROC-AUC and PR-AUC depend on a stratified fold split whose RNG
cannot be aligned between MATLAB and scikit-learn, and on MATLAB's LogitBoost
standing in for scikit-learn's gradient boosting. Those numbers agree to within
the spread across fold seeds, which is a real claim but not a 1e-9 one, so
asserting it here at this tolerance would only produce a flaky check. The
dataset summary is where a silent divergence would actually do damage -- a
missing entity pairing quietly halves the matched population -- and that is
checked exactly.

The tolerance is 1e-9. These are the same formulas over the same inputs, so
agreement should be near machine precision; anything looser would let a genuine
methodological difference pass as rounding.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from ranking_ml.eda.run_eda import correlation_with_target, covariate_shift
from ranking_ml.evaluation.baselines import (
    normalised_coefficients,
    published_weight_prediction,
)
from ranking_ml.evaluation.metrics import regression_metrics
from ranking_ml.features.build_features import load_feature_matrix, missingness_report
from ranking_ml.features.cross_source import build_cross_source_frame, disagreement_label
from ranking_ml.features.schema import QS_INDICATORS, QS_PUBLISHED_WEIGHTS
from ranking_ml.models.overall_score import RenormalisedWeightedScore, build_pipelines
from ranking_ml.models.support import SupportFlagger

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ML_ROOT = _REPO_ROOT / "crawlernest" / "crawlernest-ml"
_MATLAB_DIR = "crawlernest/crawlernest-ml/matlab"

TOLERANCE = 1e-9

#: Helpers every entry point calls. A change to one of these can move any
#: artifact, so they count as a source for every port rather than for none.
SHARED_SOURCES: tuple[str, ...] = (
    "load_qs_snapshot.m",
    "qs_to_float.m",
    "qs_to_rank.m",
)

#: Entry points whose output is not compared, listed so that "not checked" is a
#: recorded decision rather than something nobody noticed. See the module
#: docstring for why the classifier's metrics are not comparable at 1e-9;
#: the diagnostics figure draws those same metrics, and a PNG has nothing this
#: module could compare numerically in any case.
UNCHECKED_SOURCES: tuple[str, ...] = (
    "train_disagreement_classifier.m",
    "plot_disagreement_diagnostics.m",
)


@dataclass(frozen=True)
class Comparison:
    """One CSV, the column its rows are keyed on, and the numbers to compare."""

    filename: str
    key: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class Port:
    """A MATLAB entry point, what it writes, and how to recompute it."""

    name: str
    source: str
    artifacts: str
    comparisons: tuple[Comparison, ...]
    build: Callable[[], dict[str, pd.DataFrame]]

    @property
    def artifact_dir(self) -> Path:
        return _REPO_ROOT / self.artifacts

    @property
    def source_paths(self) -> list[str]:
        return [f"{_MATLAB_DIR}/{name}" for name in (self.source, *SHARED_SOURCES)]


# ---------------------------------------------------------------------------
# Python references
# ---------------------------------------------------------------------------


def eda_tables() -> dict[str, pd.DataFrame]:
    """The three EDA tables, at full precision."""
    matrix = load_feature_matrix()
    missing = missingness_report(matrix).reset_index(names="indicator")
    return {
        "correlation_with_target.csv": correlation_with_target(matrix),
        "covariate_shift.csv": covariate_shift(matrix),
        "missingness.csv": missing,
    }


def weight_tables() -> dict[str, pd.DataFrame]:
    """Phase 2 weight recovery, at full precision.

    ``weight_recovery_table`` in ``evaluation.baselines`` rounds to four
    decimals for display, which would wash out a real disagreement at this
    tolerance, so the frames are assembled here from the unrounded fits.
    """
    matrix = load_feature_matrix()
    X_lab, y_lab = matrix.labelled()
    published = np.array([QS_PUBLISHED_WEIGHTS[name] for name in QS_INDICATORS])

    linear_raw = build_pipelines()["linear_raw"].fit(X_lab, y_lab)
    raw_weights = np.array(
        [normalised_coefficients(linear_raw.named_steps["model"].coef_)[n] for n in QS_INDICATORS]
    )

    renorm = RenormalisedWeightedScore().fit(X_lab, y_lab)

    def recovery(weights: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "indicator": list(QS_INDICATORS),
                "qs_published": published,
                "recovered": weights,
                "abs_error": np.abs(weights - published),
            }
        )

    y_true = y_lab.to_numpy()
    fits = {
        "QS published weighting (no fit)": published_weight_prediction(X_lab),
        "linear_raw": linear_raw.predict(X_lab),
        "linear_renorm": renorm.predict(X_lab),
    }
    fit_rows = []
    for name, prediction in fits.items():
        m = regression_metrics(y_true, prediction)
        fit_rows.append({"fit": name, "rmse": m.rmse, "mae": m.mae, "r2": m.r2, "n": m.n})

    importance = recovery(raw_weights)[["indicator", "qs_published", "recovered"]].merge(
        correlation_with_target(matrix), on="indicator"
    )

    return {
        "weight_recovery_linear_raw.csv": recovery(raw_weights),
        "weight_recovery_linear_renorm.csv": recovery(renorm.weights_),
        "in_sample_fit.csv": pd.DataFrame(fit_rows),
        "weight_vs_correlation.csv": importance,
    }


def support_tables() -> dict[str, pd.DataFrame]:
    """Support-flag summary, at full precision.

    ``SupportFlagger.report`` rounds, so the same quantities are recomputed here
    from the unrounded distances.
    """
    matrix = load_feature_matrix()
    X_lab, _ = matrix.labelled()
    flagger = SupportFlagger().fit(X_lab)

    rows = []
    for label, X in (("labelled", X_lab), ("unlabelled", matrix.unlabelled())):
        distances = flagger.distance(X)
        supported = distances <= flagger.threshold_
        rows.append(
            {
                "set": label,
                "n": len(distances),
                "supported": int(supported.sum()),
                "supported_pct": 100.0 * float(supported.mean()),
                "distance_median": float(np.median(distances)),
                "distance_p95": float(np.percentile(distances, 95)),
                "threshold": flagger.threshold_,
            }
        )
    return {"support_summary.csv": pd.DataFrame(rows)}


def cross_source_tables() -> dict[str, pd.DataFrame]:
    """The deterministic half of Phase 3: who was matched and how many disagree."""
    cross = build_cross_source_frame()
    frame = cross.frame
    y, threshold = disagreement_label(frame, quantile=0.80)
    favoured = frame.loc[y == 1, "favoured_by"].value_counts()

    values = {
        "matched": len(frame),
        "qs_population": cross.qs_population,
        "the_population": cross.the_population,
        "gap_threshold": threshold,
        "positives": int(y.sum()),
        "positive_rate": float(y.mean()),
        "favoured_the": int(favoured.get("THE", 0)),
        "favoured_qs": int(favoured.get("QS", 0)),
        "paired_count": int(frame["key"].astype(str).str.startswith("pair::").sum()),
    }
    return {
        "dataset_summary.csv": pd.DataFrame(
            {"quantity": list(values), "value": [float(v) for v in values.values()]}
        )
    }


PORTS: tuple[Port, ...] = (
    Port(
        name="eda",
        source="run_qs_eda.m",
        artifacts="crawlernest/crawlernest-ml/artifacts/eda_matlab",
        comparisons=(
            Comparison("correlation_with_target.csv", "indicator", ("pearson_r",)),
            Comparison(
                "covariate_shift.csv",
                "indicator",
                ("labelled_mean", "unlabelled_mean", "standardised_gap"),
            ),
            Comparison("missingness.csv", "indicator", ("missing", "missing_pct")),
        ),
        build=eda_tables,
    ),
    Port(
        name="weights",
        source="recover_qs_weights.m",
        artifacts="crawlernest/crawlernest-ml/artifacts/weights_matlab",
        comparisons=(
            Comparison(
                "weight_recovery_linear_raw.csv",
                "indicator",
                ("qs_published", "recovered", "abs_error"),
            ),
            Comparison(
                "weight_recovery_linear_renorm.csv",
                "indicator",
                ("qs_published", "recovered", "abs_error"),
            ),
            Comparison("in_sample_fit.csv", "fit", ("rmse", "mae", "r2", "n")),
            Comparison(
                "weight_vs_correlation.csv",
                "indicator",
                ("qs_published", "recovered", "pearson_r"),
            ),
        ),
        build=weight_tables,
    ),
    Port(
        name="support",
        source="qs_support_flagger.m",
        artifacts="crawlernest/crawlernest-ml/artifacts/support_matlab",
        comparisons=(
            Comparison(
                "support_summary.csv",
                "set",
                (
                    "n",
                    "supported",
                    "supported_pct",
                    "distance_median",
                    "distance_p95",
                    "threshold",
                ),
            ),
        ),
        build=support_tables,
    ),
    Port(
        name="cross_source",
        source="build_cross_source_data.m",
        artifacts="crawlernest/crawlernest-ml/artifacts/cross_source_matlab",
        comparisons=(Comparison("dataset_summary.csv", "quantity", ("value",)),),
        build=cross_source_tables,
    ),
)


# ---------------------------------------------------------------------------
# freshness guard
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(_REPO_ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def check_artifacts_are_current(ports: tuple[Port, ...] = PORTS) -> list[str]:
    """Did any ``.m`` source move after the artifacts it produces?

    The parity check reads committed CSVs, so editing a source and forgetting to
    re-run it leaves a check that passes on stale files. Git can answer the
    narrower question of ordering without MATLAB being installed, per port:

    - in history, is the newest commit touching this port's sources newer than
      the newest commit touching its artifact directory?
    - in the working tree, is one of its sources modified while its artifacts
      are not?

    Neither proves the numbers still agree -- only re-running does that -- but
    both catch the sequence that produces a silently stale artifact. Asking per
    port matters: adding a second entry point used to fail the whole check,
    because a new ``.m`` file was newer than an artifact directory it has
    nothing to do with.
    """
    failures: list[str] = []

    # A shallow clone reports the grafted commit's timestamp for *every* path, so
    # the two timestamps come back equal and the ordering test can never fire.
    # That is worse than an error: the guard would pass on a stale artifact and
    # look like it had checked. actions/checkout defaults to fetch-depth 1, so
    # this is the normal state in CI unless fetch-depth: 0 is set.
    if _git("rev-parse", "--is-shallow-repository") == "true":
        return [
            "cannot determine whether the artifacts are current: this is a shallow "
            "clone, where git reports one timestamp for every path and the ordering "
            "test is meaningless. Set fetch-depth: 0 on actions/checkout."
        ]

    for port in ports:
        source_time = _git("log", "-1", "--format=%ct", "--", *port.source_paths)
        artifact_time = _git("log", "-1", "--format=%ct", "--", port.artifacts)

        if not source_time or not artifact_time:
            missing = port.source if not source_time else port.artifacts
            failures.append(
                f"{port.name}: cannot determine whether the artifacts are current -- "
                f"no commit touches {missing} in this checkout."
            )
            continue

        if int(source_time) > int(artifact_time):
            changed = _git("log", "-1", "--format=%h %s", "--", *port.source_paths)
            failures.append(
                f"{port.name}: sources were committed after {port.artifacts} ({changed}). "
                f"Re-run {port.source} and commit the regenerated artifacts, or the "
                "parity check is comparing against output the sources no longer produce."
            )

        dirty = _git("status", "--porcelain", "--", *port.source_paths, port.artifacts)
        lines = [line[3:] for line in dirty.splitlines() if line[3:]]
        dirty_sources = [path for path in lines if path.endswith(".m")]
        dirty_artifacts = [path for path in lines if path.startswith(port.artifacts)]
        if dirty_sources and not dirty_artifacts:
            names = ", ".join(Path(path).name for path in dirty_sources)
            failures.append(
                f"{port.name}: uncommitted changes in {names} with no corresponding "
                f"change in {port.artifacts}. Re-run {port.source} before committing."
            )

    return failures


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def compare(
    label: str, comparison: Comparison, python: pd.DataFrame, matlab: pd.DataFrame
) -> list[str]:
    """Compare one table, returning failure messages."""
    failures: list[str] = []
    key = comparison.key

    python_keys = set(python[key].astype(str))
    matlab_keys = set(matlab[key].astype(str))
    if python_keys != matlab_keys:
        failures.append(
            f"{label}: the two implementations do not cover the same {key} values. "
            f"Python only: {sorted(python_keys - matlab_keys)}. "
            f"MATLAB only: {sorted(matlab_keys - python_keys)}."
        )
        return failures

    python = python.assign(**{key: python[key].astype(str)})
    matlab = matlab.assign(**{key: matlab[key].astype(str)})
    merged = python.merge(matlab, on=key, suffixes=("_py", "_ml"))
    print(f"\n{label}  ({len(merged)} rows)")
    print(f"  {'column':<20} {'max abs difference':>20}   verdict")

    for column in comparison.columns:
        difference = (
            merged[f"{column}_py"].astype(float) - merged[f"{column}_ml"].astype(float)
        ).abs()
        worst = float(difference.max())
        ok = worst <= TOLERANCE
        print(f"  {column:<20} {worst:>20.3e}   {'ok' if ok else 'MISMATCH'}")
        if not ok:
            row = merged.loc[difference.idxmax()]
            failures.append(
                f"{label}: {column} differs by {worst:.3e} (tolerance {TOLERANCE:.0e}). "
                f"Worst at {row[key]!r}: Python {row[f'{column}_py']}, "
                f"MATLAB {row[f'{column}_ml']}."
            )

    return failures


def compare_artifact_dirs(port: Port, fresh: Path) -> list[str]:
    """Do freshly executed sources still produce the committed artifacts?

    ``check_artifacts_are_current`` can only ask git about commit ordering, which
    catches the usual mistake but proves nothing about the numbers. Given MATLAB
    on the runner, this answers it directly: run the ``.m`` sources into a fresh
    directory and compare that against what is committed.

    A difference here means the committed CSVs are not what the sources produce
    -- somebody edited MATLAB and did not re-run it, or re-ran it and did not
    commit the result. Either way the parity check has been reading a reference
    that no longer exists.
    """
    failures: list[str] = []

    for comparison in port.comparisons:
        fresh_path = fresh / comparison.filename
        committed_path = port.artifact_dir / comparison.filename
        if not fresh_path.is_file():
            failures.append(f"{port.name}: MATLAB produced no {fresh_path}")
            continue
        if not committed_path.is_file():
            failures.append(f"{port.name}: nothing committed at {committed_path}")
            continue

        fresh_table = pd.read_csv(fresh_path)
        committed_table = pd.read_csv(committed_path)
        key = comparison.key
        if set(fresh_table[key].astype(str)) != set(committed_table[key].astype(str)):
            failures.append(
                f"{port.name}/{comparison.filename}: a fresh MATLAB run covers "
                f"different {key} values than the committed artifact."
            )
            continue

        merged = fresh_table.merge(
            committed_table, on=key, suffixes=("_new", "_old")
        )
        for column in comparison.columns:
            worst = float(
                (merged[f"{column}_new"].astype(float) - merged[f"{column}_old"].astype(float))
                .abs().max()
            )
            print(
                f"  {port.name + '/' + comparison.filename:<44} {column:<18} "
                f"{worst:>12.3e}  {'ok' if worst <= TOLERANCE else 'STALE'}"
            )
            if worst > TOLERANCE:
                failures.append(
                    f"{port.name}/{comparison.filename}: {column} from a fresh MATLAB run "
                    f"differs from the committed artifact by {worst:.3e}. "
                    f"Re-run {port.source} and commit the result."
                )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare the MATLAB ports to the Python ones.")
    parser.add_argument(
        "--fresh-root",
        default=None,
        help=(
            "Directory holding output from a MATLAB run that just happened, one "
            "subdirectory per port named after its artifact directory. Used in CI: "
            "the fresh output becomes the MATLAB side of every comparison, and the "
            "committed artifacts are additionally asserted to match it."
        ),
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Comma-separated port names to check (default: all).",
    )
    args = parser.parse_args()

    ports = PORTS
    if args.only:
        wanted = {name.strip() for name in args.only.split(",")}
        unknown = wanted - {port.name for port in PORTS}
        if unknown:
            parser.error(f"unknown port(s): {sorted(unknown)}")
        ports = tuple(port for port in PORTS if port.name in wanted)

    fresh_root = Path(args.fresh_root) if args.fresh_root else None

    failures: list[str] = []

    # The ordering question is a proxy, and a lossy one: it fails a source commit
    # that provably does not change its artifact, and such a commit cannot be made
    # to pass, because there is no regenerated output to commit. That is not
    # hypothetical -- adding a field to a returned struct triggered it, with every
    # numeric comparison passing and the re-executed sources reproducing the
    # committed artifact exactly.
    #
    # So it is reported, not enforced. The gate is compare_artifact_dirs below,
    # which runs the sources and compares what they produce -- it answers directly
    # what this can only approximate, and it runs on every push now that the
    # repository is public. If the matlab-reexecution job is ever removed, these
    # warnings have to go back to being failures: nothing else would catch a .m
    # file that was edited and never re-run.
    staleness = check_artifacts_are_current(ports)
    print("### are the committed artifacts current with the .m sources?")
    print("    " + ("git ordering says no -- see below" if staleness else "yes"))
    print(f"    not compared: {', '.join(UNCHECKED_SOURCES)} (see module docstring)")
    for warning in staleness:
        print(f"    [warn] {warning}")

    if fresh_root:
        print("\n### do the .m sources still produce the committed artifacts?")
        for port in ports:
            failures.extend(compare_artifact_dirs(port, fresh_root / Path(port.artifacts).name))
    elif staleness:
        print("\n    No --fresh-root given, so the warnings above are unverified here.")
        print("    The matlab-reexecution job settles them by running the sources.")

    for port in ports:
        computed = port.build()
        matlab_dir = fresh_root / Path(port.artifacts).name if fresh_root else port.artifact_dir
        for comparison in port.comparisons:
            matlab_path = matlab_dir / comparison.filename
            if not matlab_path.is_file():
                failures.append(f"{port.name}: no MATLAB artifact at {matlab_path}")
                continue
            failures.extend(
                compare(
                    f"{port.name}/{comparison.filename}",
                    comparison,
                    computed[comparison.filename],
                    pd.read_csv(matlab_path),
                )
            )

    print()
    if failures:
        print(f"FAIL -- {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nIf the numbers disagree, one implementation is wrong. Check the "
            "missing-value handling first, since both sides must median-impute and the "
            "medians must come from the same rows, and then the percentile convention: "
            "numpy places order statistics at (i-1)/(n-1) and MATLAB prctile at "
            "(i-0.5)/n, which is a real difference and not rounding. If the artifacts "
            "are stale, re-run the .m file named above -- this module never executes "
            "MATLAB itself; CI does that and passes the result in with --fresh-root."
        )
        return 1

    print(f"PASS -- both implementations agree to within {TOLERANCE:.0e} on every compared number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
