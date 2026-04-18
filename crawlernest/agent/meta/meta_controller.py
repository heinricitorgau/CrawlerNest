from __future__ import annotations

from typing import Any

from crawlernest.agent.meta.policy_manager import PolicyManager
from crawlernest.agent.meta.prompt_optimizer import PromptOptimizer
from crawlernest.agent.meta.tool_strategy_optimizer import ToolStrategyOptimizer
from crawlernest.agent.self_improvement.strategy_store import StrategyStore


class MetaController:
    def __init__(
        self,
        *,
        strategy_store: StrategyStore | None = None,
        policy_manager: PolicyManager | None = None,
        prompt_optimizer: PromptOptimizer | None = None,
        tool_strategy_optimizer: ToolStrategyOptimizer | None = None,
    ) -> None:
        self._strategy_store = strategy_store or StrategyStore()
        self._policy_manager = policy_manager or PolicyManager()
        self._prompt_optimizer = prompt_optimizer or PromptOptimizer()
        self._tool_optimizer = tool_strategy_optimizer or ToolStrategyOptimizer()

    def resolve_for_request(
        self,
        *,
        engine: str,
        task_kind: str,
        request_signature: str,
        target: str | None = None,
    ) -> dict[str, Any]:
        applied: list[dict[str, Any]] = []
        for strategy_type in ("prompt_patch", "tool_strategy"):
            for entry in self._strategy_store.query(
                engine=engine,
                task_kind=task_kind,
                target=target,
                min_confidence=0.7,
                limit=2,
                strategy_type=strategy_type,
                require_active=True,
            ):
                allowed, reason = self._policy_manager.should_apply(
                    strategy_entry=entry,
                    request_signature=request_signature,
                    strategy_store=self._strategy_store,
                )
                if allowed:
                    applied.append({**entry, "policy_reason": reason})
        prompt_patches = [
            item
            for entry in applied
            if entry.get("strategy_type") == "prompt_patch"
            for item in entry.get("strategy", [])
            if isinstance(item, str) and item.strip()
        ]
        tool_strategies = [
            item
            for entry in applied
            if entry.get("strategy_type") == "tool_strategy"
            for item in entry.get("strategy", [])
            if isinstance(item, str) and item.strip()
        ]
        primary = applied[0] if applied else None
        return {
            "prompt_patches": prompt_patches,
            "tool_strategies": tool_strategies,
            "applied_entries": applied,
            "debug": {
                "strategy_applied": bool(applied),
                "strategy_type": primary.get("strategy_type") if primary else None,
                "confidence": float(primary.get("confidence")) if primary else None,
                "source": primary.get("source") if primary else None,
                "applied": [
                    {
                        "id": entry.get("id"),
                        "strategy_type": entry.get("strategy_type"),
                        "confidence": entry.get("confidence"),
                        "source": entry.get("source"),
                        "version": entry.get("version"),
                        "target": entry.get("target"),
                    }
                    for entry in applied
                ],
            },
        }

    def update_from_performance(
        self,
        *,
        engine: str,
        task_kind: str,
        performance: dict[str, Any],
        experiences: list[dict[str, Any]],
        target: str | None = None,
    ) -> dict[str, Any]:
        generated_entries: list[dict[str, Any]] = []
        for candidate in (
            self._prompt_optimizer.generate(
                task_kind=task_kind,
                performance=performance,
                experiences=experiences,
            ) if engine == "web" else None,
            self._tool_optimizer.generate(
                engine=engine,
                task_kind=task_kind,
                performance=performance,
                experiences=experiences,
                target=target,
            ),
        ):
            if candidate is None:
                continue
            allowed, reason = self._policy_manager.should_store(strategy=candidate)
            if not allowed:
                continue
            stored = self._strategy_store.upsert(
                engine=engine,
                task_kind=task_kind,
                strategy=list(candidate.get("strategy", [])),
                confidence=float(candidate.get("confidence", 0.7)),
                reason=str(candidate.get("reason", reason)),
                target=target,
                strategy_type=str(candidate.get("strategy_type", "behavior")),
                source=str(candidate.get("reason", "experience_analysis")),
                rollout_percent=int(candidate.get("rollout_percent", 30)),
                status="active",
            )
            generated_entries.append(stored)
        return {
            "generated_entries": generated_entries,
        }

    def record_outcome(
        self,
        *,
        applied_entries: list[dict[str, Any]],
        final_score: float,
    ) -> dict[str, Any]:
        rolled_back: list[dict[str, Any]] = []
        for entry in applied_entries:
            did_rollback, reason = self._policy_manager.maybe_rollback(
                strategy_entry=entry,
                final_score=final_score,
                strategy_store=self._strategy_store,
            )
            if did_rollback:
                rolled_back.append(
                    {
                        "id": entry.get("id"),
                        "strategy_type": entry.get("strategy_type"),
                        "reason": reason,
                    }
                )
        return {"rolled_back": rolled_back}
