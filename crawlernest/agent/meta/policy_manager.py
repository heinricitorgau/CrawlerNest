from __future__ import annotations

from typing import Any

from crawlernest.agent.self_improvement.strategy_store import StrategyStore


class PolicyManager:
    def __init__(self, *, apply_threshold: float = 0.7, rollback_threshold: float = 0.45) -> None:
        self._apply_threshold = apply_threshold
        self._rollback_threshold = rollback_threshold

    def should_apply(
        self,
        *,
        strategy_entry: dict[str, Any],
        request_signature: str,
        strategy_store: StrategyStore,
    ) -> tuple[bool, str]:
        confidence = float(strategy_entry.get("confidence", 0.0))
        if confidence < self._apply_threshold:
            return False, "confidence below apply threshold"
        if strategy_entry.get("status", "active") != "active":
            return False, "strategy is not active"
        if not strategy_store.rollout_allows(entry=strategy_entry, request_signature=request_signature):
            return False, "canary rollout bucket not selected"
        return True, "strategy approved by policy manager"

    def should_store(self, *, strategy: dict[str, Any]) -> tuple[bool, str]:
        confidence = float(strategy.get("confidence", 0.0))
        if confidence < 0.65:
            return False, "strategy confidence too low to store"
        if not isinstance(strategy.get("strategy"), list) or not strategy.get("strategy"):
            return False, "strategy payload is empty"
        return True, "strategy is safe to store"

    def maybe_rollback(
        self,
        *,
        strategy_entry: dict[str, Any],
        final_score: float,
        strategy_store: StrategyStore,
    ) -> tuple[bool, str]:
        if final_score >= self._rollback_threshold:
            strategy_store.record_outcome(strategy_id=strategy_entry["id"], success=True)
            return False, "strategy outcome remains acceptable"
        strategy_store.record_outcome(strategy_id=strategy_entry["id"], success=False)
        strategy_store.rollback(
            strategy_id=strategy_entry["id"],
            reason="performance dropped below rollback threshold",
        )
        return True, "strategy rolled back after low-score outcome"
