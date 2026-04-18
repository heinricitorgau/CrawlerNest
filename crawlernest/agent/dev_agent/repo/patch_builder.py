from __future__ import annotations

from typing import Any


class PatchBuilder:
    def build(
        self,
        *,
        task: str,
        resolution_result: dict[str, Any],
        repo_index: dict[str, Any],
    ) -> dict[str, Any]:
        file_path = resolution_result.get("file_path")
        symbol = resolution_result.get("symbol")
        lowered = task.lower()

        if file_path and symbol:
            return {
                "file": file_path,
                "changes": [
                    {
                        "type": "modify_function",
                        "target": symbol,
                        "description": self._describe_change(task, symbol=symbol),
                        "patch_hint": self._patch_hint(task, symbol=symbol),
                    },
                    {
                        "type": "add_validation",
                        "description": "Ensure the updated function handles invalid or missing inputs safely.",
                    },
                ],
            }

        if file_path:
            change_type = "improve_extractor" if "extractor" in lowered else "modify_file"
            return {
                "file": file_path,
                "changes": [
                    {
                        "type": change_type,
                        "target": "file_scope",
                        "description": self._describe_change(task),
                        "patch_hint": self._patch_hint(task),
                    },
                    {
                        "type": "add_validation",
                        "description": "Add lightweight guardrails or structural checks before returning the updated result.",
                    },
                ],
            }

        return {
            "file": None,
            "changes": [
                {
                    "type": "generic_suggestion",
                    "target": "unspecified",
                    "description": "No concrete file was resolved, so the patch remains a high-level refinement suggestion.",
                    "patch_hint": "Identify the primary implementation file first, then tighten error handling and validation around the failing path.",
                }
            ],
        }

    def _describe_change(self, task: str, symbol: str | None = None) -> str:
        if symbol:
            return f"Refine {symbol} so it better satisfies: {task}"
        return f"Refine the resolved file to better satisfy: {task}"

    def _patch_hint(self, task: str, symbol: str | None = None) -> str:
        lowered = task.lower()
        target = symbol or "the target area"
        if "extractor" in lowered:
            return f"Add robust fallback parsing and input checks around {target}."
        if "validation" in lowered or "invalid" in lowered:
            return f"Wrap {target} with precondition checks and safer failure handling."
        if "parser" in lowered:
            return f"Restructure {target} so parsing branches are easier to validate and less brittle."
        return f"Introduce a small, testable change inside {target} and keep surrounding behavior stable."
