from __future__ import annotations

from typing import Any, Callable


ToolFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def query_database(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    """Mock database lookup for recommendation-like tasks."""
    recommendations = [
        {"name": "University of Leeds", "country": "United Kingdom", "ielts": 6.5},
        {"name": "University of Leicester", "country": "United Kingdom", "ielts": 6.5},
        {"name": "Queen's University Belfast", "country": "United Kingdom", "ielts": 6.5},
    ]
    return {
        "tool": "query_database",
        "summary": f"Found {len(recommendations)} mock records for prompt: {prompt}",
        "records": recommendations,
        "context_messages": context.get("message_count", 0),
    }


def evaluate_extractor(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    """Mock extractor analysis for development tasks."""
    return {
        "tool": "evaluate_extractor",
        "summary": "Extractor health is moderate; parser edge cases still need cleanup.",
        "signals": {
            "coverage": 0.72,
            "stability": 0.68,
            "history_used": len(context.get("history", [])),
        },
        "task_hint": prompt,
    }


def get_default_tools() -> dict[str, ToolFn]:
    return {
        "query_database": query_database,
        "evaluate_extractor": evaluate_extractor,
    }

