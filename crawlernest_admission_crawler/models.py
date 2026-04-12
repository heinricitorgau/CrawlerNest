from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(slots=True)
class AdmissionRecord:
    university_name: str
    ielts_requirement: Optional[float]
    toefl_requirement: Optional[int]
    source_url: str
    extracted_at: datetime
    confidence: Optional[float]
    raw_payload: Optional[dict[str, Any]] = None
