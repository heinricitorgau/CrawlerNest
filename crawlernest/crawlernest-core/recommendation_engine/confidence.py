from __future__ import annotations

from dataclasses import dataclass

from .config import RecommendationConfig


@dataclass(frozen=True)
class ConfidenceAssessment:
    score: float
    label: str
    reason: str


def build_confidence_assessment(
    *,
    completeness_score: float,
    source_count: int,
    source_spread_ratio: float | None,
    missing_ielts_for_query: bool,
    config: RecommendationConfig,
) -> ConfidenceAssessment:
    if source_count <= 0:
        agreement = 45.0
        agreement_reason = "no ranking source agreement is available"
    elif source_count == 1:
        agreement = 68.0
        agreement_reason = "only one ranking source is available"
    else:
        spread_ratio = max(0.0, min(1.0, float(source_spread_ratio or 0.0)))
        missing_sources = max(0, 3 - source_count)
        agreement = max(45.0, 100.0 - (spread_ratio * 100.0) - (config.missing_source_penalty * missing_sources))
        agreement_reason = f"{source_count} ranking sources are available with spread ratio {spread_ratio:.2f}"

    confidence = (
        (config.completeness_confidence_weight * completeness_score)
        + (config.source_agreement_weight * agreement)
    )
    if missing_ielts_for_query:
        confidence -= 8.0

    confidence = round(max(0.0, min(100.0, confidence)), 4)
    if confidence >= 80:
        label = "high"
    elif confidence >= 60:
        label = "medium"
    else:
        label = "low"

    reason = (
        f"Confidence is {label} because completeness is {completeness_score:.2f}/100 and "
        f"{agreement_reason}."
    )
    if missing_ielts_for_query:
        reason += " IELTS evidence is incomplete for this query."
    return ConfidenceAssessment(score=confidence, label=label, reason=reason)
