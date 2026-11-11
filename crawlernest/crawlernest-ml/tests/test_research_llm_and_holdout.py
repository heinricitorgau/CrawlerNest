"""The LLM proposer stays inside the space, and the holdout is read a bounded number of times across runs."""

from __future__ import annotations

import json

import pytest

from ranking_ml.research.holdout import HoldoutLedger
from ranking_ml.research.llm_proposer import (
    GuardedProposer,
    build_user_message,
    llm_proposer,
    parse_reply,
)
from ranking_ml.research.loop import ResearchLoop
from ranking_ml.research.space import BASELINE, InvalidSpec

from test_research_loop import FakeRunner


def _reply(model, missing, region, statement="try it"):
    return json.dumps({"spec": {"model": model, "missing": missing, "region": region},
                       "statement": statement, "reason": "trace says so"})


class ScriptedModel:
    """A model whose replies are given in advance; records every prompt it saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, system, user):
        self.prompts.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_the_prompt_names_the_space_and_the_trace():
    text = build_user_message([{"index": 0, "parent": None, "hypothesis": {"spec": BASELINE.as_dict()},
                                "result": {"search_spearman": 0.96}, "feedback": {"decision": True, "reason": "baseline"}}])
    assert '"gradient_boosting"' in text and "renormalise" in text and "only with model=\"linear\"" in text
    assert "search_spearman=0.96 ACCEPTED" in text


def test_replies_are_parsed_from_fences_and_prose_is_refused():
    assert parse_reply("```json\n" + _reply("ridge", "median", False) + "\n```")["spec"]["model"] == "ridge"
    assert parse_reply('{"spec": null, "reason": "done"}') is None
    with pytest.raises(InvalidSpec):
        parse_reply("I think ridge regression would be nice.")


def test_valid_proposals_run_and_are_credited_to_the_model():
    model = ScriptedModel([_reply("ridge", "median", False), _reply("ridge", "knn", False)])
    loop = ResearchLoop(FakeRunner({"ridge|median|no-region": 0.97, "ridge|knn|no-region": 0.98}), llm_proposer(model))
    loop.run(3)
    keys = [exp.spec.key() for exp, _ in loop.trace.hist]
    assert keys == [BASELINE.key(), "ridge|median|no-region", "ridge|knn|no-region"]
    assert loop.report()["proposer"]["accepted_from_model"] == 2
    assert loop.trace.hist[1][0].hypothesis.reason.startswith("[model]")


def test_out_of_space_repeats_prose_and_errors_are_refused_never_run():
    model = ScriptedModel([
        _reply("xgboost", "median", False),          # outside the space
        _reply("ridge", "renormalise", False),       # an invalid combination
        BASELINE and _reply("linear", "renormalise", False),  # a repeat of the baseline
        "Let me think about this.",                  # prose
        RuntimeError("provider timed out"),          # a failed call
    ])
    runner = FakeRunner({})
    loop = ResearchLoop(runner, llm_proposer(model))
    loop.run(6)
    proposer = loop.proposer
    assert isinstance(proposer, GuardedProposer)
    assert len(proposer.refusals) == 5
    assert all("fallback_spec" in r for r in proposer.refusals)
    # Nothing the model named outside the space reached the runner.
    assert not any(k.startswith("xgboost") or k == "ridge|renormalise|no-region" for k in runner.run_calls)
    assert proposer.summary()["accepted_from_model"] == 0


def test_stopping_early_is_refused_while_specs_remain():
    model = ScriptedModel(['{"spec": null, "reason": "looks done"}'])
    loop = ResearchLoop(FakeRunner({}), llm_proposer(model))
    loop.run(2)
    assert len(loop.trace.hist) == 2
    assert "untried specs remained" in loop.proposer.refusals[0]["reason"]


def test_the_holdout_is_read_a_bounded_number_of_times(tmp_path):
    ledger = HoldoutLedger(tmp_path / "ledger.json", "abc:alternate-by-rank-v1", max_reads=2)
    for expected_reads in (1, 2):
        runner = FakeRunner({})
        loop = ResearchLoop(runner)
        loop.run(1)
        report = loop.report(ledger)
        assert report["holdout_reads"] == expected_reads
        assert any(f"read {expected_reads} time" in c for c in report["caveats"])

    runner = FakeRunner({})
    loop = ResearchLoop(runner)
    loop.run(1)
    refused = loop.report(ledger)
    assert "holdout" not in refused and "already been read 2 times" in refused["holdout_withheld"]
    assert runner.holdout_calls == []

    forced = loop.report(ledger, allow_reread=True)
    assert forced["holdout_reads"] == 3
    assert any("past its limit, by explicit override" in c for c in forced["caveats"])


def test_another_snapshot_or_split_is_a_fresh_holdout(tmp_path):
    path = tmp_path / "ledger.json"
    HoldoutLedger(path, "a:rule", max_reads=1).record_read()
    assert not HoldoutLedger(path, "a:rule", max_reads=1).may_read()
    assert HoldoutLedger(path, "b:rule", max_reads=1).may_read()
