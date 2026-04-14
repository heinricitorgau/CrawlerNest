from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AdmissionRecord:
    university_name: str
    source_url: str
    country: str | None
    ielts_requirement: float | None
    toefl_requirement: int | None
    extracted_at: datetime
    raw_payload: dict[str, Any] | None = None


@dataclass(slots=True)
class NormalizedAdmissionRow:
    university_name: str
    normalized_university_name: str
    source_url: str
    country: str | None
    ielts_requirement: float | None
    toefl_requirement: int | None
    extracted_at: datetime
    raw_payload: dict[str, Any] | None = None


@dataclass(slots=True)
class WarehouseReadyAdmissionRow:
    university_name: str
    normalized_university_name: str
    source_url: str
    country: str | None
    ielts_requirement: float | None
    toefl_requirement: int | None
    extracted_at: datetime
    canonical_university_id: int | None = None
    entity_resolution_status: str = "unresolved"
    raw_payload: dict[str, Any] | None = None
