from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

AgentMode = Literal["dev", "web"]
TaskSource = Literal["web", "cli", "api-dev", "system"]
TaskKind = Literal[
    "dev_refinement",
    "data_query",
    "recommendation",
    "ranking_explain",
    "university_lookup",
]


@dataclass(slots=True)
class TaskRequest:
    task_id: str
    mode: AgentMode
    kind: TaskKind
    user_input: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    source: TaskSource = "web"
    # Optional session identifier for multi-turn conversation memory.
    # None means the request is stateless (no history loaded or stored).
    session_id: str | None = None
