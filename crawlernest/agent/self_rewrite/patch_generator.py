from __future__ import annotations

from typing import Any

from crawlernest.agent.dev_agent.repo.patch_builder import PatchBuilder


class PatchGenerator:
    def __init__(self, *, patch_builder: PatchBuilder | None = None) -> None:
        self._patch_builder = patch_builder or PatchBuilder()

    def generate(
        self,
        *,
        task: str,
        resolution_result: dict[str, Any],
        repo_index: dict[str, Any],
    ) -> dict[str, Any]:
        semantic_patch = self._patch_builder.build(
            task=task,
            resolution_result=resolution_result,
            repo_index=repo_index,
        )
        changes = semantic_patch.get("changes", []) if isinstance(semantic_patch, dict) else []
        first_change = changes[0] if changes and isinstance(changes[0], dict) else {}
        target_file = semantic_patch.get("file")
        target_symbol = resolution_result.get("symbol")
        change_type = str(first_change.get("type") or "generic_suggestion")
        patch_hint = str(first_change.get("patch_hint") or first_change.get("description") or "").strip()
        reason = self._build_reason(task=task, resolution_result=resolution_result)

        return {
            "target_file": target_file,
            "target_symbol": target_symbol,
            "change_type": change_type,
            "patch": patch_hint,
            "reason": reason,
            "scope": "function" if target_symbol else ("file" if target_file else "generic"),
            "semantic_patch": semantic_patch,
        }

    def _build_reason(self, *, task: str, resolution_result: dict[str, Any]) -> str:
        symbol = resolution_result.get("symbol")
        file_path = resolution_result.get("file_path")
        if symbol:
            return f"{symbol} appears to be the most relevant function for: {task}"
        if file_path:
            return f"{file_path} appears to be the best local file target for: {task}"
        return f"The task still needs a more precise target before a concrete rewrite can be approved: {task}"
