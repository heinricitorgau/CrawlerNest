"""University admission crawler stub."""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = CURRENT_DIR.parent
CORE_DIR = ENGINE_DIR.parent / "crawlernest-crawler-core"
for path in (ENGINE_DIR, CORE_DIR):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

from base import BaseCrawler
from extractors.admission_requirements import build_admission_record
from models import AdmissionRecord
from site_profiles.default import DEFAULT_ADMISSION_KEYWORDS


class UniversityAdmissionCrawler(BaseCrawler):
    """Minimal stub for crawling admission pages from a university website."""

    def __init__(self) -> None:
        super().__init__(name="crawlernest.admission.university_site")

    def crawl(self, *, university_name: str, base_url: str) -> list[AdmissionRecord]:
        self.logger.info("Running admission crawl stub for %s", university_name)
        notes = (
            "Stub crawl only. Future implementation should add page discovery, "
            "HTML parsing, extractor scoring, and site-specific profiles."
        )
        return [
            build_admission_record(
                university_name=university_name,
                source_url=f"{base_url.rstrip('/')}/admissions",
                degree_level="postgraduate",
                requirements={
                    "IELTS": "6.5 overall",
                    "TOEFL": "90 iBT",
                    "keywords_seeded": ", ".join(DEFAULT_ADMISSION_KEYWORDS[:3]),
                },
                notes=notes,
            )
        ]
