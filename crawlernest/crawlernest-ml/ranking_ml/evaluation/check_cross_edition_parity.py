"""Check the MATLAB cross-edition experiment against the Python re-implementation of its deterministic part.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \
        -m ranking_ml.evaluation.check_cross_edition_parity

``matlab/run_cross_edition_forecast.m`` writes ``forecast_metrics.csv``. Two things in it are
deterministic functions of the committed export and are recomputed here from scratch, with no code
shared with the MATLAB side:

* the number of consecutive-edition pairs per source and test year, and
* persistence (``persist_mid``, ``persist_lo``), persistence shifted by the training drift
  (``persist_drift``) and ordinary least squares (``linear_own``, ``linear``): their sizes, mean interval
  error, hit rate and mean absolute log error, per source, test edition, stratum, and pooled.

Those are the numbers every learned-model claim is measured against, so an off-by-one in the pair
construction, or a band midpoint computed differently, would corrupt the conclusion without anything
failing. The tolerance is 1e-9 for the baselines: same formulas, same inputs.

Ordinary least squares (``linear_own`` and ``linear``) is deterministic too, and is compared at 1e-7:
a least-squares solve in two linear-algebra libraries agrees to rounding, not to the last bit, and the
looser bound is that rounding, not a methodological allowance. It is a stronger check than the
baselines, because it exercises the whole feature construction -- imputation, flags, the log scale --
that the boosted model also consumes.

Not compared: the boosted model's errors, and the bootstrap intervals. MATLAB and Python share neither
a boosting implementation nor a random stream, so those agree only to within sampling noise, which is a
statement about the method rather than something this check can assert at machine precision. What *is*
checked for them is that they were scored on exactly the same test rows as everything else: the same
``n`` in every cell.

Exit status 0 when everything agrees, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ranking_ml.features.cross_edition import (
    DEFAULT_CSV,
    MIN_TRAIN,
    SOURCES,
    TEST_FROM,
    build_pairs,
    load_ranks,
    MODELS,
    OLS_MODELS,
    deterministic_metrics,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MATLAB_DIR = _REPO_ROOT / "crawlernest" / "crawlernest-ml" / "artifacts" / "cross_edition_matlab"
TOLERANCE = 1e-9
OLS_TOLERANCE = 1e-7
KEYS = ["source", "test", "model", "stratum"]
NUMERIC = ["n", "meanIntervalErr", "hitRate", "meanAbsLogErrMid"]


def compare(matlab_dir: Path = DEFAULT_MATLAB_DIR, csv: Path = DEFAULT_CSV) -> list[str]:
    """Every disagreement, as a sentence. Empty means the two implementations agree."""
    problems: list[str] = []
    metrics = pd.read_csv(matlab_dir / "forecast_metrics.csv", dtype={"test": str})
    run = json.loads((matlab_dir / "forecast_run.json").read_text(encoding="utf-8"))
    ranks = load_ranks(csv)
    pairs = build_pairs(ranks)

    meta_path = csv.with_suffix(".meta.json")
    if meta_path.exists():
        sha = json.loads(meta_path.read_text(encoding="utf-8"))["csv_sha256"]
        if run["data_sha256"] != sha:
            problems.append(f"the MATLAB run used data {run['data_sha256'][:12]}, the committed export is {sha[:12]}")

    for source in SOURCES:
        expected = int((pairs["source"] == source).sum())
        got = int(run["pairs_per_source"][source])
        if expected != got:
            problems.append(f"{source}: {got} pairs in MATLAB, {expected} in Python")

    test_from = int(run.get("test_from", TEST_FROM))
    min_train = int(run.get("min_train", MIN_TRAIN))
    python = deterministic_metrics(pairs, test_from=test_from, min_train=min_train)
    merged = python.merge(metrics, on=KEYS, how="outer", suffixes=("_py", "_ml"), indicator=True)
    compared = merged[merged["model"].isin(MODELS)]
    for _, row in compared[compared["_merge"] != "both"].iterrows():
        side = "only in Python" if row["_merge"] == "left_only" else "only in MATLAB"
        problems.append(f"{row['source']} {row['test']} {row['model']} {row['stratum']}: row {side}")
    both = compared[compared["_merge"] == "both"]
    tolerance = both["model"].map(lambda m: OLS_TOLERANCE if m in OLS_MODELS else TOLERANCE)
    for column in NUMERIC:
        delta = (both[f"{column}_py"] - both[f"{column}_ml"]).abs()
        for _, row in both[delta > tolerance].iterrows():
            problems.append(
                f"{row['source']} {row['test']} {row['model']} {row['stratum']}: {column} "
                f"{row[f'{column}_py']!r} (Python) vs {row[f'{column}_ml']!r} (MATLAB)"
            )

    # Every model is scored on the same rows as the baseline in its cell.
    sizes = metrics.groupby(["source", "test", "stratum"])["n"].nunique()
    for key, count in sizes[sizes > 1].items():
        problems.append(f"{key}: the models were scored on different numbers of rows")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--matlab-dir", type=Path, default=DEFAULT_MATLAB_DIR)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args(argv)
    problems = compare(args.matlab_dir, args.csv)
    if problems:
        print(f"{len(problems)} disagreement(s) between MATLAB and Python:")
        for line in problems[:40]:
            print(f"  {line}")
        return 1
    print("MATLAB and Python agree on every pair count, every persistence baseline (1e-9) and both "
          "least-squares models (1e-7).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
