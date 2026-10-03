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

#: What a requirement applies to. Mirrored by ck_admission_record_requirement_scope
#: and ck_admission_record_scope_shape in crawlernest-schema/admission_postgresql.sql.
SCOPE_PROGRAMME = "programme"
SCOPE_FACULTY = "faculty"
SCOPE_INSTITUTION_MINIMUM = "institution_minimum"
SCOPE_UNSPECIFIED = "unspecified"
REQUIREMENT_SCOPES = (SCOPE_PROGRAMME, SCOPE_FACULTY, SCOPE_INSTITUTION_MINIMUM, SCOPE_UNSPECIFIED)

#: How intake_year was established. Mirrored by ck_admission_record_intake.
INTAKE_PAGE_STATED = "page_stated"
INTAKE_DEADLINE_INFERRED = "deadline_inferred"
INTAKE_UNKNOWN = "unknown"
INTAKE_YEAR_BASES = (INTAKE_PAGE_STATED, INTAKE_DEADLINE_INFERRED, INTAKE_UNKNOWN)

#: Where the page content came from. Mirrored by ck_admission_record_fetch.
FETCH_LIVE = "live"
FETCH_SNAPSHOT = "snapshot"
FETCH_UNKNOWN = "unknown"
FETCH_MODES = (FETCH_LIVE, FETCH_SNAPSHOT, FETCH_UNKNOWN)


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
    #: When the page was read off the network (timezone-aware), or None when
    #: nobody recorded it -- a snapshot, or a source that predates this field.
    fetched_at: datetime | None = None
    fetch_mode: str = FETCH_UNKNOWN


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
    fetched_at: datetime | None = None
    fetch_mode: str = FETCH_UNKNOWN


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
    #: Programme granularity. Both NULL with scope "unspecified" is what every
    #: current source produces: one number per page, scope not established.
    faculty: str | None = None
    programme_name: str | None = None
    requirement_scope: str = SCOPE_UNSPECIFIED
    intake_year: int | None = None
    intake_year_basis: str = INTAKE_UNKNOWN
    fetched_at: datetime | None = None
    fetch_mode: str = FETCH_UNKNOWN
