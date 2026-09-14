from __future__ import annotations

import re

from crawlernest.agent.memory_long_term.memory_store import LongTermMemoryStore
from crawlernest.agent.persistence.factory import long_term_memory_store

_IELTS_RE = re.compile(r"(?:ielts|雅思)\s*[:=]?\s*([0-9](?:\.[0-9])?)", re.IGNORECASE)
_TOEFL_RE = re.compile(r"(?:toefl)\s*[:=]?\s*([0-9]{2,3})", re.IGNORECASE)
_COUNTRY_PATTERNS = {
    "United Kingdom": [r"\buk\b", r"united kingdom", r"英國"],
    "Singapore": [r"singapore", r"新加坡"],
    "United States": [r"\bus\b", r"united states", r"美國"],
    "Canada": [r"canada", r"加拿大"],
}


class LongTermMemoryWriter:
    def __init__(self, store: LongTermMemoryStore | None = None) -> None:
        self._store = store or long_term_memory_store()

    def write_from_interaction(
        self,
        *,
        user_id: str | None,
        session_id: str | None,
        task_kind: str,
        user_input: str,
        response_data: dict | None = None,
        resolved_reference: dict | None = None,
    ) -> None:
        identity = user_id or session_id
        if not identity:
            return

        for memory in self._extract_preferences(
            user_id=identity,
            session_id=session_id,
            user_input=user_input,
        ):
            self._store.insert(**memory)

        for memory in self._extract_interaction_patterns(
            user_id=identity,
            session_id=session_id,
            task_kind=task_kind,
            response_data=response_data or {},
            resolved_reference=resolved_reference or {},
        ):
            self._store.insert(**memory)

    def _extract_preferences(self, *, user_id: str, session_id: str | None, user_input: str) -> list[dict]:
        entries: list[dict] = []
        lowered = user_input.lower()

        ielts_match = _IELTS_RE.search(user_input)
        if ielts_match:
            score = ielts_match.group(1)
            entries.append(
                {
                    "memory_type": "user_preference",
                    "content": f"User prefers options compatible with IELTS {score}",
                    "metadata": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "entities": ["IELTS", score],
                    },
                    "importance": 0.85,
                }
            )

        toefl_match = _TOEFL_RE.search(user_input)
        if toefl_match:
            score = toefl_match.group(1)
            entries.append(
                {
                    "memory_type": "user_preference",
                    "content": f"User prefers options compatible with TOEFL {score}",
                    "metadata": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "entities": ["TOEFL", score],
                    },
                    "importance": 0.82,
                }
            )

        for country, patterns in _COUNTRY_PATTERNS.items():
            if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
                entries.append(
                    {
                        "memory_type": "user_preference",
                        "content": f"User prefers {country} universities",
                        "metadata": {
                            "user_id": user_id,
                            "session_id": session_id,
                            "entities": [country],
                        },
                        "importance": 0.8,
                    }
                )
                break

        if "conservative" in lowered or "保守" in user_input:
            entries.append(
                {
                    "memory_type": "user_preference",
                    "content": "User prefers a conservative recommendation profile",
                    "metadata": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "entities": ["conservative"],
                    },
                    "importance": 0.72,
                }
            )
        return entries

    def _extract_interaction_patterns(
        self,
        *,
        user_id: str,
        session_id: str | None,
        task_kind: str,
        response_data: dict,
        resolved_reference: dict,
    ) -> list[dict]:
        entries: list[dict] = []
        entities = resolved_reference.get("resolved_entities", []) if isinstance(resolved_reference, dict) else []
        display_name = response_data.get("universityDisplayName") or response_data.get("focusEntity")
        if display_name or entities:
            primary = str(display_name or entities[0])
            entries.append(
                {
                    "memory_type": "interaction_pattern",
                    "content": f"User has previously looked at {primary}",
                    "metadata": {
                        "user_id": user_id,
                        "session_id": session_id,
                        "entities": [primary],
                        "task_kind": task_kind,
                    },
                    "importance": 0.45,
                }
            )

        if task_kind == "university_lookup":
            country_signal = None
            admission_summary = response_data.get("admissionSummary")
            if isinstance(admission_summary, dict):
                countries = admission_summary.get("countries")
                if isinstance(countries, list) and countries:
                    country_signal = str(countries[0])
            if display_name and country_signal:
                entries.append(
                    {
                        "memory_type": "entity_knowledge",
                        "content": f"{display_name} is associated with {country_signal} in current preview data",
                        "metadata": {
                            "user_id": user_id,
                            "session_id": session_id,
                            "entities": [str(display_name), country_signal],
                        },
                        "importance": 0.55,
                    }
                )
        return entries
