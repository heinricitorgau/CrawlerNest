from __future__ import annotations

import re

from crawlernest.agent.memory_long_term.memory_store import LongTermMemoryStore
from crawlernest.agent.memory_long_term.memory_types import RetrievedMemory, RetrievedMemoryEntry
from crawlernest.agent.web_agent.memory.memory_policy import _extract_entity_tokens

_PREFERENCE_RE = re.compile(r"\b(recommend|推薦|recommendation|ielts|toefl|risk|country|uk|英國|united kingdom)\b", re.IGNORECASE)


class LongTermMemoryRetriever:
    def __init__(self, store: LongTermMemoryStore | None = None) -> None:
        self._store = store or LongTermMemoryStore()

    def retrieve(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        current_input: str,
        task_kind: str,
        resolved_reference: dict | None = None,
    ) -> RetrievedMemory:
        identity = user_id or session_id
        if not identity:
            return RetrievedMemory(entries=[], used=False)

        entities = self._extract_entities(current_input, resolved_reference)
        memory_types = self._candidate_types(task_kind=task_kind, current_input=current_input)
        entries = self._store.query(user_id=identity, entities=entities, types=memory_types, limit=8)

        retrieved: list[RetrievedMemoryEntry] = []
        for entry in entries:
            confidence = self._score_entry(
                entry=entry,
                task_kind=task_kind,
                current_input=current_input,
                entities=entities,
            )
            if confidence < 0.35 or entry.decay_score > 0.85:
                continue
            retrieved.append(
                RetrievedMemoryEntry(
                    id=entry.id,
                    type=entry.type,
                    content=entry.content,
                    confidence=confidence,
                    importance=entry.importance,
                    decay_score=entry.decay_score,
                    metadata=entry.metadata,
                )
            )

        retrieved.sort(key=lambda item: item.confidence, reverse=True)
        return RetrievedMemory(entries=retrieved[:5], used=bool(retrieved))

    def _extract_entities(self, current_input: str, resolved_reference: dict | None) -> list[str]:
        entities = [token for token in _extract_entity_tokens(current_input) if str(token).strip()]
        if isinstance(resolved_reference, dict):
            for entity in resolved_reference.get("resolved_entities", []) or []:
                if str(entity).strip() and str(entity).lower() not in {value.lower() for value in entities}:
                    entities.append(str(entity))
        return entities

    def _candidate_types(self, *, task_kind: str, current_input: str) -> list[str]:
        if task_kind == "recommendation" or _PREFERENCE_RE.search(current_input):
            return ["user_preference", "interaction_pattern"]
        if task_kind in {"ranking_explain", "university_lookup", "data_query"}:
            return ["interaction_pattern", "entity_knowledge", "user_preference"]
        return ["interaction_pattern"]

    def _score_entry(
        self,
        *,
        entry,
        task_kind: str,
        current_input: str,
        entities: list[str],
    ) -> float:
        content_lower = entry.content.lower()
        entity_match = any(entity.lower() in content_lower for entity in entities)
        task_pref = task_kind == "recommendation" and entry.type == "user_preference"
        keyword_match = any(token in content_lower for token in current_input.lower().split())

        base = 0.25
        if entity_match:
            base += 0.4
        if task_pref:
            base += 0.25
        elif keyword_match:
            base += 0.15
        confidence = base * (0.6 + 0.4 * entry.importance) * (1.0 - 0.7 * entry.decay_score)
        return max(0.0, min(1.0, confidence))
