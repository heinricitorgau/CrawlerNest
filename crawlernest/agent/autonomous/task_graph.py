from __future__ import annotations

import re


class TaskGraphBuilder:
    def build(self, *, goal: str, context: dict | None = None) -> list[dict[str, object]]:
        normalized = goal.strip()
        lowered = normalized.lower()
        context = context or {}
        strategy_hints = [
            str(item).strip()
            for item in context.get("strategy_hints", [])
            if isinstance(item, str) and str(item).strip()
        ]

        steps: list[dict[str, object]] = [
            {
                "step": "analyze",
                "description": "Analyze the current target and identify the most likely failure surface.",
                "strategy_hints": strategy_hints[:2],
            }
        ]

        if any("validate" in hint.lower() for hint in strategy_hints):
            steps.append(
                {
                    "step": "strategy_review",
                    "description": "Review previously successful strategy hints before proposing changes.",
                    "strategy_hints": strategy_hints[:4],
                }
            )

        if "extractor" in lowered or "抽取器" in normalized:
            steps.append(
                {
                    "step": "identify_weaknesses",
                    "description": "Identify extractor robustness gaps and failure patterns.",
                    "strategy_hints": strategy_hints[:3],
                }
            )
        elif "parser" in lowered or "解析器" in normalized:
            steps.append(
                {
                    "step": "identify_weaknesses",
                    "description": "Identify parser edge cases and brittle handling.",
                    "strategy_hints": strategy_hints[:3],
                }
            )

        if re.search(r"\b(fix|bug|error|failure)\b", lowered) or any(
            token in normalized for token in ("修", "錯", "壞")
        ):
            steps.append(
                {
                    "step": "propose_fix",
                    "description": "Propose a focused fix for the detected failure handling issue.",
                    "strategy_hints": strategy_hints[:4],
                }
            )
        else:
            steps.append(
                {
                    "step": "propose_improvement",
                    "description": "Propose a scoped improvement for the current implementation.",
                    "strategy_hints": strategy_hints[:4],
                }
            )

        steps.append(
            {
                "step": "apply_refinement",
                "description": "Turn the proposal into a concrete semantic patch plan.",
                "strategy_hints": strategy_hints[:4],
            }
        )
        steps.append(
            {
                "step": "validate",
                "description": "Validate file targeting, symbol targeting, and change consistency.",
                "strategy_hints": strategy_hints[:4],
            }
        )

        if context.get("autonomous_refine", True):
            steps.append(
                {
                    "step": "refine",
                    "description": "Refine the plan if validation score is still not strong enough.",
                    "strategy_hints": strategy_hints[:4],
                }
            )

        return steps
