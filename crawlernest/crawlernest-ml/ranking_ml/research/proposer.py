"""Hypothesis generation -- RD-Agent's ``HypothesisGen``.

The built-in :class:`OneChangeProposer` grows the search from the best accepted
node: it changes one axis at a time, never proposes a spec already in the trace,
and tries the axis whose last change was accepted before the others. That is the
same "build on SOTA, learn from the feedback" behaviour RD-Agent asks its LLM
for, written down as a rule so it runs without one.

:class:`CallableProposer` is the hook for an LLM. The callable receives the trace
as plain data and returns ``{"spec": {...}, "statement": ..., "reason": ...}``;
the spec is validated against the space, and a repeat or an invalid spec is
refused rather than run.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from ranking_ml.research.space import AXES, BASELINE, ExperimentSpec, InvalidSpec, is_valid
from ranking_ml.research.trace import Hypothesis, Trace


class Proposer(Protocol):
    def propose(self, trace: Trace) -> Hypothesis | None:
        """The next hypothesis, or ``None`` when there is nothing left to try."""


def _baseline_hypothesis() -> Hypothesis:
    return Hypothesis(
        statement="Baseline: linear weighting, missing indicators renormalised, no region block.",
        reason="The model train_overall_score recommends for the withheld rows; every change is measured against it.",
        spec=BASELINE,
        parent_index=None,
    )


class OneChangeProposer:
    def propose(self, trace: Trace) -> Hypothesis | None:
        if not trace.hist:
            return _baseline_hypothesis()

        tried = trace.tried_keys()
        axes = self._axis_order(trace)
        # Grow from the best accepted node; once its neighbourhood is exhausted,
        # from the next-best runnable node, as RD-Agent may expand any node.
        for parent in self._parents_by_score(trace):
            parent_spec = trace.hist[parent][0].spec
            for axis in axes:
                for value in AXES[axis]:
                    spec = self._compatible(parent_spec.with_change(axis, value), axis)
                    if spec is None or spec == parent_spec or spec.key() in tried:
                        continue
                    repaired = "" if spec.missing == parent_spec.missing or axis == "missing" else (
                        f" (missing values switch to {spec.missing!r}, since renormalisation exists only for "
                        "the linear weighting without regions)"
                    )
                    return Hypothesis(
                        statement=f"Changing {axis} from {getattr(parent_spec, axis)!r} to {value!r}{repaired} "
                        f"improves rank agreement on the search rows.",
                        reason=self._reason(trace, parent, axis),
                        spec=spec,
                        parent_index=parent,
                        axis=axis,
                        value=value,
                    )
        return None

    @staticmethod
    def _parents_by_score(trace: Trace) -> list[int]:
        best = trace.best_index()
        if best is None:
            # Even the baseline failed to run; there is no node to grow from.
            return []
        others = [i for i, (exp, _) in enumerate(trace.hist) if exp.result is not None and i != best]
        others.sort(key=lambda i: trace.hist[i][0].result.search_spearman, reverse=True)
        return [best, *others]

    @staticmethod
    def _compatible(spec: ExperimentSpec, axis: str) -> ExperimentSpec | None:
        """The spec itself if valid; for a model or region change off renormalisation, its median-imputed twin."""
        if is_valid(spec):
            return spec
        if axis != "missing" and spec.missing == "renormalise":
            repaired = spec.with_change("missing", "median")
            return repaired if is_valid(repaired) else None
        return None

    @staticmethod
    def _axis_order(trace: Trace) -> list[str]:
        """Axes whose most recent change was accepted come first."""
        last_outcome: dict[str, bool] = {}
        for exp, fb in trace.hist:
            if exp.hypothesis.axis is not None:
                last_outcome[exp.hypothesis.axis] = fb.decision
        return sorted(AXES, key=lambda axis: (not last_outcome.get(axis, False), list(AXES).index(axis)))

    @staticmethod
    def _reason(trace: Trace, parent: int, axis: str) -> str:
        outcomes = [fb.decision for exp, fb in trace.hist if exp.hypothesis.axis == axis]
        base = f"Grown from node {parent}, the best accepted experiment so far."
        if not outcomes:
            return f"{base} The {axis} axis has not been varied yet."
        accepted = sum(outcomes)
        return f"{base} Earlier changes to {axis}: {accepted} accepted of {len(outcomes)}."


class CallableProposer:
    """Wrap any ``trace -> dict`` function (an LLM call, a human) as a proposer."""

    def __init__(self, fn: Callable[[list[dict[str, Any]]], dict[str, Any] | None]) -> None:
        self._fn = fn

    def propose(self, trace: Trace) -> Hypothesis | None:
        if not trace.hist:
            return _baseline_hypothesis()
        proposal = self._fn(trace.as_dict())
        if proposal is None:
            return None
        spec = ExperimentSpec.from_dict(proposal.get("spec") or {})
        if spec.key() in trace.tried_keys():
            raise InvalidSpec(f"{spec.key()} is already in the trace")
        parent = trace.best_index()
        return Hypothesis(
            statement=str(proposal.get("statement") or spec.key()),
            reason=str(proposal.get("reason") or ""),
            spec=spec,
            parent_index=parent,
        )
