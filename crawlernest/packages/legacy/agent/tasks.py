from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentTask:
    """Simple task contract for the agent engine."""

    name: str
    prompt: str
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def infer_tools(prompt: str) -> list[str]:
    lowered = prompt.lower()
    tools: list[str] = []

    if any(keyword in lowered for keyword in ("recommend", "university", "database", "uk")):
        tools.append("query_database")
    if any(keyword in lowered for keyword in ("extractor", "parser", "fix")):
        tools.append("evaluate_extractor")

    return tools


def create_task(prompt: str) -> AgentTask:
    slug = prompt.strip().lower().replace(" ", "-") or "ad-hoc-task"
    return AgentTask(
        name=slug,
        prompt=prompt.strip(),
        tools=infer_tools(prompt),
        metadata={"source": "user"},
    )

