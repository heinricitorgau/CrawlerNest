from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class PatchStore:
    def __init__(self, *, path: str | None = None) -> None:
        self._path = Path(
            path
            or os.environ.get("CRAWLERNEST_PATCH_STORE_PATH")
            or "/tmp/crawlernest_patch_store.json"
        )
        self._lock = threading.Lock()
        self._entries: list[dict[str, Any]] = []
        self._load()

    def append(
        self,
        *,
        task: str,
        patch_candidate: dict[str, Any],
        patch_validation: dict[str, Any],
        patch_execution: dict[str, Any],
    ) -> dict[str, Any]:
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "task": task,
            "patch_candidate": patch_candidate,
            "patch_validation": patch_validation,
            "patch_execution": patch_execution,
            "status": "approved"
            if patch_execution.get("improvement")
            else ("discarded" if patch_validation.get("valid") else "rejected"),
        }
        with self._lock:
            self._entries.append(entry)
            self._persist()
        return dict(entry)

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
        self._path.write_text(
            json.dumps({"entries": self._entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
