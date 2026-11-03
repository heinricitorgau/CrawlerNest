"""Research-loop tests: the trace, the proposer, the judge, and the holdout boundary.

Most run against a fake runner, so they test the loop's logic and not the models.
One runs three real experiments on the committed snapshot.
"""

from __future__ import annotations

import numpy as np
import pytest

from ranking_ml.features.build_features import load_feature_matrix
from ranking_ml.research.loop import ResearchLoop, Runner, judge, split_withheld
from ranking_ml.research.proposer import CallableProposer, OneChangeProposer
from ranking_ml.research.space import (
    AXES,
    BASELINE,
    ExperimentSpec,
    InvalidSpec,
    build_estimator,
    is_valid,
)
from ranking_ml.research.trace import Experiment, ExperimentResult, Feedback, Hypothesis, Trace


def _result(score: float) -> ExperimentResult:
    return ExperimentResult(
        cv_rmse_mean=1.0, cv_rmse_std=0.1, cv_r2_mean=0.9,
        search_spearman=score, search_n=400, supported_search_spearman=score,
    )


class FakeRunner:
    """Scores a spec from a table; records every call so the holdout boundary can be checked."""

    def __init__(self, scores: dict[str, float], fail: set[str] = frozenset()) -> None:
        self.scores = scores
        self.fail = fail
        self.run_calls: list[str] = []
        self.holdout_calls: list[str] = []

    def run(self, spec: ExperimentSpec) -> ExperimentResult:
        self.run_calls.append(spec.key())
        if spec.key() in self.fail:
            raise RuntimeError("boom")
        return _result(self.scores.get(spec.key(), 0.5))

    def score_holdout(self, spec: ExperimentSpec) -> dict[str, float]:
        self.holdout_calls.append(spec.key())
        return {"spearman": 0.9, "p_value": 0.0, "n": 400}


def _all_valid_specs() -> list[ExperimentSpec]:
    return [
        ExperimentSpec(model=m, missing=s, region=r)
        for m in AXES["model"] for s in AXES["missing"] for r in AXES["region"]
        if is_valid(ExperimentSpec(model=m, missing=s, region=r))
    ]


# ── the space ────────────────────────────────────────────────────────────────


def test_renormalise_only_exists_for_the_plain_linear_weighting():
    assert is_valid(BASELINE)
    assert not is_valid(ExperimentSpec(model="ridge", missing="renormalise", region=False))
    assert not is_valid(ExperimentSpec(model="linear", missing="renormalise", region=True))


def test_a_spec_outside_the_space_is_refused_not_built():
    with pytest.raises(InvalidSpec):
        ExperimentSpec.from_dict({"model": "xgboost", "missing": "median", "region": False})
    with pytest.raises(InvalidSpec):
        build_estimator(ExperimentSpec(model="linear", missing="zero", region=False))


# ── the trace ────────────────────────────────────────────────────────────────


def _node(trace: Trace, spec: ExperimentSpec, parent: int | None, accepted: bool) -> int:
    hypothesis = Hypothesis(statement="", reason="", spec=spec, parent_index=parent)
    return trace.record(Experiment(hypothesis, result=_result(0.5)), Feedback(decision=accepted, reason=""))


def test_sota_is_the_last_accepted_node_on_the_path_not_on_another_branch():
    trace = Trace()
    root = _node(trace, BASELINE, None, True)
    a = _node(trace, ExperimentSpec("linear", "median", False), root, True)
    _node(trace, ExperimentSpec("linear", "knn", False), a, False)
    b = _node(trace, ExperimentSpec("ridge", "median", False), root, False)

    assert trace.ancestors(2) == [root, a, 2]
    assert trace.sota_index(2) == a
    assert trace.sota_index(b) == root  # node a is on a sibling branch


def test_recording_against_an_unknown_parent_fails():
    with pytest.raises(IndexError):
        _node(Trace(), BASELINE, 3, True)


# ── the judge ────────────────────────────────────────────────────────────────


