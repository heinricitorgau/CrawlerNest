"""Admission crawler engine entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
CORE_DIR = CURRENT_DIR.parent / "crawlernest-crawler-core"
for path in (CURRENT_DIR, CORE_DIR, CURRENT_DIR / "crawlers", CURRENT_DIR / "extractors", CURRENT_DIR / "site_profiles"):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

from crawlers.university_site import UniversityAdmissionCrawler
from logger import get_logger
from models import AdmissionRecord


class AdmissionCrawlerEngine:
    """Coordinates admission crawlers for university websites."""

    def __init__(self) -> None:
        self.logger = get_logger("crawlernest.admission.engine")
        self.crawlers = {
            "default_university_site": UniversityAdmissionCrawler(),
        }

    def crawl_university(self, *, university_name: str, base_url: str) -> list[AdmissionRecord]:
        crawler = self.crawlers["default_university_site"]
        self.logger.info("Starting admission crawl for %s", university_name)
        records = crawler.crawl(university_name=university_name, base_url=base_url)
        self.logger.info("Produced %s admission records", len(records))
        return records


def main() -> None:
    engine = AdmissionCrawlerEngine()
    records = engine.crawl_university(
        university_name="University of Melbourne",
        base_url="https://study.unimelb.edu.au",
    )
    for record in records:
        print(record)


if __name__ == "__main__":
    main()
