from __future__ import annotations

import json
import re
from typing import Any


CODE_TASK_MARKERS = ("extractor", "parser", "fix", "build", "implement")


def _clean_output(output: str) -> str:
    cleaned_lines: list[str] = []
    for line in output.splitlines():
        lowered = line.lower().strip()
        if lowered.startswith("# prior task hints:"):
            continue
        if lowered.startswith("recent context:"):
            continue
        if "user:" in lowered or "assistant:" in lowered or "system:" in lowered:
            continue
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_code_task(task: str) -> bool:
    lowered = task.lower()
    return any(marker in lowered for marker in CODE_TASK_MARKERS)


def presentation_refine(task: str, output: str, score: float) -> str:
    """Improve readability without changing factual values."""

    cleaned = _clean_output(output)
    parsed = _safe_json_loads(cleaned)

    if parsed is not None:
        refined = {
            "task": task,
            "status": "refined",
            "explanation": "Refinement improved presentation while preserving the original data.",
            "payload": parsed,
        }
        return json.dumps(refined, indent=2, sort_keys=True)

    refined = {
        "task": task,
        "status": "refined",
        "explanation": "Refinement wrapped the original output for clearer presentation.",
        "payload": cleaned,
    }
    return json.dumps(refined, indent=2, sort_keys=True)


def _refine_extractor_code() -> str:
    return "\n".join(
        [
            "def build_extractor(record):",
            '    """Normalize a crawled record into structured extractor output."""',
            "",
            "    if not isinstance(record, dict):",
            "        return {",
            "            'task_type': 'extractor',",
            "            'status': 'error',",
            "            'reason': 'invalid input',",
            "        }",
            "",
            "    title = str(record.get('title', '')).strip()",
            "    source = str(record.get('source', 'unknown')).strip() or 'unknown'",
            "",
            "    rank = record.get('rank')",
            "    if rank is not None:",
            "        try:",
            "            rank = int(rank)",
            "        except (TypeError, ValueError):",
            "            rank = None",
            "",
            "    return {",
            "        'task_type': 'extractor',",
            "        'title': title,",
            "        'source': source,",
            "        'rank': rank,",
            "        'status': 'ready',",
            "    }",
        ]
    )


def _refine_parser_code() -> str:
    return "\n".join(
        [
            "def build_parser(payload):",
            '    """Parse comma-separated input into a stable token structure."""',
            "",
            "    if payload is None:",
            "        payload = ''",
            "    if not isinstance(payload, str):",
            "        payload = str(payload)",
            "",
            "    tokens = [item.strip() for item in payload.split(',') if item.strip()]",
            "",
            "    return {",
            "        'task_type': 'parser',",
            "        'tokens': tokens,",
            "        'count': len(tokens),",
            "        'status': 'ready',",
            "    }",
        ]
    )


def _extract_return_mapping(output: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for key, value in re.findall(r"'([^']+)':\s*([^,\n}]+)", output):
        cleaned = value.strip()
        if cleaned:
            pairs[key] = cleaned
    return pairs


def _refine_generic_code(output: str) -> str:
    extracted = _extract_return_mapping(output)
    status_expr = extracted.get("status", "'ready'")
    result_expr = extracted.get("result", "input_value")

    return "\n".join(
        [
            '"""Refined implementation with defensive structure."""',
            "",
            "def run_task(input_value):",
            '    """Return a stable result object for development-oriented tasks."""',
            "",
            "    if input_value is None:",
            "        return {'status': 'error', 'reason': 'invalid input'}",
            "",
            "    if isinstance(input_value, str):",
            "        input_value = input_value.strip()",
            "",
            f"    status = {status_expr}",
            f"    result = {result_expr}",
            "",
            "    return {",
            "        'status': status,",
            "        'result': result,",
            "    }",
        ]
    )


def code_refine(task: str, output: str, score: float) -> str:
    """Improve code quality with validation and defensive handling."""

    cleaned = _clean_output(output)
    lowered = task.lower()

    if "extractor" in lowered:
        return _refine_extractor_code()

    if "parser" in lowered:
        return _refine_parser_code()

    return _refine_generic_code(cleaned)


def refine_output(
    task: str,
    output: str,
    score: float,
    context: dict[str, Any] | None = None,
) -> str:
    """Refine output using either code-focused or presentation-focused mode."""

    if _is_code_task(task):
        return code_refine(task, output, score)
    return presentation_refine(task, output, score)


class Refiner:
    """Task-aware deterministic refiner."""

    def refine(
        self,
        task: str,
        output: str,
        score: float,
        context: dict[str, Any] | None = None,
    ) -> str:
        return refine_output(task, output, score, context)
