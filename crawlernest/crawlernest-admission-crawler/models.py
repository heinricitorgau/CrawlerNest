"""Admission crawler data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from observability import ExtractionSummary


@dataclass(slots=True)
class AdmissionRecord:
    university_name: str
    source_url: str
    degree_level: str
    requirements: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    # Observability fields — populated by build_admission_record() when crawl_status is known.
    crawl_status: str = "success"   # CrawlStatus literal
    extraction_summary: "ExtractionSummary | None" = None
