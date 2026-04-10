from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EvaluationResult:
    score: float
    passed: bool
    feedback: list[str] = field(default_factory=list)


class Evaluator:
    """Simple heuristic evaluator that can later wrap a real judge model."""

    def evaluate(self, result: str) -> EvaluationResult:
        score = 0.35
        feedback: list[str] = []
        normalized = result.lower()

        if len(result) >= 80:
            score += 0.2
        else:
            feedback.append("Add more detail so the output is actionable.")

        if "tool insights" in normalized:
            score += 0.2
        else:
            feedback.append("Use at least one tool signal when tools are available.")

        if "plan" in normalized or "next step" in normalized:
            score += 0.15
        else:
            feedback.append("Include a clearer execution plan or next step.")

        if "refined" in normalized or "improved" in normalized:
            score += 0.1

        score = min(score, 1.0)
        return EvaluationResult(score=score, passed=score >= 0.75, feedback=feedback)

