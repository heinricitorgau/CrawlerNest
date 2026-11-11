"""An LLM as the hypothesis generator, kept inside the whitelisted space.

RD-Agent asks an LLM for the next hypothesis. Here the model sees the space (every allowed value and the one
invalid combination), the trace so far, and must answer with one JSON object naming a spec. It never writes code
and never names anything outside :data:`~ranking_ml.research.space.AXES`.

:class:`GuardedProposer` is what keeps that true. Whatever the model returns -- a spec outside the space, a repeat,
prose instead of JSON, an exception, or a refusal while untried specs remain -- is **refused and logged, never run**,
and the built-in :class:`~ranking_ml.research.proposer.OneChangeProposer` proposes that step instead. The report lists
every refusal, so a reader can see how much of the search the model actually steered.

The model is reached through a plain ``complete(system, user) -> str`` function, so this package does not depend on
the agent. ``loop.py --proposer llm`` builds one from the agent's configured provider.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ranking_ml.research.proposer import CallableProposer, OneChangeProposer, Proposer
from ranking_ml.research.space import AXES, ExperimentSpec, InvalidSpec, is_valid
from ranking_ml.research.trace import Hypothesis, Trace

Complete = Callable[[str, str], str]

SYSTEM_INSTRUCTION = (
    "You propose the next experiment in a search over models that estimate QS's overall score. "
    "You may only choose values from the space you are given; anything else is refused without being run. "
    "Answer with exactly one JSON object and nothing else: "
    '{"spec": {"model": ..., "missing": ..., "region": true|false}, "statement": "...", "reason": "..."} '
    "-- or {\"spec\": null, \"reason\": \"...\"} if you judge the search finished. "
    "The statement is a falsifiable hypothesis about the search-row Spearman; the reason cites the trace."
)


def _space_text() -> str:
    lines = [f"- {axis}: {', '.join(json.dumps(v) for v in values)}" for axis, values in AXES.items()]
    lines.append('- invalid: missing="renormalise" exists only with model="linear" and region=false')
    return "\n".join(lines)


def _trace_text(trace: list[dict[str, Any]]) -> str:
    rows = []
    for node in trace:
        spec = node.get("hypothesis", {}).get("spec") or node.get("spec") or {}
        result = node.get("result") or {}
        feedback = node.get("feedback") or {}
        score = result.get("search_spearman")
        rows.append(
            f"[{node.get('index')}] parent={node.get('parent')} spec={json.dumps(spec, sort_keys=True)} "
            f"search_spearman={'error' if score is None else round(score, 4)} "
            f"{'ACCEPTED' if feedback.get('decision') else 'rejected'}: {feedback.get('reason', '')}"
        )
    return "\n".join(rows) or "(empty)"


def build_user_message(trace: list[dict[str, Any]]) -> str:
    return (
        "Space:\n" + _space_text()
        + "\n\nTrace so far (search half of the withheld rows; higher Spearman is better; a change is accepted only "
        "if it beats the best accepted node by the minimum delta):\n" + _trace_text(trace)
        + "\n\nPropose one spec not already in the trace."
    )


def parse_reply(reply: str) -> dict[str, Any] | None:
    """The JSON object in a reply (fenced or bare). Raises InvalidSpec for anything else."""
    text = (reply or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1] if "{" in text else ""
    try:
        data = json.loads(candidate)
    except ValueError:
        raise InvalidSpec(f"reply is not one JSON object: {text[:120]!r}") from None
    if not isinstance(data, dict):
        raise InvalidSpec("reply JSON is not an object")
    if data.get("spec") is None:
        return None
    return data


def llm_callable(complete: Complete) -> Callable[[list[dict[str, Any]]], dict[str, Any] | None]:
    """The ``trace -> proposal`` function :class:`CallableProposer` wraps."""

    def propose(trace: list[dict[str, Any]]) -> dict[str, Any] | None:
        return parse_reply(complete(SYSTEM_INSTRUCTION, build_user_message(trace)))

    return propose


def _untried_valid_specs(trace: Trace) -> int:
    tried = trace.tried_keys()
    return sum(
        1
        for model in AXES["model"] for missing in AXES["missing"] for region in AXES["region"]
        if is_valid(spec := ExperimentSpec(model=model, missing=missing, region=region)) and spec.key() not in tried
    )


@dataclass
class GuardedProposer:
    """``primary`` proposes; a proposal it cannot make validly is refused, logged, and ``fallback`` proposes instead."""

    primary: Proposer
    fallback: Proposer = field(default_factory=OneChangeProposer)
    refusals: list[dict[str, Any]] = field(default_factory=list)
    accepted_from_primary: int = 0

    def propose(self, trace: Trace) -> Hypothesis | None:
        step = len(trace.hist)
        try:
            hypothesis = self.primary.propose(trace)
        except Exception as exc:  # noqa: BLE001 -- any failure of the model is a refusal, never a crash or a run
            self.refusals.append({"step": step, "reason": f"{type(exc).__name__}: {exc}"})
            return self._fallback(trace, step)
        if hypothesis is None:
            if _untried_valid_specs(trace):
                self.refusals.append({"step": step, "reason": "the model stopped while untried specs remained"})
                return self._fallback(trace, step)
            return None
        if not is_valid(hypothesis.spec) or hypothesis.spec.key() in trace.tried_keys():
            self.refusals.append({"step": step, "reason": f"out of space or repeated: {hypothesis.spec.key()}"})
            return self._fallback(trace, step)
        if step:  # the baseline is not the model's choice
            self.accepted_from_primary += 1
        return Hypothesis(
            statement=hypothesis.statement,
            reason=f"[model] {hypothesis.reason}".strip(),
            spec=hypothesis.spec,
            parent_index=hypothesis.parent_index,
            axis=hypothesis.axis,
            value=hypothesis.value,
        )

    def _fallback(self, trace: Trace, step: int) -> Hypothesis | None:
        hypothesis = self.fallback.propose(trace)
        if hypothesis is not None:
            self.refusals[-1]["fallback_spec"] = hypothesis.spec.key()
        return hypothesis

    def summary(self) -> dict[str, Any]:
        return {"accepted_from_model": self.accepted_from_primary, "refusals": list(self.refusals)}


def llm_proposer(complete: Complete) -> GuardedProposer:
    return GuardedProposer(primary=CallableProposer(llm_callable(complete)))
