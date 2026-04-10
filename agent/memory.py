from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Memory:
    """Tiny in-memory conversation store."""

    messages: list[dict[str, Any]] = field(default_factory=list)

    def add(self, role: str, content: str, **extra: Any) -> None:
        entry = {"role": role, "content": content}
        entry.update(extra)
        self.messages.append(entry)

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        return self.messages[-limit:]

    def build_context(self, limit: int = 5) -> dict[str, Any]:
        return {
            "history": self.recent(limit=limit),
            "message_count": len(self.messages),
        }

