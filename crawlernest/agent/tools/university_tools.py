from __future__ import annotations

import re
from typing import Any

from crawlernest.core.services.university_service import UniversityService


class UniversityTools:
    def __init__(self, service: UniversityService | None = None) -> None:
        self._service = service or UniversityService()

    def _extract_university_name(self, user_input: str) -> str:
        text = user_input.strip()
        if not text:
            return ""

        patterns = [
            r"show\s+the\s+(.+?)\s+university preview",
            r"show\s+(.+?)\s+university preview",
            r"lookup\s+(.+)",
            r"find\s+(.+)",
            r"tell me about\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip(" .?!")
                if candidate:
                    return candidate

        return ""

    def get_detail_preview(self, context: dict[str, Any], user_input: str = "") -> dict[str, Any]:
        canonical_id = context.get("canonical_university_id")
        university_name = context.get("university_name")
        if canonical_id is None and not university_name:
            extracted_name = self._extract_university_name(user_input)
            if extracted_name:
                university_name = extracted_name
        return self._service.get_detail_preview(
            canonical_university_id=int(canonical_id) if canonical_id is not None else None,
            university_name=None if university_name is None else str(university_name),
        )
