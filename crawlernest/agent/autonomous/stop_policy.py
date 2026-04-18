from __future__ import annotations


class StopPolicy:
    def __init__(self, *, success_threshold: float = 0.9, max_stagnant_steps: int = 2) -> None:
        self._success_threshold = success_threshold
        self._max_stagnant_steps = max_stagnant_steps

    def should_stop(
        self,
        *,
        iteration: int,
        max_iterations: int,
        score: float,
        best_score: float,
        stagnant_steps: int,
        step_name: str,
    ) -> tuple[bool, str | None]:
        if step_name == "validate" and score >= self._success_threshold:
            return True, "score_threshold"
        if iteration >= max_iterations:
            return True, "max_steps_reached"
        if step_name == "validate" and stagnant_steps >= self._max_stagnant_steps:
            return True, "no_improvement"
        return False, None
