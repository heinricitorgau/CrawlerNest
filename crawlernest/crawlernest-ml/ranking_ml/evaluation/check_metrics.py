"""Fail if a retrained model is worse than the committed metrics say it was.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.evaluation.check_metrics --baseline-dir <dir>

Run after retraining. The training scripts overwrite ``artifacts/metrics/*.json``
in place, so CI copies the committed files aside first and points this at the
copies: the committed numbers are the baseline, the freshly-written ones are the
candidate.

Why this exists: a model has no compiler and no failing test to tell you it broke.
Without a gate, a change that quietly costs three points of AUC looks exactly
like a change that costs nothing, and the metrics in the README slowly become
fiction. This repo already has one instance of that failure mode -- a Java test
that stayed red for two months because no workflow ran it.

Two kinds of guard, because they fail differently:

``metric``
    A number that may drift a little between library versions but must not
    regress. Compared against the baseline with a direction and a tolerance.
``invariant``
    A number that describes the *data*, not the model -- row counts, class
    balance. These are exact. If the training set stops being 600 rows, no
    metric comparison below it means anything, so they are checked first.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_METRICS_DIR = _REPO_ROOT / "crawlernest" / "crawlernest-ml" / "artifacts" / "metrics"


@dataclass(frozen=True)
class Guard:
    path: str
    #: "higher" -- larger is better; "lower" -- smaller is better.
    direction: str
    tolerance: float


@dataclass(frozen=True)
class Invariant:
    path: str


#: Guarded metrics per report. Deliberately a short list: guarding every number
#: produces a gate that fails for reasons nobody reads. These are the ones whose
#: movement would change a claim made in the model cards.
GUARDS: dict[str, list[Guard]] = {
    "overall_score.json": [
        # The recommended estimator. Tolerances are loose enough for library
        # drift, tight enough that a real regression cannot hide under them.
        Guard("cross_validation.linear_renorm.rmse_mean", "lower", 0.05),
        Guard("cross_validation.linear_renorm.r2_mean", "higher", 0.0005),
        # The headline claim: QS's published weighting is recovered.
        Guard("weight_recovery.mean_abs_error", "lower", 0.0005),
        # The only external check in the shifted region.
        Guard("rank_agreement.linear_renorm.all_unlabelled.spearman", "higher", 0.01),
    ],
    "disagreement.json": [
        Guard("qs_only.gradient_boosting.roc_auc", "higher", 0.02),
        Guard("qs_only.gradient_boosting.pr_auc", "higher", 0.03),
    ],
}

#: Structural facts about the data. Checked exactly, and before the metrics.
INVARIANTS: dict[str, list[Invariant]] = {
    "overall_score.json": [
        Invariant("dataset.rows_total"),
        Invariant("dataset.rows_labelled"),
        Invariant("dataset.rows_unlabelled"),
    ],
    "disagreement.json": [
        Invariant("dataset.matched"),
        Invariant("dataset.positives"),
    ],
}


def resolve(report: dict[str, Any], path: str) -> Any:
    """Look up a dotted path, returning ``None`` if any segment is missing."""
    node: Any = report
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def compare_report(name: str, baseline: dict, candidate: dict) -> list[str]:
    """Returns a list of failure messages; empty means the report passed."""
    failures: list[str] = []

    print(f"\n{name}")
    print(f"  {'metric':<58} {'baseline':>10} {'candidate':>10}   verdict")

    for invariant in INVARIANTS.get(name, []):
        want = resolve(baseline, invariant.path)
        got = resolve(candidate, invariant.path)
        if want is None or got is None:
            failures.append(f"{name}: invariant {invariant.path} missing from a report")
            verdict = "MISSING"
        elif want != got:
            failures.append(
                f"{name}: invariant {invariant.path} changed from {want} to {got}. "
                "The data underneath the model moved; the metric comparison below is "
                "not meaningful until this is explained."
            )
            verdict = "CHANGED"
        else:
            verdict = "ok"
        print(f"  {invariant.path:<58} {str(want):>10} {str(got):>10}   {verdict}")

    for guard in GUARDS.get(name, []):
        base = resolve(baseline, guard.path)
        cand = resolve(candidate, guard.path)
        if base is None or cand is None:
            failures.append(f"{name}: guarded metric {guard.path} missing from a report")
            print(f"  {guard.path:<58} {'-':>10} {'-':>10}   MISSING")
            continue

        base, cand = float(base), float(cand)
        if guard.direction == "higher":
            regressed = cand < base - guard.tolerance
            arrow = "must not fall"
        else:
            regressed = cand > base + guard.tolerance
            arrow = "must not rise"

        verdict = "REGRESSED" if regressed else "ok"
        print(f"  {guard.path:<58} {base:>10.4f} {cand:>10.4f}   {verdict}")
        if regressed:
            failures.append(
                f"{name}: {guard.path} {arrow} by more than {guard.tolerance} -- "
                f"baseline {base:.4f}, candidate {cand:.4f}"
            )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare freshly-trained metrics to the committed ones.")
    parser.add_argument("--baseline-dir", required=True,
                        help="Directory holding the committed metrics JSON files")
    parser.add_argument("--candidate-dir", default=str(DEFAULT_METRICS_DIR),
                        help="Directory holding the freshly-written metrics JSON files")
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir)
    candidate_dir = Path(args.candidate_dir)

    failures: list[str] = []
    for name in GUARDS:
        baseline_path = baseline_dir / name
        candidate_path = candidate_dir / name
        if not baseline_path.is_file():
            failures.append(f"{name}: no committed baseline at {baseline_path}")
            continue
        if not candidate_path.is_file():
            failures.append(f"{name}: no freshly-written report at {candidate_path}. Did training run?")
            continue
        failures.extend(
            compare_report(
                name,
                json.loads(baseline_path.read_text(encoding="utf-8")),
                json.loads(candidate_path.read_text(encoding="utf-8")),
            )
        )

    print()
    if failures:
        print(f"FAIL -- {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nIf the change is intended, retrain locally, commit the updated "
            "artifacts/metrics/*.json, and say in the commit message why the number moved."
        )
        return 1

    print("PASS -- no guarded metric regressed and the data invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
