from __future__ import annotations

from typing import Any


class ImprovementEngine:
    def generate(
        self,
        *,
        engine: str,
        task_kind: str,
        performance: dict[str, Any],
        experiences: list[dict[str, Any]],
        target: str | None = None,
    ) -> dict[str, Any] | None:
        if not self._should_generate(performance):
            return None

        strategies: list[str] = []
        reason_parts: list[str] = []
        common_failure_step = performance.get("common_failure_step")
        avg_score = float(performance.get("avg_score", 0.0))
        failure_rate = float(performance.get("failure_rate", 0.0))
        normalized_target = (target or "").strip().lower()

        if engine == "dev":
            if common_failure_step == "validate" or avg_score < 0.8:
                strategies.append("Always validate after each refinement attempt before accepting the patch plan.")
            if "extractor" in normalized_target or any("extractor" in str(item.get("task", "")).lower() for item in experiences):
                strategies.extend(
                    [
                        "Handle None and invalid rank values explicitly in extractor-facing changes.",
                        "Prefer type-safe return normalization before leaving extractor code paths.",
                    ]
                )
            if "parser" in normalized_target or any("parser" in str(item.get("task", "")).lower() for item in experiences):
                strategies.append("Normalize parser edge cases before adding new branch-specific logic.")
            if not strategies:
                strategies.append("Keep changes scoped, then validate before proposing additional refinement.")
            reason_parts.append("dev refinement performance dropped below the preferred threshold")
        else:
            if task_kind == "ranking_explain":
                strategies.extend(
                    [
                        "Anchor ranking explanations to the strongest direct retrieval signal before adding interpretation.",
                        "State page-level limitations clearly when ranking evidence is partial.",
                    ]
                )
            elif task_kind == "recommendation":
                strategies.extend(
                    [
                        "Parse country and language constraints before presenting recommendation reasoning.",
                        "Make tradeoffs and uncertainty explicit when recommendation evidence is incomplete.",
                    ]
                )
            elif task_kind == "university_lookup":
                strategies.extend(
                    [
                        "Answer identity or location questions directly before adding optional background.",
                        "Say when preview data is missing instead of filling gaps from general knowledge.",
                    ]
                )
            else:
                strategies.append("Keep user-facing responses grounded in retrieved data before adding explanation.")
            reason_parts.append("web task quality signals suggest the response policy can be tightened")

        confidence = max(0.55, min(0.9, 1.0 - failure_rate / 2.0))
        return {
            "engine": engine,
            "task_kind": task_kind,
            "target": normalized_target or None,
            "strategy": self._dedupe(strategies),
            "confidence": confidence,
            "reason": "; ".join(reason_parts),
        }

    def _should_generate(self, performance: dict[str, Any]) -> bool:
        sample_size = int(performance.get("sample_size", 0))
        avg_score = float(performance.get("avg_score", 0.0))
        failure_rate = float(performance.get("failure_rate", 0.0))
        return sample_size >= 1 and (avg_score < 0.82 or failure_rate >= 0.3)

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered
