from __future__ import annotations

from typing import Optional


def build_filter_summary(filter_reasons: list[str]) -> str:
    if not filter_reasons:
        return "Passed eligibility because no blocking filters applied."
    return "Passed eligibility because " + "; ".join(filter_reasons) + "."


def build_v3_explanation(
    *,
    category_reason: str,
    category: str,
    effective_rank: Optional[int],
    target_rank: Optional[int],
    ielts_margin: Optional[float],
    confidence_label: Optional[str],
    country_preference: Optional[str],
    country_policy: str,
    candidate_country: Optional[str],
    country_match_score: Optional[float],
    risk_profile: str,
    risk_adjustment: float,
) -> str:
    summary_parts: list[str] = [category_reason]
    fit_bits: list[str] = []
    if effective_rank is not None and target_rank is not None:
        fit_bits.append(f"rank #{effective_rank} is being judged against your target #{target_rank}")
    if ielts_margin is not None:
        if ielts_margin >= 0:
            fit_bits.append(f"IELTS clears the requirement by {ielts_margin:.2f}")
        else:
            fit_bits.append(f"IELTS is short by {abs(ielts_margin):.2f}")
    if country_preference:
        if country_policy == "hard_filter":
            fit_bits.append(f"country is filtered to {country_preference}")
        elif candidate_country and candidate_country.strip().lower() == country_preference.strip().lower():
            fit_bits.append(f"country matches {country_preference}")
        else:
            fit_bits.append(f"country mismatch is tolerated as a soft preference")
    if confidence_label:
        fit_bits.append(f"confidence is {confidence_label}")
    if fit_bits:
        summary_parts.append("Recommended because " + ", ".join(fit_bits) + ".")

    if abs(risk_adjustment) >= 1.0:
        direction = "boosted" if risk_adjustment > 0 else "reduced"
        summary_parts.append(
            f"The {risk_profile} profile {direction} this {category} option."
        )

    return " ".join(summary_parts)


def build_no_results_reason(candidate_count: int, target_rank: Optional[int]) -> str:
    if candidate_count == 0:
        return "No candidates were available from the recommendation view."
    if target_rank is not None:
        return f"No universities produced a valid decision result for target rank {target_rank}."
    return "No universities produced a valid decision result."
