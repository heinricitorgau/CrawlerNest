from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TaskStatus = Literal["success", "error", "rejected", "partial"]


@dataclass(slots=True)
class TaskResponse:
    task_id: str
    status: TaskStatus
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    traces: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
