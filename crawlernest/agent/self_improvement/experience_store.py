from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class ExperienceStore:
    def __init__(
        self,
        *,
        path: str | None = None,
        max_entries: int = 2000,
    ) -> None:
        self._path = Path(
            path
            or os.environ.get("CRAWLERNEST_EXPERIENCE_STORE_PATH")
            or "/tmp/crawlernest_agent_experiences.json"
        )
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._load()

    def append(
        self,
        *,
        engine: str,
        task_kind: str,
        task: str,
        status: str,
        final_score: float,
        tools_used: list[str],
        steps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "engine": engine,
            "task_kind": task_kind,
            "task": task,
            "status": status,
            "final_score": max(0.0, min(1.0, float(final_score))),
            "tools_used": [str(tool) for tool in tools_used if str(tool).strip()],
            "steps": list(steps or []),
            "metadata": dict(metadata or {}),
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries :]
            self._persist()
        return dict(entry)

    def recent(
        self,
        *,
        engine: str | None = None,
        task_kind: str | None = None,
        target: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._entries)
        filtered: list[dict[str, Any]] = []
        for entry in reversed(items):
            if engine and entry.get("engine") != engine:
                continue
            if task_kind and entry.get("task_kind") != task_kind:
                continue
            if target:
                metadata = entry.get("metadata", {})
                if not isinstance(metadata, dict):
                    continue
                entry_target = metadata.get("target")
                if not isinstance(entry_target, str) or entry_target.lower() != target.lower():
                    continue
            filtered.append(dict(entry))
            if len(filtered) >= limit:
                break
        return filtered

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
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": self._entries}
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