def test_judge_needs_more_than_min_delta_to_accept():
    trace = Trace()
    _node(trace, BASELINE, None, True)  # search 0.5
    close = Experiment(Hypothesis("", "", ExperimentSpec("ridge", "median", False), 0), result=_result(0.5005))
    clear = Experiment(Hypothesis("", "", ExperimentSpec("ridge", "median", False), 0), result=_result(0.52))
    assert not judge(close, trace, min_delta=0.001)
    assert judge(clear, trace, min_delta=0.001)


def test_a_failed_experiment_is_rejected_with_its_error():
    failed = Experiment(Hypothesis("", "", BASELINE, None), error="RuntimeError: boom")
    feedback = judge(failed, Trace())
    assert not feedback and "boom" in feedback.reason


# ── the loop ─────────────────────────────────────────────────────────────────


def test_the_loop_covers_the_space_once_and_never_repeats():
    runner = FakeRunner({})
    loop = ResearchLoop(runner)
    loop.run(loops=100)
    assert len(runner.run_calls) == len(set(runner.run_calls))
    assert set(runner.run_calls) == {spec.key() for spec in _all_valid_specs()}
    assert loop.step() is False


def test_the_loop_grows_from_an_accepted_improvement():
    better = ExperimentSpec("linear", "median", False)
    runner = FakeRunner({BASELINE.key(): 0.90, better.key(): 0.95})
    loop = ResearchLoop(runner)
    loop.run(loops=3)
    first_after_improvement = loop.trace.hist[2][0].hypothesis
    assert loop.trace.hist[1][1].decision
    assert first_after_improvement.parent_index == 1
    assert loop.trace.best_index() == 1


def test_a_raising_experiment_becomes_a_rejected_node_and_the_loop_goes_on():
    bad = ExperimentSpec("linear", "median", False)
    runner = FakeRunner({}, fail={bad.key()})
    loop = ResearchLoop(runner)
    loop.run(loops=4)
    errors = [exp.error for exp, _ in loop.trace.hist if exp.error]
    assert errors == ["RuntimeError: boom"]
    assert len(loop.trace.hist) == 4


def test_the_holdout_is_only_read_by_the_report():
    runner = FakeRunner({})
    loop = ResearchLoop(runner)
    loop.run(loops=100)
    assert runner.holdout_calls == []
    report = loop.report()
    assert runner.holdout_calls == [BASELINE.key(), BASELINE.key()]
    assert report["trials"] == len(_all_valid_specs())
    assert any("optimistic" in caveat for caveat in report["caveats"])


def test_callable_proposer_refuses_a_repeat_and_an_invented_model():
    loop = ResearchLoop(FakeRunner({}), CallableProposer(lambda trace: {"spec": BASELINE.as_dict()}))
    loop.step()  # baseline
    with pytest.raises(RuntimeError, match="already in the trace"):
        loop.step()

    invented = CallableProposer(lambda trace: {"spec": {"model": "xgboost", "missing": "median", "region": False}})
    loop = ResearchLoop(FakeRunner({}), invented)
    loop.step()
    with pytest.raises(RuntimeError, match="unknown model"):
        loop.step()


# ── the real split and runner ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def split():
    return split_withheld(load_feature_matrix())


def test_search_and_holdout_partition_the_withheld_rows(split):
    matrix = load_feature_matrix()
    withheld = set(matrix.X.index[~matrix.labelled_mask])
    search, holdout = set(split.X_search.index), set(split.X_holdout.index)
    assert search.isdisjoint(holdout)
    assert search | holdout == withheld
    assert abs(len(search) - len(holdout)) <= 1
    # Alternating in rank order keeps both halves spread across the whole tail.
    assert abs(np.median(split.rank_search) - np.median(split.rank_holdout)) < 50


def test_three_real_experiments_keep_the_renormalised_baseline(split):
    loop = ResearchLoop(Runner(split, folds=3), OneChangeProposer())
    loop.run(loops=3)
    keys = [exp.spec.key() for exp, _ in loop.trace.hist]
    assert keys[0] == BASELINE.key()
    # The module's own finding: median imputation loses to renormalisation out in the tail.
    assert loop.trace.best_index() == 0
    assert loop.trace.hist[0][0].result.search_spearman > 0.95
