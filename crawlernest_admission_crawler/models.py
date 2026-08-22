from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

#: The only degree levels admission_text_extractor._DEGREE_MAP can produce,
#: plus the placeholder for "the page did not say". Mirrored by
#: ck_admission_record_degree_level in crawlernest-schema/admission_postgresql.sql
#: and by _VALID_DEGREE_LEVELS in the crawler.
DEGREE_LEVELS = ("undergraduate", "postgraduate", "doctoral")
UNKNOWN_DEGREE_LEVEL = "unknown"


@dataclass(slots=True)
class AdmissionRecord:
    university_name: str
    source_url: str
    country: str | None
    ielts_requirement: float | None
    toefl_requirement: int | None
    extracted_at: datetime
    duolingo_requirement: int | None = None
    gpa_requirement: float | None = None
    application_deadline: date | None = None
    degree_level: str | None = None
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
    duolingo_requirement: int | None = None
    gpa_requirement: float | None = None
    application_deadline: date | None = None
    degree_level: str = UNKNOWN_DEGREE_LEVEL
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
    #: Half of the natural key, alongside source_code and degree_level, and the
    #: identity a warehouse.mapping_review decision hangs on. Derived from the
    #: URL by source_identity.admission_source_entity_id.
    source_entity_id: str = ""
    duolingo_requirement: int | None = None
    gpa_requirement: float | None = None
    application_deadline: date | None = None
    degree_level: str = UNKNOWN_DEGREE_LEVEL
    canonical_university_id: int | None = None
    entity_resolution_status: str = "unresolved"
    raw_payload: dict[str, Any] | None = None
