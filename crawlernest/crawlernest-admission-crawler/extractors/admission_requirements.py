"""Admission extraction helpers."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_CRAWLER_DIR = Path(__file__).resolve().parent.parent
if str(_CRAWLER_DIR) not in sys.path:
    sys.path.insert(0, str(_CRAWLER_DIR))

from models import FETCH_UNKNOWN, AdmissionRecord
from observability import compute_extraction_summary


def build_admission_record(
    *,
    university_name: str,
    source_url: str,
    degree_level: str,
    requirements: dict[str, str],
    notes: str = "",
    crawl_status: str = "success",
    flagged_fields: list[str] | None = None,
    input_truncated: bool = False,
    fetched_at: datetime | None = None,
    fetch_mode: str = FETCH_UNKNOWN,
) -> AdmissionRecord:
    """Create an :class:`AdmissionRecord` and attach an :class:`ExtractionSummary`.

    Args:
        university_name: Human-readable university name.
        source_url: The URL the data was extracted from.
        degree_level: Degree level string (e.g. ``"postgraduate"``).
        requirements: Free-form key→value map of extracted requirements.
        notes: Optional free-text notes from the crawler.
        crawl_status: The outcome of the HTTP fetch (default ``"success"``).
        fetched_at: When a live fetch read the page, in UTC.
        fetch_mode: ``live``, ``snapshot`` or ``unknown``.

    Returns:
        A fully populated :class:`AdmissionRecord` with an attached
        :class:`ExtractionSummary`.
    """
    summary = compute_extraction_summary(
        url=source_url,
        crawl_status=crawl_status,
        requirements=requirements,
        degree_level=degree_level,
        flagged_fields=flagged_fields or [],
        input_truncated=input_truncated,
    )
    return AdmissionRecord(
        university_name=university_name,
        source_url=source_url,
        degree_level=degree_level,
        requirements=requirements,
        notes=notes,
        crawl_status=crawl_status,
        extraction_summary=summary,
        fetched_at=fetched_at,
        fetch_mode=fetch_mode,
    )
