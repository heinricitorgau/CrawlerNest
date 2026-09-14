from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

from crawlernest.agent.persistence.factory import json_store_path
from crawlernest.agent.persistence.json_files import write_json_atomically


def build_patch_record(
    *,
    task: str,
    patch_candidate: dict[str, Any],
    patch_validation: dict[str, Any],
    patch_execution: dict[str, Any],
) -> dict[str, Any]:
    """One patch record. Shared with the PostgreSQL store."""
    return {
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


class PatchStore:
    def __init__(self, *, path: str | None = None) -> None:
        self._path = json_store_path(path, "CRAWLERNEST_PATCH_STORE_PATH", "patches.json")
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
        entry = build_patch_record(
            task=task,
            patch_candidate=patch_candidate,
            patch_validation=patch_validation,
            patch_execution=patch_execution,
        )
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
        write_json_atomically(self._path, {"entries": self._entries})
