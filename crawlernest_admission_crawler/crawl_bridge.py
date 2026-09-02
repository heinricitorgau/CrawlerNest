"""The missing link between the admission crawler and the admission pipeline.

Two packages have carried the word "admission" for months without touching:

* ``crawlernest/crawlernest-admission-crawler`` fetches pages and extracts
  IELTS, TOEFL, Duolingo, GPA, deadline and degree level.
* ``crawlernest_admission_crawler`` (this package) validates, stages, resolves
  and lands admission rows.

Nothing joined them. ``run_admission_crawl.py`` wrote only a ``CrawlReport`` --
crawl_status, is_usable, which fields were missing -- and dropped
``record.requirements`` on the floor, so not one extracted number ever reached
a database. The pipeline's only input was a single hardcoded MIT record.

This module converts the crawler's ``AdmissionRecord`` into the pipeline's, so
the existing staging, validation, resolution and landing path can run on real
data. It adds no extraction logic of its own: everything it reports was
already being computed and thrown away.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from crawlernest_admission_crawler.models import AdmissionRecord

_CRAWLER_DIR = (
    Path(__file__).resolve().parent.parent
    / "crawlernest"
    / "crawlernest-admission-crawler"
)

#: The crawler package imports its own modules by flat name (``from models
#: import ...``) and the repository root also has a models.py, so its
#: directories go in front. Same ordering run_admission_crawl.py uses.
_CRAWLER_PATHS = (
    _CRAWLER_DIR.parent / "crawlernest-core",
    _CRAWLER_DIR.parent / "crawlernest-crawler-core",
    _CRAWLER_DIR / "site_profiles",
    _CRAWLER_DIR / "extractors",
    _CRAWLER_DIR / "crawlers",
    _CRAWLER_DIR,
)

#: Keys as UniversityAdmissionCrawler._display_field_name writes them.
FIELD_IELTS = "IELTS"
FIELD_TOEFL = "TOEFL"
FIELD_DUOLINGO = "Duolingo"
FIELD_GPA = "GPA"
FIELD_DEADLINE = "deadline"


@dataclass(slots=True)
class CrawlBridgeSummary:
    universities_attempted: int
    urls_attempted: int
    usable_record_count: int
    skipped_record_count: int
    #: crawl_status -> count, for everything that did not become a row.
    skipped_by_status: dict[str, int]


@dataclass(frozen=True)
class _UrlWork:
    """One candidate URL plus the profile it came from.

    Results come back positionally, so the profile has to travel with the URL --
    reading it from a loop variable would attribute records to whichever
    university happened to be last.
    """

    profile: Any
    url: str


#: Flat module names the crawler package defines that something else already
#: on sys.path also defines. Only ``models`` collides today
#: (crawlernest-core/models.py), and run_pipeline imports that one during its
#: own bootstrap -- so by the time this module runs, ``models`` is already in
#: sys.modules pointing at the wrong file and the crawler's
#: ``from models import AdmissionRecord`` fails.
_FLAT_NAME_COLLISIONS = ("models",)


def _ensure_crawler_importable() -> None:
    for path in _CRAWLER_PATHS:
        entry = str(path)
        if not path.is_dir():
            continue
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)


@contextmanager
def _crawler_imports():
    """Let the crawler's flat module names win, then put the others back.

    Fixing this properly means giving the crawler package real relative
    imports, which would break ``run_admission_crawl.py`` and every
    ``sys.path``-juggling script that already drives it. Until that happens,
    the collision is shadowed for the duration of the import only: the crawler
    modules bind their references at import time, so restoring afterwards
    leaves both packages working.
    """
    saved = {name: sys.modules[name] for name in _FLAT_NAME_COLLISIONS if name in sys.modules}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in _FLAT_NAME_COLLISIONS:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def crawl_admission_records(
    *,
    snapshot_dir: Path | None = None,
    only: Iterable[str] | None = None,
    rate_limit_seconds: float = 1.0,
    max_workers: int = 0,
    serial: bool = False,
) -> tuple[list[AdmissionRecord], CrawlBridgeSummary]:
    """Crawl the configured universities and return pipeline-shaped records.

    ``snapshot_dir`` reads the checked-in HTML instead of going out to the
    network, which is what CI and any offline run should use.

    Only usable records become rows. A blocked or empty page yields an
    AdmissionRecord with no requirements, and staging one would assert that a
    university publishes no entry requirements at all -- which is a different
    claim from "we could not read the page". The counts come back in the
    summary instead.
    """
    _ensure_crawler_importable()

    with _crawler_imports():
        from crawlers.university_site import (  # noqa: E402
            UniversityAdmissionCrawler,
            _url_to_slug,
        )
        from site_profiles.universities import UNIVERSITY_PROFILES  # noqa: E402

    # crawlernest-crawler-core only joins sys.path in _ensure_crawler_importable
    # above, so this cannot be a module-level import.
    from host_scheduler import DEFAULT_MAX_WORKERS, run_grouped_by_host  # noqa: E402

    keys = list(UNIVERSITY_PROFILES) if only is None else [k for k in UNIVERSITY_PROFILES if k in set(only)]
    crawler = UniversityAdmissionCrawler(
        snapshot_dir=snapshot_dir,
        rate_limit_seconds=rate_limit_seconds,
    )

    records: list[AdmissionRecord] = []
    skipped = 0
    skipped_by_status: dict[str, int] = {}
    extracted_at = datetime.now(timezone.utc)

    # Build every unit of work first, then schedule it. Crawling used to be two
    # nested loops -- universities, then their URLs -- which put all 23 requests
    # on one thread in one line, so the wall clock was the sum of 23 round trips
    # plus 23 courtesy delays. The work actually spans 11 independent hosts with
    # at most 3 URLs each, so the floor is one host's chain, not the whole list.
    work: list[_UrlWork] = []
    for key in keys:
        profile = UNIVERSITY_PROFILES[key]
        candidate_urls = profile.candidate_urls
        if snapshot_dir is not None:
            # The crawler falls back to live HTTP for any URL it has no
            # snapshot for, so passing a snapshot directory would still put
            # requests on the wire -- against real university sites, from CI.
            # Only the URLs actually on disk are offered.
            offline = [
                url
                for url in candidate_urls
                if (snapshot_dir / f"{_url_to_slug(url)}.html").is_file()
                or (snapshot_dir / f"{_url_to_slug(url)}.htm").is_file()
            ]
            missing = len(candidate_urls) - len(offline)
            if missing:
                skipped += missing
                skipped_by_status["no_snapshot"] = (
                    skipped_by_status.get("no_snapshot", 0) + missing
                )
            candidate_urls = offline
        for url in candidate_urls:
            work.append(_UrlWork(profile=profile, url=url))

    crawled_records = run_grouped_by_host(
        work,
        lambda item: crawler.crawl_one(
            university_name=item.profile.name,
            base_url=item.profile.base_url,
            url=item.url,
        ),
        url_of=lambda item: item.url,
        max_workers=max_workers or DEFAULT_MAX_WORKERS,
        # Snapshot runs touch no network, so threads buy nothing and only make
        # log interleaving nondeterministic in CI.
        serial=serial or snapshot_dir is not None,
    )

    urls_attempted = len(crawled_records)
    for item, crawled in zip(work, crawled_records):
        summary = crawled.extraction_summary
        if summary is None or not summary.is_usable:
            skipped += 1
            status = crawled.crawl_status or "unknown"
            skipped_by_status[status] = skipped_by_status.get(status, 0) + 1
            continue
        records.append(
            to_pipeline_record(
                crawled,
                country=item.profile.country or None,
                extracted_at=extracted_at,
            )
        )

    return records, CrawlBridgeSummary(
        universities_attempted=len(keys),
        urls_attempted=urls_attempted,
        usable_record_count=len(records),
        skipped_record_count=skipped,
        skipped_by_status=skipped_by_status,
    )


def to_pipeline_record(crawled: Any, *, country: str | None, extracted_at: datetime) -> AdmissionRecord:
    """Convert one crawler AdmissionRecord into the pipeline's.

    The crawler reports requirements as a display-keyed dict of strings; the
    pipeline wants typed fields. Values are passed through as-is rather than
    re-validated: the crawler already applied the same bounds in
    ``_validate_extracted_fields``, and validator.py checks them again at the
    staging gate, so a third opinion here could only disagree with both.
    """
    requirements: dict[str, str] = dict(getattr(crawled, "requirements", {}) or {})
    return AdmissionRecord(
        university_name=str(crawled.university_name),
        source_url=str(crawled.source_url),
        country=country,
        ielts_requirement=_as_float(requirements.get(FIELD_IELTS)),
        toefl_requirement=_as_int(requirements.get(FIELD_TOEFL)),
        extracted_at=extracted_at,
        duolingo_requirement=_as_int(requirements.get(FIELD_DUOLINGO)),
        gpa_requirement=_as_float(requirements.get(FIELD_GPA)),
        application_deadline=requirements.get(FIELD_DEADLINE) or None,
        degree_level=str(getattr(crawled, "degree_level", "") or "") or None,
        raw_payload=_raw_payload(crawled, requirements),
    )


def _raw_payload(crawled: Any, requirements: dict[str, str]) -> dict[str, Any]:
    """What is worth keeping that has no column of its own.

    The crawl status and the flagged fields travel with the row so a reviewer
    looking at an odd value can see the extraction was flagged, rather than
    having to go back to crawl_outputs and match it up by URL.
    """
    summary = getattr(crawled, "extraction_summary", None)
    payload: dict[str, Any] = {
        "crawl_status": getattr(crawled, "crawl_status", None),
        "extracted_fields": sorted(requirements),
    }
    if summary is not None:
        flagged = list(getattr(summary, "flagged_fields", []) or [])
        if flagged:
            payload["flagged_fields"] = flagged
        if getattr(summary, "input_truncated", False):
            payload["input_truncated"] = True
    notes = getattr(crawled, "notes", "")
    if notes:
        payload["notes"] = notes
    return payload


def bridge_summary_to_dict(summary: CrawlBridgeSummary) -> dict[str, Any]:
    return {
        "universities_attempted": summary.universities_attempted,
        "urls_attempted": summary.urls_attempted,
        "usable_record_count": summary.usable_record_count,
        "skipped_record_count": summary.skipped_record_count,
        "skipped_by_status": dict(sorted(summary.skipped_by_status.items())),
    }


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)
