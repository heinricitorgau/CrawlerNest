from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agent.evaluator import EvaluationResult, Evaluator
from agent.memory import Memory
from agent.refiner import Refiner
from agent.tasks import AgentTask
from agent.tools import ToolFn


Logger = Callable[[str], None]


@dataclass(slots=True)
class AgentRunResult:
    task: str
    output: str
    score: float
    passed: bool
    iterations: int
    tool_outputs: list[dict[str, Any]] = field(default_factory=list)
    feedback: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


class AgentEngine:
    """Unified generate -> evaluate -> refine loop."""

    def __init__(
        self,
        evaluator: Evaluator,
        refiner: Refiner,
        tools: dict[str, ToolFn],
        threshold: float = 0.75,
        max_iterations: int = 2,
        logger: Logger | None = None,
    ) -> None:
        self.evaluator = evaluator
        self.refiner = refiner
        self.tools = tools
        self.threshold = threshold
        self.max_iterations = max_iterations
        self.logger = logger

    def run(self, task: AgentTask, memory: Memory) -> AgentRunResult:
        trace: list[str] = []
        context = memory.build_context()

        self._log(f"[engine] start task={task.name}", trace)
        generated, tool_outputs = self.generate(task, context)
        evaluation = self.evaluate(generated, trace)

        iterations = 1
        current_output = generated
        current_evaluation = evaluation

        while current_evaluation.score < self.threshold and iterations < self.max_iterations:
            self._log(
                f"[engine] score {current_evaluation.score:.2f} below threshold {self.threshold:.2f}; refining",
                trace,
            )
            current_output = self.refine(current_output, current_evaluation, trace)
            current_evaluation = self.evaluate(current_output, trace)
            iterations += 1

        memory.add("user", task.prompt, task=task.name)
        memory.add("assistant", current_output, score=current_evaluation.score)

        self._log(
            f"[engine] finished after {iterations} iteration(s) with score={current_evaluation.score:.2f}",
            trace,
        )
        return AgentRunResult(
            task=task.name,
            output=current_output,
            score=current_evaluation.score,
            passed=current_evaluation.passed,
            iterations=iterations,
            tool_outputs=tool_outputs,
            feedback=current_evaluation.feedback,
            trace=trace,
        )

    def generate(self, task: AgentTask, context: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        tool_outputs = self._run_tools(task, context)
        history_summary = self._summarize_history(context)

        lines = [
            f"Task: {task.prompt}",
            f"Context summary: {history_summary}",
            "Draft answer: provide a focused response with a short plan.",
        ]

        if tool_outputs:
            lines.append("Tool insights:")
            for output in tool_outputs:
                lines.append(f"- {output['tool']}: {output['summary']}")

        lines.append("Plan: deliver a minimal working solution that can be expanded later.")
        return "\n".join(lines), tool_outputs

    def evaluate(self, result: str, trace: list[str]) -> EvaluationResult:
        evaluation = self.evaluator.evaluate(result)
        self._log(f"[evaluate] score={evaluation.score:.2f} passed={evaluation.passed}", trace)
        return evaluation

    def refine(self, result: str, evaluation: EvaluationResult, trace: list[str]) -> str:
        refined = self.refiner.refine(result, evaluation)
        self._log("[refine] produced improved draft", trace)
        return refined

    def _run_tools(self, task: AgentTask, context: dict[str, Any]) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        for tool_name in task.tools:
            tool = self.tools.get(tool_name)
            if not tool:
                continue
            outputs.append(tool(task.prompt, context))
        return outputs

    def _summarize_history(self, context: dict[str, Any]) -> str:
        history = context.get("history", [])
        if not history:
            return "no prior memory"
        return " | ".join(f"{item['role']}: {item['content']}" for item in history)

    def _log(self, message: str, trace: list[str]) -> None:
        trace.append(message)
        if self.logger:
            self.logger(message)

