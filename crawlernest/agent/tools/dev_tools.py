from __future__ import annotations

from typing import Any


class DevTools:
    def collect_context(self, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "target": context.get("target", "unspecified"),
            "notes": context.get("notes", []),
        }

    def suggest_refinement_loop(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "task": user_input,
            "loop": ["evaluate", "modify", "re-evaluate", "keep_or_revert"],
            "context": self.collect_context(context),
        }

