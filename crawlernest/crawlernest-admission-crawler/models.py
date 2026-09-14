"""Admission crawler data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from observability import ExtractionSummary

#: Where a record's page content came from. The same three values as FETCH_MODES
#: in crawlernest_admission_crawler/models.py and ck_admission_record_fetch in the
#: warehouse schema; this package cannot import either, so they are repeated.
FETCH_LIVE = "live"
FETCH_SNAPSHOT = "snapshot"
FETCH_UNKNOWN = "unknown"


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
    #: When the page content was read off the network, in UTC. Set only for a
    #: live fetch that returned a body. A snapshot read leaves it None: the file
    #: was captured at some earlier time nobody recorded, and the moment it was
    #: opened is not that time.
    fetched_at: datetime | None = None
    #: live, snapshot, or unknown when no content was read at all.
    fetch_mode: str = FETCH_UNKNOWN
