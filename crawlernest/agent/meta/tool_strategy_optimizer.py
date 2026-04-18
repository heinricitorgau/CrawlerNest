from __future__ import annotations

from typing import Any


class ToolStrategyOptimizer:
    def generate(
        self,
        *,
        engine: str,
        task_kind: str,
        performance: dict[str, Any],
        experiences: list[dict[str, Any]],
        target: str | None = None,
    ) -> dict[str, Any] | None:
        avg_score = float(performance.get("avg_score", 0.0))
        failure_rate = float(performance.get("failure_rate", 0.0))
        common_failure_step = performance.get("common_failure_step")
        normalized_target = (target or "").strip().lower()

        if avg_score >= 0.82 and failure_rate < 0.3 and common_failure_step not in {"validate", "apply_refinement"}:
            return None

        strategy: list[str] = []
        if engine == "dev":
            if common_failure_step == "validate" or avg_score < 0.8:
                strategy.append("Always run validation immediately after semantic patch planning.")
            if common_failure_step == "apply_refinement":
                strategy.append("Tighten semantic patch scope before attempting another refinement step.")
            if "extractor" in normalized_target or any("extractor" in str(item.get("task", "")).lower() for item in experiences):
                strategy.append("Retry extractor refinement once with stricter type-safety hints before failing.")
        else:
            if task_kind == "recommendation":
                strategy.append("Resolve recommendation constraints before generation and keep recommendation retrieval authoritative.")
            elif task_kind == "ranking_explain":
                strategy.append("Prefer ranking retrieval before generation; do not skip direct entity lookup.")
            elif task_kind == "university_lookup":
                strategy.append("Prefer direct preview lookup before falling back to broader ranking explanation.")

        if not strategy:
            return None

        confidence = max(0.7, min(0.88, 1.0 - failure_rate / 2.5))
        return {
            "strategy_type": "tool_strategy",
            "strategy": strategy,
            "confidence": confidence,
            "reason": "experience_analysis",
            "rollout_percent": 30,
        }
