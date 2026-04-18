from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GroundingSourceDetail:
    used: bool
    matched_items: list[str] = field(default_factory=list)
    match_score: float = 0.0
    reason: str | None = None


@dataclass(slots=True)
class GroundingScore:
    overall: float
    breakdown: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class HallucinationRisk:
    level: str
    reason: str


@dataclass(slots=True)
class GroundingExplanation:
    summary: str
    detail: str


@dataclass(slots=True)
class GroundingReport:
    answer_preview: str
    grounding_sources: dict[str, object]
    grounding_score: GroundingScore
    hallucination_risk: HallucinationRisk
    explanation: GroundingExplanation
