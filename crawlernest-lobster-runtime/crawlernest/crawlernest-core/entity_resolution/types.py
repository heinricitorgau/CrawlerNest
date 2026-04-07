from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class EntityRecord:
    source_name: str
    source_entity_id: str
    university_name: str
    country_hint: Optional[str] = None
    language_code: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalProfile:
    canonical_university_id: int
    display_name: str
    country_hint: Optional[str] = None
    aliases: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolutionResult:
    source_name: str
    source_entity_id: str
    canonical_university_id: Optional[int]
    matched_alias: Optional[str]
    confidence_score: float
    matching_method: str  # exact / normalized / fuzzy / embedding / unresolved
    candidate_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
