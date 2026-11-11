"""The research loop: propose -> build -> run -> feedback -> record.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.research.loop --loops 12

Each step is RD-Agent's step of the same name (``RDLoop`` in
``rdagent/components/workflow/rd_loop.py``): the proposer plays ``HypothesisGen``,
:func:`build_estimator` plays ``Hypothesis2Experiment`` and the coder, the runner
plays the runner, and :func:`judge` plays ``Experiment2Feedback``. An experiment
that raises is recorded as a rejected node with its error, as RDLoop records it,
and the loop goes on.

Decisions are made on the *search* half of the withheld rows. The *holdout* half
is read once, after the loop, for the best node and the baseline. The report
goes to ``.local/reports/research/`` and is an estimate of model quality, not
data: it never reaches ``analytics.ml_predictions``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ranking_ml.evaluation.metrics import rank_agreement
from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, FeatureMatrix, load_feature_matrix
from ranking_ml.models.support import SupportFlagger
from ranking_ml.research.holdout import DEFAULT_MAX_READS, HoldoutLedger, holdout_key
from ranking_ml.research.proposer import OneChangeProposer, Proposer
from ranking_ml.research.space import ExperimentSpec, InvalidSpec, build_estimator
from ranking_ml.research.trace import Experiment, ExperimentResult, Feedback, Hypothesis, Trace
from ranking_ml.training.train_overall_score import cross_validate_pipeline

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUT_DIR = _REPO_ROOT / ".local" / "reports" / "research"

#: A change has to beat the best node by this much Spearman to be accepted, so
#: a difference in the fourth decimal does not move the search.
DEFAULT_MIN_DELTA = 0.001
#: Names the rule split_withheld cuts by; part of the holdout's identity in the ledger. Change it with the rule.
SPLIT_RULE = "alternate-by-rank-v1"


@dataclass(frozen=True)
class SearchSplit:
    """The withheld rows, split by rank into the half the loop sees and the half it does not."""

    X_lab: pd.DataFrame
    y_lab: pd.Series
    X_search: pd.DataFrame
    rank_search: np.ndarray
    X_holdout: pd.DataFrame
    rank_holdout: np.ndarray


def split_withheld(matrix: FeatureMatrix) -> SearchSplit:
    """Alternate the withheld rows in rank order, so both halves span the whole tail."""
    X_lab, y_lab = matrix.labelled()
    unlabelled = matrix.rank.loc[~matrix.labelled_mask]
    ordered = unlabelled.reset_index().sort_values([unlabelled.name, "index"], kind="stable")["index"].to_numpy()
    search, holdout = ordered[0::2], ordered[1::2]
    return SearchSplit(
        X_lab=X_lab,
        y_lab=y_lab,
        X_search=matrix.X.loc[search],
        rank_search=matrix.rank.loc[search].to_numpy(),
        X_holdout=matrix.X.loc[holdout],
        rank_holdout=matrix.rank.loc[holdout].to_numpy(),
    )


class Runner:
    def __init__(self, split: SearchSplit, folds: int = 5) -> None:
        self._split = split
        self._folds = folds
        self._supported_search = SupportFlagger().fit(split.X_lab).is_supported(split.X_search)

    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        s = self._split
        cv, _ = cross_validate_pipeline(build_estimator(spec), s.X_lab, s.y_lab, self._folds)
        predicted = build_estimator(spec).fit(s.X_lab, s.y_lab).predict(s.X_search)
        search = rank_agreement(predicted, s.rank_search)
        supported = rank_agreement(predicted[self._supported_search], s.rank_search[self._supported_search])
        return ExperimentResult(
            cv_rmse_mean=cv.rmse_mean,
            cv_rmse_std=cv.rmse_std,
            cv_r2_mean=cv.r2_mean,
            search_spearman=search["spearman"],
            search_n=search["n"],
            supported_search_spearman=supported["spearman"],
        )

    def score_holdout(self, spec: ExperimentSpec) -> dict[str, float]:
        s = self._split
        predicted = build_estimator(spec).fit(s.X_lab, s.y_lab).predict(s.X_holdout)
        return rank_agreement(predicted, s.rank_holdout)


def judge(experiment: Experiment, trace: Trace, min_delta: float = DEFAULT_MIN_DELTA) -> Feedback:
    """Accept a node only if it beats the best accepted node by ``min_delta``."""
    if experiment.error is not None:
        return Feedback(decision=False, reason=f"The experiment failed: {experiment.error}")
    result = experiment.result
    name = result.metric_name
    if not np.isfinite(result.search_score):
        return Feedback(decision=False, reason=f"{name} is not finite.")

    best = trace.best_index()
    if best is None:
        return Feedback(decision=True, reason="First runnable node; it becomes the reference.")
    best_score = trace.hist[best][0].result.search_score
    delta = result.search_score - best_score
    if delta > min_delta:
        return Feedback(
            decision=True,
            reason=f"{name} {result.search_score:.4f} beats node {best} ({best_score:.4f}) by {delta:+.4f}.",
            delta=delta,
        )
    return Feedback(
        decision=False,
        reason=f"{name} {result.search_score:.4f} vs node {best} ({best_score:.4f}): "
        f"{delta:+.4f}, not above the {min_delta} threshold.",
        delta=delta,
    )


class ResearchLoop:
    def __init__(
        self,
        runner: Runner,
        proposer: Proposer | None = None,
        *,
        min_delta: float = DEFAULT_MIN_DELTA,
    ) -> None:
        self.runner = runner
        self.proposer = proposer or OneChangeProposer()
        self.min_delta = min_delta
        self.trace = Trace()

    def step(self) -> bool:
        """One full loop. ``False`` when the proposer has nothing left to try."""
        try:
            hypothesis = self.proposer.propose(self.trace)
        except InvalidSpec as refused:
            # A proposal outside the space is refused without running; there is
            # no node to record it against, so the loop stops on it.
            raise RuntimeError(f"proposer returned an invalid hypothesis: {refused}") from refused
        if hypothesis is None:
            return False
        experiment = self._run(hypothesis)
        self.trace.record(experiment, judge(experiment, self.trace, self.min_delta))
        return True

    def _run(self, hypothesis: Hypothesis) -> Experiment:
        experiment = Experiment(hypothesis=hypothesis)
        try:
            experiment.result = self.runner.run(hypothesis.spec)
        except Exception as e:  # noqa: BLE001 -- a failed experiment is a node, as in RDLoop
            experiment.error = f"{type(e).__name__}: {e}"
        return experiment

    def run(self, loops: int) -> Trace:
        for _ in range(loops):
            if not self.step():
                break
        return self.trace

    def report(self, ledger: HoldoutLedger | None = None, *, allow_reread: bool = False) -> dict[str, Any]:
        """The run's report. With a ledger, the holdout is read only while it has been read fewer than
        ``ledger.max_reads`` times across runs (``allow_reread`` overrides that, and the report says so)."""
        trace = self.trace
        best = trace.best_index()
        runnable = sum(1 for exp, _ in trace.hist if exp.result is not None)
        metric = next((exp.result.metric_name for exp, _ in trace.hist if exp.result is not None), "Search Spearman")
        runner_caveats = getattr(self.runner, "report_caveats", None)
        report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "decision_metric": (
                "Spearman between predicted score and published rank, search half of the withheld rows"
                if metric == "Search Spearman" else f"{metric} on the search rows (out of fold)"
            ),
            "min_delta": self.min_delta,
            "trials": len(trace.hist),
            "runnable_trials": runnable,
            "trace": trace.as_dict(),
            "best_index": best,
            "caveats": [
                f"The best node was chosen among {runnable} runnable trials on the same search rows, "
                "so its search-row margin is optimistic. The holdout figures are the ones to quote.",
                *(list(runner_caveats) if runner_caveats is not None else [
                    "Rank agreement is measured against QS's published rank, which for the withheld tail is "
                    "often a band lower bound (1401+), so tied ranks cap the attainable Spearman.",
                    "Every score here is a model estimate of QS's overall score; nothing is written to the warehouse.",
                ]),
            ],
        }
        summary = getattr(self.proposer, "summary", None)
        if callable(summary):
            report["proposer"] = summary()
        if best is not None:
            if ledger is not None and not ledger.may_read() and not allow_reread:
                report["holdout_withheld"] = (
                    f"The holdout has already been read {ledger.reads()} times (limit {ledger.max_reads}). "
                    "Another read would be a choice made on it; use a fresh holdout instead."
                )
                return report
            baseline_spec = trace.hist[0][0].spec
            best_spec = trace.hist[best][0].spec
            report["holdout"] = {
                "best": {"spec": best_spec.as_dict(), **self.runner.score_holdout(best_spec)},
                "baseline": {"spec": baseline_spec.as_dict(), **self.runner.score_holdout(baseline_spec)},
            }
            if ledger is not None:
                reads = ledger.record_read(note=f"best={best_spec.key()} trials={len(trace.hist)}")
                report["holdout_reads"] = reads
                report["caveats"].append(
                    f"This holdout has now been read {reads} time(s) across runs"
                    + (" -- past its limit, by explicit override." if reads > ledger.max_reads else ".")
                )
        return report


def _agent_complete():
    """``complete(system, user)`` over the agent's configured provider (WEB_AGENT_* / AGENT_MODEL_* settings).

    Imported here only: the ML package has no other dependency on the agent. With no provider configured the
    generator answers with its fallback text, which is not JSON, so every step is refused and the rule proposes.
    """
    import sys

    sys.path.insert(0, str(_REPO_ROOT))
    from crawlernest.agent.web_agent.generation.models import PromptPayload
    from crawlernest.agent.web_agent.generation.response_generator import WebResponseGenerator

    generator = WebResponseGenerator()

    def complete(system: str, user: str) -> str:
        result = generator.generate_response(
            prompt=PromptPayload(system_instruction=system, user_message=user, context_block=""),
            fallback_text="(no model)",
        )
        return result.reply_text

    return complete


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RD-style research loop over the overall-score model.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--loops", type=int, default=12)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--min-delta", type=float, default=DEFAULT_MIN_DELTA)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--proposer", choices=("rule", "llm"), default="rule",
                        help="llm: the agent's configured model proposes, inside the space; refusals fall back to rule")
    parser.add_argument("--max-holdout-reads", type=int, default=DEFAULT_MAX_READS)
    parser.add_argument("--allow-holdout-reread", action="store_true")
    args = parser.parse_args()

    split = split_withheld(load_feature_matrix(args.snapshot))
    proposer: Proposer | None = None
    if args.proposer == "llm":
        from ranking_ml.research.llm_proposer import llm_proposer

        proposer = llm_proposer(_agent_complete())
    loop = ResearchLoop(Runner(split, folds=args.folds), proposer, min_delta=args.min_delta)
    ledger = HoldoutLedger(Path(args.out_dir) / "holdout_ledger.json",
                           holdout_key(Path(args.snapshot), SPLIT_RULE), max_reads=args.max_holdout_reads)
    for _ in range(args.loops):
        if not loop.step():
            print("proposer exhausted the space")
            break
        i = len(loop.trace.hist) - 1
        exp, fb = loop.trace.hist[i]
        score = "error" if exp.result is None else f"{exp.result.search_score:.4f}"
        print(f"[{i:>2}] parent={exp.hypothesis.parent_index!s:>4}  {exp.spec.key():<40} "
              f"search {score:<7} {'ACCEPT' if fb else 'reject'}  {fb.reason}")

    report = loop.report(ledger, allow_reread=args.allow_holdout_reread)
    if "holdout_withheld" in report:
        print(f"\nholdout not read: {report['holdout_withheld']}")
    if "holdout" in report:
        best, base = report["holdout"]["best"], report["holdout"]["baseline"]
        print(f"\nholdout  best {best['spearman']:.4f}  ({ExperimentSpec(**best['spec']).key()})")
        print(f"holdout  base {base['spearman']:.4f}  ({ExperimentSpec(**base['spec']).key()})")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"overall_score_research_{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
