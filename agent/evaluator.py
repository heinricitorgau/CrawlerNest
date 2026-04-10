from __future__ import annotations

import json
from typing import Any


def _safe_json_loads(output: str) -> dict[str, Any] | None:
    text = output.strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _task_keywords(task: str) -> set[str]:
    task_lower = task.lower()
    keywords: set[str] = set()
    for key in ("extractor", "parser", "recommend", "query", "rank", "ielts", "country"):
        if key in task_lower:
            keywords.add(key)
    return keywords


def _memory_relevant(task: str, memory_hint: str) -> bool:
    if not memory_hint:
        return True

    task_lower = task.lower()
    hint_lower = memory_hint.lower()

    categories = {
        "extractor": "extractor",
        "parser": "parser",
        "recommend": "recommend",
        "query": "query",
    }

    matched_task = {name for key, name in categories.items() if key in task_lower}
    matched_hint = {name for key, name in categories.items() if key in hint_lower}

    if matched_task and matched_hint:
        return bool(matched_task.intersection(matched_hint))

    task_words = {word for word in task_lower.replace("-", " ").split() if len(word) > 3}
    hint_words = {word for word in hint_lower.replace("-", " ").split() if len(word) > 3}
    return bool(task_words.intersection(hint_words))


def _is_dev_task(task: str) -> bool:
    lowered = task.lower()
    return any(marker in lowered for marker in ("fix", "build", "implement", "extractor", "parser"))


def _is_vague_task(task: str) -> bool:
    lowered = task.lower().strip()
    vague_markers = (
        "do something",
        "help me",
        "make it better",
    )
    return any(marker in lowered for marker in vague_markers)


def evaluate_output(output: str, task: str) -> dict[str, Any]:
    """Deterministically score output quality while penalizing fabricated values."""

    normalized = output.lower()
    parsed_json = _safe_json_loads(output)

    structure_score = 0.0
    relevance_score = 0.0
    specificity_score = 0.0
    penalty = 0.0
    notes: list[str] = []

    if parsed_json is not None:
        structure_score += 0.2
        notes.append("valid JSON object")
        required_fields = {"task", "status"}
        present = len(required_fields.intersection(parsed_json.keys()))
        structure_score += min(0.2, present * 0.1)
        if any(key in parsed_json for key in ("result", "payload", "explanation")):
            structure_score += 0.1
        structure_score = min(structure_score, 0.4)
    else:
        structure_markers = 0
        for marker in ("def ", "return {", "task_type", "status", "{", "}"):
            if marker in output:
                structure_markers += 1
        structure_score = min(0.4, structure_markers * 0.07)
        notes.append("partial structure detected" if structure_markers else "weak structure")

    task_keys = _task_keywords(task)
    if "extractor" in task.lower():
        if "extractor" in normalized:
            relevance_score += 0.18
        if any(token in normalized for token in ("rank", "source", "title")):
            relevance_score += 0.12
    elif "parser" in task.lower():
        if "parser" in normalized or "tokens" in normalized:
            relevance_score += 0.18
        if "count" in normalized or "payload" in normalized:
            relevance_score += 0.12
    elif "recommend" in task.lower():
        if "recommendation" in normalized or "results" in normalized:
            relevance_score += 0.18
        if any(token in normalized for token in ("ielts", "target_rank", "country")):
            relevance_score += 0.12
    elif "query" in task.lower():
        if "db_query" in normalized or '"query"' in normalized:
            relevance_score += 0.18
        if "results" in normalized:
            relevance_score += 0.12
    else:
        if "task" in normalized and "result" in normalized:
            relevance_score += 0.2
        if "status" in normalized:
            relevance_score += 0.1

    if parsed_json is not None:
        if "payload" in parsed_json and isinstance(parsed_json["payload"], dict):
            payload = parsed_json["payload"]
            if payload.get("results") or payload.get("score") is not None:
                specificity_score += 0.2
                notes.append("real tool payload preserved")
        if "explanation" in parsed_json:
            explanation = str(parsed_json["explanation"]).strip().lower()
            if explanation and "preserved" in explanation or "original" in explanation or "readability" in explanation:
                specificity_score += 0.1
                notes.append("accurate explanation present")
        if any(key in parsed_json for key in ("score", "target_rank", "count", "status", "tool")):
            specificity_score += 0.08
    else:
        detail_markers = ("rank", "source", "tokens", "count", "status", "results")
        detail_hits = sum(1 for marker in detail_markers if marker in normalized)
        specificity_score += min(0.18, detail_hits * 0.03)
        if len(output.strip()) > 180:
            specificity_score += 0.04
        if "isinstance(" in output:
            specificity_score += 0.1
            notes.append("input validation present")
        if "try:" in output and "except" in output:
            specificity_score += 0.1
            notes.append("edge case handling present")
        if " is none" in normalized or "if input_value is None" in output or "if payload is None" in output:
            specificity_score += 0.1
            notes.append("none handling present")
        if '"""' in output:
            specificity_score += 0.05
            notes.append("code documentation present")

    if _is_vague_task(task):
        if "generic" in normalized:
            penalty += 0.2
            notes.append("generic output for vague task")
        if not any(token in normalized for token in ("result", "status", "return", "payload", "results")):
            penalty += 0.2
            notes.append("no concrete action or result")
        if "structured minimal response" in normalized or "template" in normalized:
            penalty += 0.1
            notes.append("template-only response")

    if _is_dev_task(task) and not any(
        marker in output for marker in ("isinstance(", "try:", "except", '"""')
    ):
        penalty += 0.1
        notes.append("development output lacks robustness signals")

    fake_markers = (
        "normalized_rank",
        "normalized_title",
        "normalized_source",
        "item_a",
        "item_b",
        "crawler_source",
        "placeholder",
    )
    if any(marker in normalized for marker in fake_markers):
        penalty += 0.3
        notes.append("fabricated or altered values detected")

    placeholder_markers = ("normalized_", "unknown_tool", "value_here", "fake", "sample_value")
    if any(marker in normalized for marker in placeholder_markers):
        penalty += 0.2
        notes.append("placeholder values detected")

    if "memory_hint" in normalized:
        memory_hint = ""
        if parsed_json is not None:
            memory_hint = str(parsed_json.get("memory_hint", "")).strip()
        if memory_hint and not _memory_relevant(task, memory_hint):
            penalty += 0.2
            notes.append("irrelevant memory used")

    if "user:" in normalized or "assistant:" in normalized or "system:" in normalized:
        penalty += 0.1
        notes.append("raw memory leakage detected")

    total_score = round(structure_score + relevance_score + specificity_score - penalty, 2)
    total_score = max(0.0, min(total_score, 0.95))

    if _is_vague_task(task):
        total_score = min(total_score, 0.75)

    if total_score >= 0.85:
        reason = "Output is well structured, preserves original data, and is specific enough to trust."
    elif total_score >= 0.65:
        reason = "Output is usable but still has weaknesses in structure, specificity, or trust signals."
    else:
        reason = "Output is weak or potentially untrustworthy and should not be preferred without refinement."

    return {
        "score": total_score,
        "reason": reason,
        "details": {
            "structure": round(structure_score, 2),
            "relevance": round(relevance_score, 2),
            "specificity": round(specificity_score, 2),
            "penalty": round(penalty, 2),
            "notes": notes,
        },
    }


class Evaluator:
    """Lightweight deterministic evaluator."""

    def evaluate(self, output: str, task: str) -> dict[str, Any]:
        return evaluate_output(output, task)
