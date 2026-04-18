from __future__ import annotations

from collections import defaultdict

from crawlernest.agent.memory_long_term.memory_types import MemoryEntry


class MemoryIndex:
    def __init__(self) -> None:
        self._by_user: dict[str, set[str]] = defaultdict(set)
        self._by_entity: dict[str, set[str]] = defaultdict(set)
        self._by_type: dict[str, set[str]] = defaultdict(set)

    def rebuild(self, entries: list[MemoryEntry]) -> None:
        self._by_user.clear()
        self._by_entity.clear()
        self._by_type.clear()
        for entry in entries:
            self.add(entry)

    def add(self, entry: MemoryEntry) -> None:
        user_id = str(entry.metadata.get("user_id") or "").strip()
        if user_id:
            self._by_user[user_id].add(entry.id)
        for entity in entry.metadata.get("entities", []) or []:
            entity_key = str(entity).strip().lower()
            if entity_key:
                self._by_entity[entity_key].add(entry.id)
        self._by_type[str(entry.type)].add(entry.id)

    def lookup(
        self,
        *,
        user_id: str | None = None,
        entities: list[str] | None = None,
        types: list[str] | None = None,
    ) -> set[str]:
        candidate_sets: list[set[str]] = []
        if user_id:
            candidate_sets.append(set(self._by_user.get(user_id, set())))
        if entities:
            entity_hits: set[str] = set()
            for entity in entities:
                entity_hits |= self._by_entity.get(str(entity).strip().lower(), set())
            if entity_hits:
                candidate_sets.append(entity_hits)
        if types:
            type_hits: set[str] = set()
            for memory_type in types:
                type_hits |= self._by_type.get(str(memory_type), set())
            if type_hits:
                candidate_sets.append(type_hits)

        if not candidate_sets:
            return set()

        result = set(candidate_sets[0])
        for candidate_set in candidate_sets[1:]:
            result &= candidate_set
        return result
