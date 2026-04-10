from __future__ import annotations


def classify_task(task: str) -> str:
    lowered = task.lower()
    if "extractor" in lowered:
        return "extractor"
    if "parser" in lowered:
        return "parser"
    return "generic"

