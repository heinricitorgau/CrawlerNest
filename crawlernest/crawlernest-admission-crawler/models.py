"""Admission crawler data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AdmissionRecord:
    university_name: str
    source_url: str
    degree_level: str
    requirements: dict[str, str] = field(default_factory=dict)
    notes: str = ""
