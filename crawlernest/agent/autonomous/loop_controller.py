from __future__ import annotations

from crawlernest.agent.autonomous.evaluator import AutonomousEvaluator
from crawlernest.agent.autonomous.stop_policy import StopPolicy
from crawlernest.agent.autonomous.step_executor import StepExecutor
from crawlernest.agent.autonomous.task_graph import TaskGraphBuilder


class LoopController:
    def __init__(
        self,
        *,
        task_graph: TaskGraphBuilder | None = None,
        step_executor: StepExecutor | None = None,
        evaluator: AutonomousEvaluator | None = None,
        stop_policy: StopPolicy | None = None,
        max_iterations: int = 5,
    ) -> None:
        self._task_graph = task_graph or TaskGraphBuilder()
        self._step_executor = step_executor
        self._evaluator = evaluator or AutonomousEvaluator()
        self._stop_policy = stop_policy or StopPolicy()
        self._max_iterations = max_iterations

    def run(
        self,
        *,
        goal: str,
        context: dict,
        repo_index: dict,
        validation_builder,
    ) -> dict[str, object]:
        if self._step_executor is None:
            raise ValueError("step_executor must be provided")

        steps = self._task_graph.build(goal=goal, context=context)
        trace_steps: list[dict[str, object]] = []
        state: dict[str, object] = {
            "best_score": 0.0,
            "best_step": None,
            "resolution": None,
            "patchCandidate": None,
        }
        final_status = "partial"
        stop_reason = "max_steps_reached"
        stagnant_steps = 0

        for iteration, step in enumerate(steps, start=1):
            if iteration > self._max_iterations:
                break

            step_result = self._step_executor.execute(
                step=step,
                goal=goal,
                context=context,
                repo_index=repo_index,
                state=state,
                validation_builder=validation_builder,
            )
            if step_result.get("resolution") is not None:
                state["resolution"] = step_result.get("resolution")
            if step_result.get("patchCandidate") is not None:
                state["patchCandidate"] = step_result.get("patchCandidate")

            evaluation = self._evaluator.evaluate(
                step_name=str(step.get("step", "unknown")),
                step_result=step_result,
                state=state,
            )
            score = float(evaluation.get("score", 0.0))
            improved = score > float(state.get("best_score", 0.0))
            if improved:
                state["best_score"] = score
                state["best_step"] = step.get("step")
                stagnant_steps = 0
            else:
                stagnant_steps += 1

            trace_steps.append(
                {
                    "step": step.get("step"),
                    "description": step.get("description"),
                    "result": step_result,
                    "score": score,
                    "status": evaluation.get("status"),
                    "reason": evaluation.get("reason"),
                }
            )

            should_stop, candidate_reason = self._stop_policy.should_stop(
                iteration=iteration,
                max_iterations=min(self._max_iterations, len(steps)),
                score=score,
                best_score=float(state.get("best_score", 0.0)),
                stagnant_steps=stagnant_steps,
                step_name=str(step.get("step", "")),
            )
            if should_stop:
                stop_reason = candidate_reason or stop_reason
                final_status = "success" if score >= 0.9 else "partial"
                break
        else:
            stop_reason = "max_steps_reached"
            final_status = "partial"

        return {
            "steps": trace_steps,
            "final_status": final_status,
            "stop_reason": stop_reason,
            "best_score": float(state.get("best_score", 0.0)),
            "best_step": state.get("best_step"),
            "strategy_hints": [
                str(item).strip()
                for item in context.get("strategy_hints", [])
                if isinstance(item, str) and str(item).strip()
            ],
        }
