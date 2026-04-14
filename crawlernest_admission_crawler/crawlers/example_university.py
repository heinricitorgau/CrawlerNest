from __future__ import annotations

from datetime import datetime, timezone

from crawlernest_admission_crawler.models import AdmissionRecord


class ExampleUniversityCrawler:
    def crawl(self) -> list[AdmissionRecord]:
        extracted_at = datetime.now(timezone.utc)
        return [
            AdmissionRecord(
                university_name="MIT",
                source_url="https://example.edu/admissions",
                country="United States",
                ielts_requirement=7.0,
                toefl_requirement=100,
                extracted_at=extracted_at,
                raw_payload={
                    "university": "MIT",
                    "country": "United States",
                    "ielts_requirement": 7.0,
                    "toefl_requirement": 100,
                    "source_url": "https://example.edu/admissions",
                },
            )
        ]
