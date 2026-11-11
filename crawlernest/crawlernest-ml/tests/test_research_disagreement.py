"""The disagreement research loop: its space, its split, and that the shared loop runs it unchanged."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ranking_ml.features.schema import QS_INDICATORS
from ranking_ml.research.disagreement import (
    BASELINE,
    DISAGREEMENT_SPACE,
    ClassifierResult,
    DisagreementSpec,
    split_frame,
)
from ranking_ml.research.llm_proposer import build_user_message, llm_proposer, system_instruction
from ranking_ml.research.loop import ResearchLoop
from ranking_ml.research.proposer import OneChangeProposer
from ranking_ml.research.space import InvalidSpec


def _result(score: float) -> ClassifierResult:
    return ClassifierResult(search_pr_auc=score, search_roc_auc=0.8, search_brier=0.1, search_n=800, search_positives=160)


class FakeRunner:
    def __init__(self, scores):
        self.scores = scores
        self.run_calls: list[str] = []
        self.holdout_calls: list[str] = []
        self.report_caveats = ["fake caveat"]

    def run(self, spec):
        self.run_calls.append(spec.key())
        return _result(self.scores.get(spec.key(), 0.5))

    def score_holdout(self, spec):
        self.holdout_calls.append(spec.key())
        return {"pr_auc": 0.55, "roc_auc": 0.85, "n": 284}


def test_the_space_has_ten_valid_specs_and_no_balanced_boosting():
    valid = DISAGREEMENT_SPACE.all_valid_specs()
    assert len(valid) == 10
    assert all(not (s.model == "gradient_boosting" and s.class_weight == "balanced") for s in valid)
    assert BASELINE in valid


def test_a_spec_outside_the_space_or_naming_a_the_feature_is_refused():
    with pytest.raises(InvalidSpec):
        DisagreementSpec.from_dict({"model": "gradient_boosting", "missing": "median", "class_weight": "balanced"})
    with pytest.raises(InvalidSpec):
        DisagreementSpec.from_dict({"model": "xgboost", "missing": "median", "class_weight": "none"})
    with pytest.raises(InvalidSpec):
        DisagreementSpec.from_dict({"model": "logistic", "missing": "median"})


def test_a_change_onto_balanced_boosting_is_repaired():
    spec = DisagreementSpec("random_forest", "median", "balanced").with_change("model", "gradient_boosting")
    assert DISAGREEMENT_SPACE.repair(spec, "model") == DisagreementSpec("gradient_boosting", "median", "none")
    assert DISAGREEMENT_SPACE.repair(spec, "class_weight") is None


def test_the_shared_loop_runs_the_whole_space_and_reports_in_its_metric():
    runner = FakeRunner({"random_forest|median|none": 0.60})
    loop = ResearchLoop(runner, OneChangeProposer(DISAGREEMENT_SPACE), min_delta=0.005)
    loop.run(20)
    assert len(loop.trace.hist) == 10
    assert loop.trace.hist[0][0].spec == BASELINE
    best = loop.trace.best_index()
    assert loop.trace.hist[best][0].spec.key() == "random_forest|median|none"
    assert loop.trace.hist[best][1].reason.startswith("Search PR-AUC 0.6000 beats node 0")
    report = loop.report()
    assert report["decision_metric"] == "Search PR-AUC on the search rows (out of fold)"
    assert "fake caveat" in report["caveats"]
    assert report["trace"][0]["result"]["metric_name"] == "Search PR-AUC"
    # The holdout is read once each for the best node and the baseline, never during the search.
    assert runner.holdout_calls == ["random_forest|median|none", BASELINE.key()]


def test_the_model_prompt_names_this_space_not_the_overall_score_one():
    text = build_user_message([], DISAGREEMENT_SPACE)
    assert '- class_weight: "none", "balanced"' in text and "renormalise" not in text
    assert "QS's nine published indicators alone" in system_instruction(DISAGREEMENT_SPACE)
    model_calls = []

    def model(system, user):
        model_calls.append(user)
        return json.dumps({"spec": {"model": "logistic", "missing": "knn", "class_weight": "balanced"},
                           "statement": "s", "reason": "r"})

    loop = ResearchLoop(FakeRunner({}), llm_proposer(model, DISAGREEMENT_SPACE))
    loop.run(2)
    assert loop.trace.hist[1][0].spec.key() == "logistic|knn|balanced"
    assert "search_pr-auc=0.5 ACCEPTED" in model_calls[0]


def test_the_label_threshold_comes_from_the_search_rows_only():
    rng = np.random.default_rng(0)
    n = 400
    frame = pd.DataFrame(rng.random((n, len(QS_INDICATORS))), columns=list(QS_INDICATORS))
    frame["percentile_gap"] = rng.random(n)
    split = split_frame(frame)
    assert len(split.y_search) == 300 and len(split.y_holdout) == 100
    search_gaps = frame["percentile_gap"].to_numpy()[split.X_search.index.to_numpy()]
    assert split.threshold == pytest.approx(np.quantile(search_gaps, 0.80))
    assert set(split.X_search.columns) == set(QS_INDICATORS)
