from __future__ import annotations

import json
import threading
import time
import uuid

from crawlernest.agent.memory_long_term.memory_index import MemoryIndex
from crawlernest.agent.memory_long_term.memory_types import MemoryEntry
from crawlernest.agent.persistence.factory import json_store_path
from crawlernest.agent.persistence.json_files import write_json_atomically

#: A memory's decay_score reaches 1.0 -- no weight at all -- after this many days.
DECAY_HORIZON_DAYS = 90.0


def decay_score_for(timestamp: float, now: float) -> float:
    age_days = max(0.0, (now - timestamp) / 86400.0)
    return max(0.0, min(1.0, age_days / DECAY_HORIZON_DAYS))


def rank_memories(entries: list[MemoryEntry], limit: int) -> list[MemoryEntry]:
    """Most useful first: importance discounted by age, then recency."""
    ordered = sorted(
        entries,
        key=lambda entry: (
            entry.importance * (1.0 - entry.decay_score),
            float(entry.metadata.get("timestamp", 0.0)),
        ),
        reverse=True,
    )
    return ordered[:limit]


class LongTermMemoryStore:
    def __init__(
        self,
        *,
        path: str | None = None,
        max_entries_per_user: int = 200,
    ) -> None:
        self._path = json_store_path(path, "CRAWLERNEST_LONG_TERM_MEMORY_PATH", "long_term_memory.json")
        self._max_entries_per_user = max_entries_per_user
        self._lock = threading.Lock()
        self._entries: dict[str, MemoryEntry] = {}
        self._index = MemoryIndex()
        self._load()

    def insert(
        self,
        *,
        memory_type: str,
        content: str,
        metadata: dict,
        importance: float,
    ) -> MemoryEntry:
        user_id = str(metadata.get("user_id") or "").strip()
        with self._lock:
            existing = next(
                (
                    entry
                    for entry in self._entries.values()
                    if entry.type == memory_type
                    and entry.content == content
                    and str(entry.metadata.get("user_id") or "").strip() == user_id
                ),
                None,
            )
            if existing is not None:
                merged_metadata = {**existing.metadata, **metadata}
                merged_metadata["timestamp"] = time.time()
                existing.metadata = merged_metadata
                existing.importance = max(existing.importance, importance)
                existing.decay_score = 0.0
                self._persist()
                return existing

            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                type=memory_type,  # type: ignore[arg-type]
                content=content,
                metadata={**metadata, "timestamp": time.time()},
                importance=max(0.0, min(1.0, importance)),
                decay_score=0.0,
            )
            self._entries[entry.id] = entry
            self._trim_user_entries(user_id)
            self._rebuild_index()
            self._persist()
            return entry

    def query(
        self,
        *,
        user_id: str | None,
        entities: list[str] | None = None,
        types: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemoryEntry]:
        with self._lock:
            self._refresh_decay_locked()
            candidate_ids = self._index.lookup(user_id=user_id, entities=entities, types=types)
            if not candidate_ids and user_id:
                candidate_ids = self._index.lookup(user_id=user_id, types=types)
            candidates = [self._entries[entry_id] for entry_id in candidate_ids if entry_id in self._entries]
            return [self._clone_entry(entry) for entry in rank_memories(candidates, limit)]

    def decay(self) -> None:
        with self._lock:
            self._refresh_decay_locked()
            self._persist()

    def _trim_user_entries(self, user_id: str) -> None:
        if not user_id:
            return
        user_entries = [
            entry
            for entry in self._entries.values()
            if str(entry.metadata.get("user_id") or "").strip() == user_id
        ]
        if len(user_entries) <= self._max_entries_per_user:
            return
        user_entries.sort(key=lambda entry: float(entry.metadata.get("timestamp", 0.0)))
        for entry in user_entries[: len(user_entries) - self._max_entries_per_user]:
            self._entries.pop(entry.id, None)

    def _refresh_decay_locked(self) -> None:
        now = time.time()
        for entry in self._entries.values():
            entry.decay_score = decay_score_for(float(entry.metadata.get("timestamp", now)), now)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        entries = payload.get("entries", []) if isinstance(payload, dict) else []
        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                entry = MemoryEntry(
                    id=str(item.get("id")),
                    type=str(item.get("type")),  # type: ignore[arg-type]
                    content=str(item.get("content", "")),
                    metadata=dict(item.get("metadata", {}) or {}),
                    importance=float(item.get("importance", 0.5)),
                    decay_score=float(item.get("decay_score", 0.0)),
                )
            except Exception:
                continue
            self._entries[entry.id] = entry
        self._rebuild_index()

    def _persist(self) -> None:
        payload = {
            "entries": [
                {
                    "id": entry.id,
                    "type": entry.type,
                    "content": entry.content,
                    "metadata": entry.metadata,
                    "importance": entry.importance,
                    "decay_score": entry.decay_score,
                }
                for entry in self._entries.values()
            ]
        }
        write_json_atomically(self._path, payload)

    def _rebuild_index(self) -> None:
        self._index.rebuild(list(self._entries.values()))

    def _clone_entry(self, entry: MemoryEntry) -> MemoryEntry:
        return MemoryEntry(
            id=entry.id,
            type=entry.type,
            content=entry.content,
            metadata=dict(entry.metadata),
            importance=entry.importance,
            decay_score=entry.decay_score,
        )
