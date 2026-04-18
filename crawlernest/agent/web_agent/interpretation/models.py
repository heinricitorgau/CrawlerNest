from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ResolvedReference:
    detected: bool
    input_type: str
    resolved_entities: list[str] = field(default_factory=list)
    confidence: str = "low"
    reason: str = ""


@dataclass(slots=True)
class RewriteResult:
    original_input: str
    rewritten_query: str | None
    rewrite_applied: bool
    rewrite_reason: str
