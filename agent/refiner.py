from __future__ import annotations

from agent.evaluator import EvaluationResult


class Refiner:
    """Applies lightweight improvements based on evaluator feedback."""

    def refine(self, result: str, evaluation: EvaluationResult) -> str:
        additions: list[str] = ["Refined version:"]

        if evaluation.feedback:
            additions.append("Applied feedback:")
            additions.extend(f"- {item}" for item in evaluation.feedback)

        additions.append(
            "Next step: validate the proposal against a real tool or implementation target."
        )

        return f"{result}\n\n" + "\n".join(additions)

