"""Admission extraction helpers."""

from __future__ import annotations

from models import AdmissionRecord


def build_admission_record(
    *,
    university_name: str,
    source_url: str,
    degree_level: str,
    requirements: dict[str, str],
    notes: str = "",
) -> AdmissionRecord:
    return AdmissionRecord(
        university_name=university_name,
        source_url=source_url,
        degree_level=degree_level,
        requirements=requirements,
        notes=notes,
    )
