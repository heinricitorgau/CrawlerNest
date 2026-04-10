from __future__ import annotations

try:
    from evaluator import evaluate_output
    from memory import Memory
    from refiner import refine_output
    from tasks import classify_task
    from tools import TOOLS
except ModuleNotFoundError:
    from .evaluator import evaluate_output
    from .memory import Memory
    from .refiner import refine_output
    from .tasks import classify_task
    from .tools import TOOLS


class Agent:
    def __init__(self, memory: Memory | None = None) -> None:
        self.memory = memory or Memory()

    def run(self, task: str) -> dict:
        context = self.memory.get_context()
        output = self.generate(task, context)
        evaluation = evaluate_output(output)
        score = float(evaluation["score"])
        initial_score = score
        refined = False

        if score < 0.7:
            output = refine_output(output, list(evaluation["feedback"]))
            evaluation = evaluate_output(output)
            score = float(evaluation["score"])
            refined = True

        self.memory.add(task, output)
        return {
            "result": output,
            "score": score,
            "initial_score": initial_score,
            "feedback": evaluation["feedback"],
            "refined": refined,
        }

    def generate(self, task: str, context: list[dict[str, str]]) -> str:
        task_type = classify_task(task)
        tool_lines: list[str] = []

        if task_type == "extractor":
            tool_result = TOOLS["evaluate_extractor"]()
            tool_lines.append(f"# Tool Result: {tool_result}")
            return "\n".join(
                [
                    "def build_extractor(record):",
                    '    """Mock extractor implementation for CrawlerNest."""',
                    "    title = record.get('title', '').strip()",
                    "    ranking = record.get('ranking', 'unknown')",
                    "    return {'title': title, 'ranking': ranking, 'status': 'extracted'}",
                    "",
                    f"# Memory size: {len(context)}",
                    *tool_lines,
                ]
            )

        if task_type == "parser":
            tool_result = TOOLS["query_database"]()
            tool_lines.append(f"# Tool Result: {tool_result}")
            return "\n".join(
                [
                    "def parse_input(payload):",
                    "    tokens = [part.strip() for part in payload.split(',') if part.strip()]",
                    "    return {'type': 'parser', 'tokens': tokens, 'count': len(tokens)}",
                    "",
                    "def validate_payload(payload):",
                    "    return bool(payload and payload.strip())",
                    "",
                    f"# Memory size: {len(context)}",
                    *tool_lines,
                ]
            )

        return "\n".join(
            [
                f"Task received: {task}",
                f"Memory items available: {len(context)}",
                "Result: generated a generic response with a concrete return path.",
                "return {'status': 'ok', 'task': task}",
            ]
        )
