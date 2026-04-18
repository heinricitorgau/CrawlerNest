from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MemoryType = Literal["user_preference", "entity_knowledge", "interaction_pattern"]


@dataclass(slots=True)
class MemoryEntry:
    id: str
    type: MemoryType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    decay_score: float = 0.0


@dataclass(slots=True)
class RetrievedMemoryEntry:
    id: str
    type: MemoryType
    content: str
    confidence: float
    importance: float
    decay_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievedMemory:
    entries: list[RetrievedMemoryEntry] = field(default_factory=list)
    used: bool = False
