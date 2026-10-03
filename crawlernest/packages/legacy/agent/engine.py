from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from agent.evaluator import Evaluator
from agent.memory import Memory
from agent.planner import plan
from agent.refiner import refine_output
from agent.tasks import AgentTask
from agent.tools import (
    apply_patch_to_file,
    evaluate_extractor,
    query_database,
    regression_test_python_function,
    resolve_file_path,
    resolve_function_name,
    run_recommender,
    smoke_test_python_function,
    validate_python_code,
)


DEV_TASK_MARKERS = ("fix", "build", "implement", "extractor", "parser")
MAX_ITERATIONS = 3


@dataclass(slots=True)
class AgentRunResult:
    task: str
    output: str
    score: float
    passed: bool
    iterations: int
    feedback: list[str]
    trace: list[str]


class Agent:
    """Deterministic agent loop with iterative refinement and task-aware targets."""

    def __init__(
        self,
        memory: Memory | None = None,
        evaluator: Evaluator | None = None,
        threshold: float = 0.85,
        memory_limit: int = 5,
        max_iterations: int = MAX_ITERATIONS,
    ) -> None:
        self.memory = memory or Memory()
        self.evaluator = evaluator or Evaluator()
        self.threshold = threshold
        self.memory_limit = memory_limit
        self.max_iterations = max_iterations

    def run(self, task: str) -> dict[str, Any]:
        normalized_task = task.strip() or "generic task"
        context = self._build_agent_context()
        is_dev_task = self._is_dev_task(normalized_task)
        file_path = resolve_file_path(normalized_task) if is_dev_task else None
        function_name = resolve_function_name(normalized_task) if is_dev_task else None
        file_resolution = self._build_file_resolution(normalized_task, is_dev_task, file_path, function_name)
        patch_execution = {
            "attempted": False,
            "executed": False,
            "reason": "Patch tool was not triggered.",
        }
        planned_steps = self._normalize_runtime_steps(plan(normalized_task), normalized_task)
        step_trace = self._initialize_steps(planned_steps)
        self._mark_step(step_trace, "analyze", result=self._analyze_task(normalized_task, is_dev_task))

        mode, generated, improve_result = self._execute_improve_step(normalized_task, context)
        initial_evaluation = self._evaluate(normalized_task, generated)
        initial_score = initial_evaluation["score"]
        initial_reason = initial_evaluation["reason"]

        output = generated
        score = initial_score
        reason = initial_reason
        iterations = 0
        improvement_history: list[dict[str, float]] = [{"score": round(initial_score, 2)}]
        target_score = self._target_score(mode=mode, is_dev_task=is_dev_task)

        self._mark_step(
            step_trace,
            "improve",
            result=improve_result,
            score=round(initial_score, 2),
            reason=initial_reason,
        )

        refinement_used = False
        for attempt in range(self.max_iterations):
            if score >= target_score and not (is_dev_task and attempt == 0):
                break

            candidate_refined = self._refine(normalized_task, output, score, context)
            candidate_evaluation = self._evaluate(normalized_task, candidate_refined)
            candidate_score = candidate_evaluation["score"]
            candidate_reason = candidate_evaluation["reason"]

            if candidate_score <= score:
                break

            refinement_used = True
            output = candidate_refined
            score = candidate_score
            reason = candidate_reason
            iterations += 1
            improvement_history.append({"score": round(candidate_score, 2)})

            if score >= target_score:
                break

        final_result = output
        final_score = round(score, 2)
        final_reason = reason
        improved = final_score > round(initial_score, 2)
        file_patch_result: dict[str, Any] | None = None
        validation_source = final_result
        validation_function = function_name

        if is_dev_task and file_path and function_name:
            patch_execution["attempted"] = True
            patch_candidate = self._prepare_patch_candidate(normalized_task, final_result, generated, function_name)
            file_patch_result = apply_patch_to_file(file_path, patch_candidate, function_name)
            patch_execution["executed"] = True
            patch_execution["reason"] = file_patch_result.get("summary", "Patch tool executed.")
            file_text = self._read_file_text(file_path)
            if file_text:
                validation_source = file_text
                validation_function = function_name
            else:
                patch_execution["reason"] = "Patch tool executed but the target file could not be re-read."
        elif is_dev_task:
            file_patch_result = {
                "type": "file_patch",
                "file": file_path,
                "function": function_name,
                "changed": False,
                "summary": "No matching project file was resolved for this task.",
            }
            patch_execution["attempted"] = True
            if not file_path and not function_name:
                patch_execution["reason"] = "Tool not triggered because neither file path nor function name could be resolved."
            elif not file_path:
                patch_execution["reason"] = "Tool not triggered because the target file could not be resolved."
            elif not function_name:
                patch_execution["reason"] = "Tool not triggered because the target function could not be resolved."
            else:
                patch_execution["reason"] = "Tool not triggered due to a safety block in file-aware mode."

        validate_result: Any = {
            "validation": "validation complete",
            "evaluator": {
                "score": final_score,
                "reason": final_reason,
            },
            "file_patch": {
                "attempted": patch_execution["attempted"],
                "changed": bool(file_patch_result and file_patch_result.get("changed", False)),
            },
        }
        if "extractor" in normalized_task.lower():
            validate_result = {
                "validation": "development validation complete",
                "evaluator": {
                    "score": final_score,
                    "reason": final_reason,
                },
                "tool_result": evaluate_extractor(),
                "file_patch": {
                    "attempted": patch_execution["attempted"],
                    "changed": bool(file_patch_result and file_patch_result.get("changed", False)),
                    "details": file_patch_result,
                },
                "code_validation": validate_python_code(validation_source),
                "smoke_test": smoke_test_python_function(validation_source, validation_function or "extract"),
                "regression_test": regression_test_python_function(validation_source, validation_function or "extract"),
            }
        elif is_dev_task:
            validate_result = {
                "validation": "development validation complete",
                "evaluator": {
                    "score": final_score,
                    "reason": final_reason,
                },
                "file_patch": {
                    "attempted": patch_execution["attempted"],
                    "changed": bool(file_patch_result and file_patch_result.get("changed", False)),
                    "details": file_patch_result,
                },
                "code_validation": validate_python_code(validation_source),
                "smoke_test": smoke_test_python_function(validation_source, validation_function or "run_task"),
                "regression_test": regression_test_python_function(validation_source, validation_function or "run_task"),
            }
        self._mark_step(
            step_trace,
            "refine",
            result="refinement improved the candidate" if refinement_used else "no stronger refined candidate was adopted",
            score=final_score,
            reason=final_reason,
            improved=improved,
        )
        self._mark_step(
            step_trace,
            "validate",
            result=validate_result,
            score=final_score,
            reason=final_reason,
        )

        self._remember_interaction(normalized_task, final_result, final_score)

        return {
            "task": normalized_task,
            "steps": step_trace,
            "mode": mode,
            "file_resolution": file_resolution,
            "patch_execution": patch_execution,
            "generated": generated,
            "initial_score": round(initial_score, 2),
            "initial_reason": initial_reason,
            "refined": output,
            "final_score": final_score,
            "final_reason": final_reason,
            "improved": improved,
            "iterations": iterations,
            "improvement_history": improvement_history,
            "final_result": final_result,
        }

    def generate(self, task: str, context: dict[str, Any]) -> tuple[str, str]:
        mode, generated, _ = self._execute_improve_step(task, context)
        return mode, generated

    def _execute_improve_step(self, task: str, context: dict[str, Any]) -> tuple[str, str, Any]:
        lowered = task.lower()
        task_hints = context.get("task_hints", [])
        summary_line = ", ".join(task_hints[:2]) if task_hints else "none"

        if "recommend" in lowered:
            tool_result = self._run_recommender_for_task(task)
            return (
                "tool",
                self._format_tool_result(task, tool_result),
                {
                    "action": "run_recommender",
                    "tool_result": tool_result,
                },
            )

        if "query" in lowered:
            tool_result = query_database(task)
            return (
                "tool",
                self._format_tool_result(task, tool_result),
                {
                    "action": "query_database",
                    "tool_result": tool_result,
                },
            )

        if "extractor" in lowered:
            tool_result = evaluate_extractor()
            generated = self._build_extractor_candidate()
            return (
                "tool",
                generated,
                {
                    "action": "generate extractor candidate",
                    "tool_result": tool_result,
                },
            )

        if "parser" in lowered:
            generated = "\n".join(
                [
                    "def build_parser(payload):",
                    '    """Parse comma-separated input into a stable token structure."""',
                    "    tokens = [item.strip() for item in payload.split(',') if item.strip()]",
                    "    return {",
                    "        'task_type': 'parser',",
                    "        'tokens': tokens,",
                    "        'count': len(tokens),",
                    "        'status': 'ready',",
                    "    }",
                    "",
                    f"# Prior task hints: {summary_line}",
                ]
            )
            return "generation", generated, "generated parser candidate"

        generated = "\n".join(
            [
                "{",
                f'  "task": "{task}",',
                '  "task_type": "generic",',
                '  "status": "ready",',
                '  "result": "Generated a structured minimal response."',
                "}",
            ]
        )
        return "generation", generated, "generated initial candidate"

    def _evaluate(self, task: str, output: str) -> dict[str, Any]:
        evaluation = self.evaluator.evaluate(output, task)
        return {
            "score": float(evaluation["score"]),
            "reason": str(evaluation["reason"]),
        }

    def _refine(self, task: str, output: str, score: float, context: dict[str, Any]) -> str:
        return refine_output(
            task=task,
            output=output,
            score=score,
            context=context,
        )

    def _target_score(self, mode: str, is_dev_task: bool) -> float:
        if is_dev_task:
            return 0.92
        if mode == "tool":
            return 0.95
        return 0.75

    def _is_dev_task(self, task: str) -> bool:
        lowered = task.lower()
        return any(marker in lowered for marker in DEV_TASK_MARKERS)

    def _format_tool_result(self, task: str, tool_result: dict[str, Any]) -> str:
        return "\n".join(
            [
                "{",
                f'  "task": "{task}",',
                '  "task_type": "tool_result",',
                f'  "tool": "{tool_result["type"]}",',
                f'  "payload": {json.dumps(tool_result, sort_keys=True)}',
                "}",
            ]
        )

    def _run_recommender_for_task(self, task: str) -> dict[str, Any]:
        lowered = task.lower()
        country = "UK" if "uk" in lowered or "united kingdom" in lowered else "United Kingdom"

        ielts_match = re.search(r"ielts\s*([0-9]+(?:\.[0-9]+)?)", task, re.IGNORECASE)
        rank_match = re.search(r"rank\s*([0-9]+)", task, re.IGNORECASE)

        ielts = float(ielts_match.group(1)) if ielts_match else 6.5
        target_rank = int(rank_match.group(1)) if rank_match else 100
        return run_recommender(country=country, ielts=ielts, target_rank=target_rank)

    def _build_agent_context(self) -> dict[str, Any]:
        history = self.memory.recent(limit=self.memory_limit)
        task_hints: list[str] = []
        for item in history:
            if not isinstance(item, dict):
                continue

            role = str(item.get("role", "unknown")).strip() or "unknown"
            task_name = str(item.get("task", "")).strip()
            content = str(item.get("content", "")).strip()

            if task_name:
                task_hints.append(task_name)
            if role == "assistant" and content and len(task_hints) < self.memory_limit:
                task_hints.append(content)

        deduped_hints: list[str] = []
        for hint in task_hints:
            if deduped_hints and deduped_hints[-1] == hint:
                continue
            deduped_hints.append(hint)

        return {
            "task_hints": deduped_hints[: self.memory_limit],
            "message_count": len(history),
        }

    def _build_extractor_candidate(self) -> str:
        return "\n".join(
            [
                "def extract(raw_input):",
                '    """Extract university, program, and quota from raw input safely."""',
                "",
                "    empty_result = {",
                "        'university': None,",
                "        'program': None,",
                "        'quota': None,",
                "    }",
                "",
                "    try:",
                "        if raw_input is None:",
                "            return empty_result",
                "",
                "        if isinstance(raw_input, dict):",
                "            result = _extract_from_dict(raw_input)",
                "            return {",
                "                'university': result.get('university'),",
                "                'program': result.get('program'),",
                "                'quota': result.get('quota'),",
                "            }",
                "",
                "        parsed_json = None",
                "        if isinstance(raw_input, str):",
                "            stripped = raw_input.strip()",
                "            if not stripped:",
                "                return empty_result",
                "            try:",
                "                parsed_json = json.loads(stripped)",
                "            except Exception:",
                "                parsed_json = None",
                "",
                "        if isinstance(parsed_json, dict):",
                "            result = _extract_from_dict(parsed_json)",
                "            if any(value is not None for value in result.values()):",
                "                return {",
                "                    'university': result.get('university'),",
                "                    'program': result.get('program'),",
                "                    'quota': result.get('quota'),",
                "                }",
                "",
                "        text = raw_input if isinstance(raw_input, str) else str(raw_input)",
                "        text = _normalize_text(text)",
                "        if not text:",
                "            return empty_result",
                "",
                "        return {",
                "            'university': _extract_university(text),",
                "            'program': _extract_program(text),",
                "            'quota': _extract_quota(text),",
                "        }",
                "    except Exception:",
                "        return empty_result",
            ]
        )

    def _build_file_resolution(
        self,
        task: str,
        is_dev_task: bool,
        file_path: str | None,
        function_name: str | None,
    ) -> dict[str, Any]:
        if not is_dev_task:
            return {
                "attempted": False,
                "resolved_path": None,
                "function_name": None,
                "reason": "Task is not a development task.",
            }

        lowered = task.lower()
        if "extractor" in lowered:
            preferred_path = "crawlernest-extractors/extractor.py"
            if file_path == preferred_path:
                reason = "Extractor task resolved to the primary extractor path."
            elif file_path:
                reason = (
                    "Primary extractor path was not available; using fallback path "
                    f"{file_path}."
                )
            else:
                reason = "Extractor resolver did not find an available file path."
            return {
                "attempted": True,
                "resolved_path": file_path or preferred_path,
                "function_name": function_name,
                "reason": reason,
            }

        if "parser" in lowered:
            return {
                "attempted": True,
                "resolved_path": file_path or "parser.py",
                "function_name": function_name,
                "reason": "Parser task used parser resolver output.",
            }

        return {
            "attempted": True,
            "resolved_path": file_path,
            "function_name": function_name,
            "reason": "Development task did not match a file-aware resolver target.",
        }

    def _prepare_patch_candidate(
        self,
        task: str,
        final_result: str,
        generated: str,
        function_name: str,
    ) -> str:
        if function_name == "extract":
            for candidate in (final_result, generated):
                if f"def {function_name}(" in candidate:
                    return candidate
            return self._build_extractor_candidate()

        for candidate in (final_result, generated):
            if f"def {function_name}(" in candidate:
                return candidate
        return final_result

    def _read_file_text(self, file_path: str | None) -> str:
        if not file_path:
            return ""
        path = Path(file_path)
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _initialize_steps(self, steps: list[dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "step": step.get("step", ""),
                "goal": step.get("goal", ""),
                "status": "pending",
            }
            for step in steps
        ]

    def _normalize_runtime_steps(
        self,
        steps: list[dict[str, str]],
        task: str,
    ) -> list[dict[str, str]]:
        normalized = list(steps)
        step_names = [step.get("step", "") for step in normalized]
        lowered = task.lower()
        is_tool_task = "recommend" in lowered or "query" in lowered or "extractor" in lowered

        if is_tool_task and "improve" not in step_names:
            insert_at = 1 if step_names and step_names[0] == "analyze" else len(normalized)
            normalized.insert(
                insert_at,
                {
                    "step": "improve",
                    "goal": "Execute the primary candidate generation or tool action for the task.",
                },
            )
            step_names.insert(insert_at, "improve")

        if is_tool_task and "validate" not in step_names:
            normalized.append(
                {
                    "step": "validate",
                    "goal": "Validate the final result and record the outcome.",
                }
            )

        return normalized

    def _mark_step(
        self,
        steps: list[dict[str, Any]],
        step_name: str,
        **updates: Any,
    ) -> None:
        for step in steps:
            if step.get("step") == step_name:
                step["status"] = "done"
                step.update(updates)
                return

    def _analyze_task(self, task: str, is_dev_task: bool) -> str:
        if is_dev_task:
            return f"Development task detected for {task}; stepwise hardening will be applied."
        lowered = task.lower()
        if "recommend" in lowered or "query" in lowered:
            return f"Tool task detected for {task}; planner will keep execution lightweight."
        return f"Generic task detected for {task}; planner will execute a minimal step path."

    def _remember_interaction(self, task: str, result: str, score: float) -> None:
        summary = self._summarize_result(task, result)
        self.memory.add("user", task, task=task, content=task)
        self.memory.add("assistant", task, content=summary)

    def _summarize_result(self, task: str, result: str) -> str:
        lowered_task = task.lower()
        if '"task_type": "tool_result"' in result:
            return "tool-backed structured response"
        if "extractor" in lowered_task:
            return "extractor output with normalized fields"
        if "parser" in lowered_task:
            return "parser output with token structure"
        if '"task_type": "generic"' in result:
            return "generic structured response"
        return "structured agent response"


class AgentEngine:
    """Compatibility wrapper for existing runner usage."""

    def __init__(
        self,
        evaluator: Evaluator | None = None,
        refiner: Any | None = None,
        tools: dict[str, Any] | None = None,
        threshold: float = 0.85,
        max_iterations: int = MAX_ITERATIONS,
        logger: Any | None = None,
    ) -> None:
        self.threshold = threshold
        self.logger = logger
        self.agent = Agent(
            evaluator=evaluator,
            threshold=threshold,
            max_iterations=max_iterations,
        )

    def run(self, task: AgentTask, memory: Memory) -> AgentRunResult:
        self.agent.memory = memory
        result = self.agent.run(task.prompt)
        trace = [
            f"[engine] task={result['task']}",
            f"[evaluate] initial_score={result['initial_score']:.2f}",
            f"[evaluate] final_score={result['final_score']:.2f}",
        ]

        if self.logger:
            for message in trace:
                self.logger(message)

        return AgentRunResult(
            task=result["task"],
            output=result["final_result"],
            score=result["final_score"],
            passed=result["final_score"] >= self.threshold,
            iterations=int(result.get("iterations", 0)),
            feedback=[result["final_reason"]],
            trace=trace,
        )
