from __future__ import annotations

from typing import Any


class ChangeSummaryBuilder:
    def build(
        self,
        *,
        task: str,
        resolution_result: dict[str, Any],
        file_patch: dict[str, Any],
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        file_path = resolution_result.get("file_path")
        symbol = resolution_result.get("symbol")
        confidence = resolution_result.get("confidence", "low")

        points = []
        if file_path:
            points.append(f"Targeted file: {file_path}")
        if symbol:
            points.append(f"Primary edit scope: {symbol}")
        for change in file_patch.get("changes", [])[:3]:
            description = change.get("description")
            if description:
                points.append(str(description))

        if validation.get("status") == "pass":
            points.append("Current file resolution and basic structural validation passed.")
        elif validation.get("checks"):
            points.append("Validation surfaced follow-up checks before applying a real patch.")

        risk_level = "low"
        if confidence == "low" or not file_path:
            risk_level = "medium"
        if file_path and "extractor" in str(file_path).lower() and not symbol:
            risk_level = "medium"

        return {
            "title": self._title(task, file_path=file_path, symbol=symbol),
            "points": points,
            "risk_level": risk_level,
        }

    def _title(self, task: str, *, file_path: str | None, symbol: str | None) -> str:
        if symbol:
            return f"Refine {symbol}"
        if file_path:
            return f"Refine {file_path.split('/')[-1]}"
        return f"Refine implementation for: {task}"
