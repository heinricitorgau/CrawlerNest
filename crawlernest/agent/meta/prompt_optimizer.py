from __future__ import annotations

from typing import Any


class PromptOptimizer:
    def generate(
        self,
        *,
        task_kind: str,
        performance: dict[str, Any],
        experiences: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        avg_score = float(performance.get("avg_score", 0.0))
        failure_rate = float(performance.get("failure_rate", 0.0))
        if avg_score >= 0.82 and failure_rate < 0.3:
            return None

        prompt_patch: list[str] = []
        if task_kind == "ranking_explain":
            prompt_patch = [
                "Always mention the clearest rank signal before interpretation.",
                "Include comparison context when another university is explicitly present.",
                "State page-level evidence limits when the retrieval slice is partial.",
            ]
        elif task_kind == "recommendation":
            prompt_patch = [
                "Restate country and language constraints before giving recommendations.",
                "Explain fit, risk, and uncertainty for each suggested university.",
            ]
        elif task_kind == "university_lookup":
            prompt_patch = [
                "Answer identity or location questions directly before adding supporting details.",
                "Explicitly say when preview sections are missing instead of inferring facts.",
            ]
        elif task_kind == "data_query":
            prompt_patch = [
                "Summarize the current slice before listing rows.",
                "Mention counts and filters only when they support the answer.",
            ]
        if not prompt_patch:
            return None

        confidence = max(0.7, min(0.9, 1.0 - failure_rate / 2.0))
        return {
            "strategy_type": "prompt_patch",
            "strategy": prompt_patch,
            "confidence": confidence,
            "reason": "experience_analysis",
            "rollout_percent": 30,
        }
