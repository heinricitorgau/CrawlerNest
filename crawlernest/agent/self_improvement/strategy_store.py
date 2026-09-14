from __future__ import annotations

import json
import threading
import time
import uuid
import hashlib
from typing import Any

from crawlernest.agent.persistence.factory import json_store_path
from crawlernest.agent.persistence.json_files import write_json_atomically


def normalize_target(target: str | None) -> str | None:
    return target.strip().lower() if isinstance(target, str) and target.strip() else None


def apply_strategy_update(
    entry: dict[str, Any],
    *,
    strategy: list[str],
    confidence: float,
    reason: str,
    source: str,
    rollout_percent: int,
    status: str,
) -> dict[str, Any]:
    """The fields an upsert overwrites. Shared with the PostgreSQL store."""
    entry["updated_at"] = time.time()
    entry["strategy"] = [str(item) for item in strategy if str(item).strip()]
    entry["confidence"] = max(0.0, min(1.0, float(confidence)))
    entry["reason"] = reason
    entry["source"] = source
    entry["rollout_percent"] = max(0, min(100, int(rollout_percent)))
    entry["status"] = status
    entry["success_count"] = int(entry.get("success_count", 0))
    entry["failure_count"] = int(entry.get("failure_count", 0))
    return entry


def select_strategies(
    items: list[dict[str, Any]],
    *,
    engine: str,
    task_kind: str,
    target: str | None,
    min_confidence: float,
    limit: int,
    strategy_type: str | None,
    require_active: bool,
) -> list[dict[str, Any]]:
    """StrategyStore.query's filter and order. Shared with the PostgreSQL store."""
    normalized_target = normalize_target(target)
    matches: list[dict[str, Any]] = []
    for entry in items:
        if entry.get("engine") != engine or entry.get("task_kind") != task_kind:
            continue
        if strategy_type and entry.get("strategy_type", "behavior") != strategy_type:
            continue
        if require_active and entry.get("status", "active") != "active":
            continue
        confidence = float(entry.get("confidence", 0.0))
        if confidence < min_confidence:
            continue
        entry_target = entry.get("target")
        if normalized_target and entry_target not in {None, normalized_target}:
            continue
        matches.append(dict(entry))
    matches.sort(
        key=lambda entry: (
            float(entry.get("confidence", 0.0)),
            float(entry.get("updated_at", 0.0)),
        ),
        reverse=True,
    )
    return matches[:limit]


def rollout_allows(*, entry: dict[str, Any], request_signature: str) -> bool:
    rollout_percent = int(entry.get("rollout_percent", 100))
    if rollout_percent >= 100:
        return True
    if rollout_percent <= 0:
        return False
    bucket = int(
        hashlib.sha1(
            f"{entry.get('id', '')}:{request_signature}".encode("utf-8")
        ).hexdigest()[:8],
        16,
    ) % 100
    return bucket < rollout_percent


class StrategyStore:
    def __init__(self, *, path: str | None = None) -> None:
        self._path = json_store_path(path, "CRAWLERNEST_STRATEGY_STORE_PATH", "strategies.json")
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._load()

    def upsert(
        self,
        *,
        engine: str,
        task_kind: str,
        strategy: list[str],
        confidence: float,
        reason: str,
        target: str | None = None,
        strategy_type: str = "behavior",
        source: str = "experience_analysis",
        rollout_percent: int = 100,
        status: str = "active",
    ) -> dict[str, Any]:
        normalized_target = normalize_target(target)
        with self._lock:
            existing = next(
                (
                    entry
                    for entry in self._entries
                    if entry.get("engine") == engine
                    and entry.get("task_kind") == task_kind
                    and entry.get("target") == normalized_target
                    and entry.get("strategy_type", "behavior") == strategy_type
                ),
                None,
            )
            if existing is None:
                previous = self._latest_version_locked(
                    engine=engine,
                    task_kind=task_kind,
                    target=normalized_target,
                    strategy_type=strategy_type,
                )
                existing = {
                    "id": str(uuid.uuid4()),
                    "created_at": time.time(),
                    "engine": engine,
                    "task_kind": task_kind,
                    "target": normalized_target,
                    "strategy_type": strategy_type,
                    "version": f"v{(int(previous.get('version', 'v0')[1:]) + 1) if previous else 1}",
                    "previous": previous.get("id") if previous else None,
                }
                self._entries.append(existing)
            apply_strategy_update(
                existing,
                strategy=strategy,
                confidence=confidence,
                reason=reason,
                source=source,
                rollout_percent=rollout_percent,
                status=status,
            )
            self._persist()
            return dict(existing)

    def query(
        self,
        *,
        engine: str,
        task_kind: str,
        target: str | None = None,
        min_confidence: float = 0.55,
        limit: int = 3,
        strategy_type: str | None = None,
        require_active: bool = True,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._entries)
        return select_strategies(
            items,
            engine=engine,
            task_kind=task_kind,
            target=target,
            min_confidence=min_confidence,
            limit=limit,
            strategy_type=strategy_type,
            require_active=require_active,
        )

    def record_outcome(
        self,
        *,
        strategy_id: str,
        success: bool,
    ) -> dict[str, Any] | None:
        with self._lock:
            entry = next((item for item in self._entries if item.get("id") == strategy_id), None)
            if entry is None:
                return None
            counter_key = "success_count" if success else "failure_count"
            entry[counter_key] = int(entry.get(counter_key, 0)) + 1
            self._persist()
            return dict(entry)

    def rollback(
        self,
        *,
        strategy_id: str,
        reason: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            entry = next((item for item in self._entries if item.get("id") == strategy_id), None)
            if entry is None:
                return None
            entry["status"] = "rolled_back"
            entry["rollback_reason"] = reason
            entry["updated_at"] = time.time()
            self._persist()
            return dict(entry)

    def rollout_allows(
        self,
        *,
        entry: dict[str, Any],
        request_signature: str,
    ) -> bool:
        return rollout_allows(entry=entry, request_signature=request_signature)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        if isinstance(entries, list):
            self._entries = [dict(item) for item in entries if isinstance(item, dict)]

    def _persist(self) -> None:
        write_json_atomically(self._path, {"entries": self._entries})

    def _latest_version_locked(
        self,
        *,
        engine: str,
        task_kind: str,
        target: str | None,
        strategy_type: str,
    ) -> dict[str, Any] | None:
        matches = [
            entry
            for entry in self._entries
            if entry.get("engine") == engine
            and entry.get("task_kind") == task_kind
            and entry.get("target") == target
            and entry.get("strategy_type", "behavior") == strategy_type
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: float(item.get("updated_at", item.get("created_at", 0.0))), reverse=True)
        return matches[0]
