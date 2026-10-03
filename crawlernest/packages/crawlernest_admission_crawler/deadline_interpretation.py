from __future__ import annotations

from typing import Any


_DEADLINE_PRIORITY = {
    "early": 0,
    "international": 1,
    "general": 2,
    "final": 3,
    "rolling": 4,
    "domestic": 5,
}

_DEADLINE_URGENCY = {
    "early": "high",
    "international": "high",
    "general": "medium",
    "final": "medium",
    "rolling": "low",
    "domestic": "low",
}


def _normalize_candidates(raw_candidates: Any) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    if not isinstance(raw_candidates, list):
        return candidates

    for item in raw_candidates:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        deadline_type, deadline_value = item
        if not isinstance(deadline_type, str) or not isinstance(deadline_value, str):
            continue
        candidates.append((deadline_type, deadline_value))
    return candidates


def interpret_deadline_decision(
    *,
    deadline: str | None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, str | None]:
    diagnostics = diagnostics or {}
    candidates = _normalize_candidates(diagnostics.get("deadline_candidates"))

    if candidates:
        ranked = sorted(
            enumerate(candidates),
            key=lambda item: (_DEADLINE_PRIORITY.get(item[1][0], 99), item[0]),
        )
        selected_type, selected_deadline = ranked[0][1]
        urgency = _DEADLINE_URGENCY.get(selected_type, "unknown")

        if len(candidates) > 1:
            other_types = [candidate_type for idx, (candidate_type, _) in enumerate(candidates) if idx != ranked[0][0]]
            if other_types:
                reason = (
                    f"{selected_type} deadline takes priority over "
                    + ", ".join(f"{candidate_type} deadline" for candidate_type in other_types)
                )
            else:
                reason = f"{selected_type} deadline selected from multiple candidates"
        else:
            reason = f"{selected_type} deadline is the only available candidate"

        return {
            "recommended_deadline": selected_deadline,
            "recommended_deadline_type": selected_type,
            "deadline_urgency": urgency,
            "deadline_reason": reason,
        }

    if deadline:
        return {
            "recommended_deadline": deadline,
            "recommended_deadline_type": "unknown",
            "deadline_urgency": "unknown",
            "deadline_reason": "deadline extracted without typed deadline candidates",
        }

    return {
        "recommended_deadline": None,
        "recommended_deadline_type": "unknown",
        "deadline_urgency": "unknown",
        "deadline_reason": "no deadline candidates available",
    }
