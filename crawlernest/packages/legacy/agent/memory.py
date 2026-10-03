from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def summarize_output(output: str) -> str:
    normalized = " ".join((output or "").strip().split()).lower()

    if not normalized:
        return ""
    if "extractor" in normalized:
        return "generated extractor helper"
    if "parser" in normalized or "tokens" in normalized:
        return "returned parser function with token split logic"
    if '"task_type": "tool_result"' in output or '"payload"' in output:
        return "returned structured tool result"
    if '"task_type": "generic"' in output or '"result"' in output:
        return "returned generic structured response"
    if "recommendation" in normalized or "db_query" in normalized:
        return "returned structured tool response"

    words = normalized.split()
    summary = " ".join(words[:8])
    return summary[:80].strip()


@dataclass(slots=True)
class Memory:
    """Small, safe in-memory store for recent summarized interactions."""

    max_items: int = 20
    debug: bool = False
    items: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.clean()

    def _normalize(self, item: Any) -> dict[str, str] | None:
        if item is None:
            return None

        if isinstance(item, dict):
            role = str(item.get("role", "unknown")).strip() or "unknown"
            task = str(item.get("task", "")).strip()
            content = str(item.get("content", "")).strip()

            if not content and not task:
                return None

            return {
                "role": role,
                "task": task,
                "content": content,
            }

        if isinstance(item, str):
            content = item.strip()
            if not content:
                return None
            return {
                "role": "unknown",
                "task": "",
                "content": content,
            }

        return None

    def add(
        self,
        role: str,
        task_or_content: str,
        content: str | None = None,
        **extra: Any,
    ) -> None:
        """Store a normalized dict entry and reject empty records.

        This supports both:
        - add(role, task, content)
        - legacy add(role, content) calls
        """

        explicit_task = str(extra.get("task", "")).strip()
        explicit_content = str(extra.get("content", "")).strip()

        if content is None:
            raw_task = explicit_task
            raw_content = explicit_content or task_or_content
        else:
            raw_task = explicit_task or task_or_content
            raw_content = explicit_content or content

        role_value = str(role).strip() or "unknown"
        task_value = str(raw_task).strip()
        content_value = str(raw_content).strip()

        if not task_value and not content_value:
            return

        entry = {
            "role": role_value,
            "task": task_value,
            "content": content_value,
        }
        normalized = self._normalize(entry)
        if normalized is None:
            return

        self.items.append(normalized)
        self.clean()

    def add_interaction(self, user_task: str, assistant_output: str) -> None:
        task_value = str(user_task).strip()
        summary = self.summarize_output(assistant_output)

        if task_value:
            self.add("user", task_value, task_value)
        if summary:
            self.add("assistant", task_value, summary)

    def summarize_output(self, output: str) -> str:
        return summarize_output(output)

    def get_all(self) -> list[dict[str, str]]:
        return [item for item in (self._normalize(item) for item in self.items) if item is not None]

    def recent(self, limit: int = 5) -> list[dict[str, str]]:
        if limit <= 0:
            return []
        normalized = self.get_all()
        return normalized[-limit:]

    def get_context(self) -> str:
        recent_items = self.recent(limit=5)
        if not recent_items:
            return "Recent context: none"

        lines = ["Recent context:"]
        for item in recent_items:
            role = item.get("role", "unknown")
            task = item.get("task", "")
            content = item.get("content", "")
            task_part = task or "-"
            content_part = content or "-"
            lines.append(f"- role: {role} | task: {task_part} | content: {content_part}")
        return "\n".join(lines)

    def build_context(self, limit: int = 5) -> dict[str, object]:
        history = self.recent(limit=limit)
        return {
            "history": history,
            "context": self.get_context(),
            "message_count": len(history),
        }

    def clear(self) -> None:
        self.items.clear()

    def clean(self) -> None:
        normalized_items: list[dict[str, str]] = []
        for item in self.items:
            normalized = self._normalize(item)
            if normalized is None:
                continue
            if normalized_items and normalized_items[-1] == normalized:
                continue
            normalized_items.append(normalized)

        if len(normalized_items) > self.max_items:
            normalized_items = normalized_items[-self.max_items :]

        self.items = normalized_items

        if self.debug:
            print("[MEMORY]", self.items)
