from __future__ import annotations

from collections import Counter
from typing import Any


class PerformanceTracker:
    def analyze(
        self,
        *,
        experiences: list[dict[str, Any]],
        task_kind: str,
    ) -> dict[str, Any]:
        if not experiences:
            return {
                "task_kind": task_kind,
                "sample_size": 0,
                "avg_score": 0.0,
                "failure_rate": 0.0,
                "success_rate": 0.0,
                "common_failure_step": None,
            }

        scores = [float(item.get("final_score", 0.0)) for item in experiences]
        failures = [
            item for item in experiences
            if str(item.get("status", "")).lower() not in {"success", "pass"}
            or float(item.get("final_score", 0.0)) < 0.8
        ]
        failed_steps: list[str] = []
        for item in failures:
            for step in item.get("steps", []) if isinstance(item.get("steps"), list) else []:
                if not isinstance(step, dict):
                    continue
                score = float(step.get("score", 0.0))
                if score < 0.7:
                    step_name = str(step.get("step") or "").strip()
                    if step_name:
                        failed_steps.append(step_name)
        common_failure_step = Counter(failed_steps).most_common(1)[0][0] if failed_steps else None
        success_count = sum(1 for item in experiences if str(item.get("status", "")).lower() in {"success", "pass"})
        return {
            "task_kind": task_kind,
            "sample_size": len(experiences),
            "avg_score": sum(scores) / max(1, len(scores)),
            "failure_rate": len(failures) / max(1, len(experiences)),
            "success_rate": success_count / max(1, len(experiences)),
            "common_failure_step": common_failure_step,
        }
