from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GenerationDecisionSignals:
    has_retrieval: bool
    retrieval_confidence: float
    has_memory: bool
    ambiguity_level: str
    query_type: str


@dataclass(slots=True)
class GenerationDecision:
    mode: str
    reason: str
    signals: GenerationDecisionSignals
    minimal_context: bool = False
    debug: dict[str, object] = field(default_factory=dict)
