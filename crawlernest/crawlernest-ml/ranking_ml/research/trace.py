"""Hypotheses, experiments, feedback, and the trace that records them.

Ported from RD-Agent's ``rdagent/core/proposal.py``. The trace keeps the same
shape: ``hist`` is the list of ``(experiment, feedback)`` nodes in the order they
were recorded, and ``dag_parent[i]`` is the index of node ``i``'s parent, ``()``
for a root. The SOTA for a node is the last accepted experiment on its path back
to the root, so a rejected branch never becomes the base of the next one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ranking_ml.research.space import ExperimentSpec


@dataclass(frozen=True)
class Hypothesis:
    """One proposed change and why it was proposed.

    ``axis`` and ``value`` name the change relative to ``parent_spec``; ``None``
    for both marks the baseline, which changes nothing.
    """

    statement: str
    reason: str
    spec: ExperimentSpec
    parent_index: int | None
    axis: str | None = None
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "statement": self.statement,
            "reason": self.reason,
            "spec": self.spec.as_dict(),
            "parent_index": self.parent_index,
            "axis": self.axis,
            "value": self.value,
        }


@dataclass
class ExperimentResult:
    """What a run of the overall-score model measured. ``search_spearman`` is the number decisions use.

    Every result type exposes ``search_score`` (the decision number, higher is better) and ``metric_name``;
    the judge, the trace and the proposers read only those, so another model's result can sit in the same loop.
    """

    cv_rmse_mean: float
    cv_rmse_std: float
    cv_r2_mean: float
    search_spearman: float
    search_n: int
    supported_search_spearman: float

    metric_name = "Search Spearman"

    @property
    def search_score(self) -> float:
        return self.search_spearman

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


@dataclass
class Experiment:
    hypothesis: Hypothesis
    result: ExperimentResult | None = None
    error: str | None = None

    @property
    def spec(self) -> ExperimentSpec:
        return self.hypothesis.spec


@dataclass(frozen=True)
class Feedback:
    decision: bool
    reason: str
    delta: float | None = None

    def __bool__(self) -> bool:
        return self.decision

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "delta": None if self.delta is None else round(self.delta, 4),
        }


@dataclass
class Trace:
    hist: list[tuple[Experiment, Feedback]] = field(default_factory=list)
    dag_parent: list[tuple[int, ...]] = field(default_factory=list)

    def record(self, experiment: Experiment, feedback: Feedback) -> int:
        parent = experiment.hypothesis.parent_index
        if parent is not None and not 0 <= parent < len(self.hist):
            raise IndexError(f"parent {parent} is not a recorded node")
        self.dag_parent.append(() if parent is None else (parent,))
        self.hist.append((experiment, feedback))
        return len(self.hist) - 1

    def ancestors(self, index: int) -> list[int]:
        """Path from the root to ``index``, inclusive, root first."""
        path: list[int] = []
        current: int | None = index
        while current is not None:
            path.insert(0, current)
            parent = self.dag_parent[current]
            current = parent[0] if parent else None
        return path

    def sota_index(self, from_index: int | None = None) -> int | None:
        """The last accepted node on the path to ``from_index`` (default: the latest node)."""
        if not self.hist:
            return None
        start = len(self.hist) - 1 if from_index is None else from_index
        for i in reversed(self.ancestors(start)):
            if self.hist[i][1].decision:
                return i
        return None

    def best_index(self) -> int | None:
        """The accepted node with the highest search score across every branch."""
        accepted = [i for i, (exp, fb) in enumerate(self.hist) if fb.decision and exp.result is not None]
        if not accepted:
            return None
        return max(accepted, key=lambda i: self.hist[i][0].result.search_score)

    def tried_keys(self) -> set[str]:
        return {exp.spec.key() for exp, _ in self.hist}

    def as_dict(self) -> list[dict[str, Any]]:
        return [
            {
                "index": i,
                "parent": self.dag_parent[i][0] if self.dag_parent[i] else None,
                "hypothesis": exp.hypothesis.as_dict(),
                "result": None if exp.result is None else {
                    **exp.result.as_dict(),
                    "metric_name": exp.result.metric_name,
                    "search_score": round(float(exp.result.search_score), 4),
                },
                "error": exp.error,
                "feedback": fb.as_dict(),
            }
            for i, (exp, fb) in enumerate(self.hist)
        ]
