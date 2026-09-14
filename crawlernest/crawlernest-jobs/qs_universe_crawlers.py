from __future__ import annotations

import asyncio
import datetime as _dt
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config import Config
from crawler import UniversityCrawler
from models import University

from qs_universe_registry import QSUniverseSpec
from ranking_edition import (
    VerifiedEdition,
    assert_crawled_edition,
    qs_fetch_for,
    resolve_qs_edition,
)


def _persist_resolution_cache(config: Config) -> None:
    cache_path = str(getattr(config, "resolution_cache_path", "") or "").strip()
    ranking_id = str(getattr(config, "ranking_id", "") or "").strip()
    if not cache_path or not ranking_id:
        return
    # Only an id actually read off this universe's ranking page earns a cache
    # entry. fetcher._ensure_ranking_id already writes one on page resolution;
    # this second writer used to persist whatever config.ranking_id happened to
    # hold, including a hardcoded default, and the next run then trusted it as
    # "resolved" and skipped page resolution entirely. That is how one wrong id
    # became permanent.
    # An id proven against the edition page (ranking_edition) qualifies too, and
    # overwrites whatever an earlier unversioned-page resolution left under this
    # year's key.
    source = str(getattr(config, "_ranking_id_source", "") or "").strip()
    if source not in ("page_resolution", "edition_page"):
        return
    universe_type = str(getattr(config, "universe_type", "") or "").strip().lower()
    universe_key = str(getattr(config, "universe_key", "") or "").strip().lower()
    ranking_year = str(getattr(config, "ranking_year", "") or "").strip()
    if not universe_type or not universe_key or not ranking_year:
        return

    key = f"QS|{ranking_year}|{universe_type}|{universe_key}"
    cache_file = Path(cache_path)
    payload: dict[str, Any] = {"entries": {}}
    if cache_file.exists():
        try:
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {"entries": {}}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        entries = {}
        payload["entries"] = entries
    entries[key] = {
        "source": "QS",
        "ranking_year": getattr(config, "ranking_year", None),
        "universe_type": universe_type,
        "universe_key": universe_key,
        "ranking_page_url": getattr(config, "ranking_page_url", None),
        "ranking_id": ranking_id,
        "ranking_id_candidates": [ranking_id],
        "subregion_id": str(getattr(config, "_subregion_id", "") or "").strip(),
        "resolved_ranking_page_url": str(
            getattr(config, "_resolved_ranking_page_url", "") or getattr(config, "ranking_page_url", "") or ""
        ),
        "api_url": str(getattr(config, "api_url", "") or "").strip(),
        "resolved_at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class BaseQSUniverseCrawler:
    def __init__(
        self,
        spec: QSUniverseSpec,
        *,
        limit: int,
        ranking_year: int,
        use_async: bool,
        workers: int,
        request_delay: float,
        local_parse_workers: int,
    ):
        self.spec = spec
        self.limit = max(1, int(limit))
        self.ranking_year = int(ranking_year)
        self.use_async = bool(use_async)
        self.workers = max(1, int(workers))
        self.request_delay = max(0.0, float(request_delay))
        self.local_parse_workers = max(1, int(local_parse_workers))

    def build_config(self) -> Config:
        effective_request_delay = self.request_delay
        if self.spec.universe_type == "region" and self.spec.universe_key == "europe":
            effective_request_delay = max(effective_request_delay, 12.0)
        # No fallback id. A universe without a pinned ranking_id must resolve one
        # from its own ranking page. This used to default to "3990755", which
        # silently gave eleven of thirteen universes the same id -- and that id
        # still answers 200 with WORLD ranking rows, so asia/europe/africa runs
        # would have ingested world data under their own labels without a single
        # error. An empty id fails loudly instead.
        preferred_ranking_id = str(self.spec.ranking_id or "").strip()
        return Config(
            ranking_id=preferred_ranking_id,
            ranking_page_url=self.spec.ranking_page_url,
            region_name=self.spec.region_name,
            universe_type=self.spec.universe_type,
            universe_key=self.spec.universe_key,
            ranking_scope=getattr(self.spec, "ranking_scope", "regional_ranking"),
            progress_label=f"{self.spec.universe_type}/{self.spec.universe_key}",
            ranking_year=self.ranking_year,
            ranking_limit=self.limit,
            use_async=self.use_async,
            show_progress=True,
            output_format="console",
            max_concurrent_requests=self.workers,
            request_delay=effective_request_delay,
            local_parse_workers=self.local_parse_workers,
            fetch_details=self.spec.fetch_details,
            resolution_cache_path=str(
                Path(__file__).resolve().parents[1] / "crawlernest-kb" / "qs_universe_resolution_cache.json"
            ),
        )

    def resolve_edition(self, config: Config) -> VerifiedEdition:
        """Prove which table is this universe's ``ranking_year`` edition before fetching it.

        Raises EditionMismatchError when the source cannot show it -- including a
        universe whose page names no year, and a pinned id that is not the id the
        edition page declares. ``edition_fetch`` is overridable for tests.
        """
        fetch = getattr(self, "edition_fetch", None) or qs_fetch_for(config)
        return resolve_qs_edition(
            self.spec.ranking_page_url,
            self.ranking_year,
            fetch,
            pinned_ranking_id=str(self.spec.ranking_id or "").strip(),
        )

    def crawl(self, existing_universities: list[University] | None = None) -> tuple[list[University], dict[str, Any]]:
        config = self.build_config()
        edition = self.resolve_edition(config)
        # Fetch with the edition's id from the edition's page, so the endpoint
        # warm-up and any re-resolution see the same edition, not the latest one.
        config.ranking_page_url = edition.page_url
        setattr(config, "_edition_ranking_id", edition.ranking_id)
        setattr(config, "_stable_ranking_id", edition.ranking_id)
        existing_universities = list(existing_universities or [])
        if existing_universities:
            config._resume_paths = [str(uni.path).strip() for uni in existing_universities if str(uni.path or "").strip()]
            config._resume_node_keys = [
                f"path:{str(uni.path).strip()}" if str(uni.path or "").strip()
                else f"rank-name:{str(uni.rank or '').strip()}|{str(uni.name or '').strip().lower()}"
                for uni in existing_universities
            ]
        crawler = UniversityCrawler(config)
        if existing_universities:
            crawler.universities = existing_universities.copy()
        universities = asyncio.run(crawler.crawl_async()) if self.use_async else crawler.crawl()
        self.interrupted = getattr(crawler, "interrupted", False)
        if universities:
            assert_crawled_edition(edition, str(getattr(config, "ranking_id", "") or ""))
            _persist_resolution_cache(config)
        crawl_meta = {
            "detail_fallback_triggered": bool(getattr(config, "_detail_fallback_triggered", False)),
            "detail_deferred_paths": list(getattr(config, "_detail_deferred_paths", []) or []),
            "detail_forbidden_count": int(getattr(config, "_detail_forbidden_count", 0) or 0),
            "failure_classification": str(getattr(config, "_last_failure_classification", "") or ""),
            "failure_message": str(getattr(config, "_last_failure_message", "") or ""),
            # Which kind of refusal, and the edge headers that prove it. Without
            # these two, "upstream_blocked" cannot tell Cloudflare apart from the
            # QS origin, and the fix for one is not the fix for the other.
            "block_reason": str(getattr(config, "_last_block_reason", "") or ""),
            "block_evidence": dict(getattr(config, "_last_block_evidence", {}) or {}),
            # Which HTTP stack produced this run. A snapshot-backed run and a
            # blocked live run look alike in the other fields; this says whether
            # the request even had a chance of getting through.
            "http_backend": str(getattr(config, "_http_backend", "") or ""),
            "http_impersonate": str(getattr(config, "_http_impersonate", "") or ""),
            # world_slice rows carry world ranks; regional_ranking rows carry
            # that region's own 1..N. Consumers cannot tell them apart from the
            # rows alone, so the run has to say which it produced.
            "ranking_scope": str(getattr(config, "ranking_scope", "") or ""),
            "ranking_id_source": str(getattr(config, "_ranking_id_source", "") or ""),
            "used_resolution_cache": bool(getattr(config, "_used_resolution_cache", False)),
            "resolved_ranking_id": str(getattr(config, "ranking_id", "") or ""),
            "ranking_id_candidates": list(getattr(config, "_ranking_id_candidates", []) or []),
            "resolved_ranking_page_url": str(getattr(config, "_resolved_ranking_page_url", "") or ""),
            "page_resolution_skipped": bool(getattr(config, "_page_resolution_skipped", False)),
            "page_resolution_attempted": bool(getattr(config, "_page_resolution_attempted", False)),
            "subregion_id": str(getattr(config, "_subregion_id", "") or ""),
            "resolution_cache_path": str(getattr(config, "resolution_cache_path", "") or ""),
            "universe": asdict(self.spec),
            # What makes this run's rows replayable under ranking_year: the
            # edition page and id it was proven against. Snapshots without it are
            # refused by the fallback and by reingest_qs_universes.
            "edition": edition.as_meta(),
        }
        return universities, crawl_meta


class QSGlobalCrawler(BaseQSUniverseCrawler):
    pass


class QSRegionCrawler(BaseQSUniverseCrawler):
    pass


class QSSubjectCrawler(BaseQSUniverseCrawler):
    pass


class QSSpecialCrawler(BaseQSUniverseCrawler):
    pass


def save_universe_snapshot(path: Path, universities: list[University], spec: QSUniverseSpec, ranking_year: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for uni in universities:
        rows.append(
            {
                "university_name": uni.name,
                "country": uni.country,
                "rank": uni.rank,
                "score": (uni.table_metrics or {}).get("Overall Score"),
                "source": "QS",
                "universe_type": spec.universe_type,
                "universe_key": spec.universe_key,
                "year": ranking_year,
                "detail_url": uni.qs_profile_path or uni.path or None,
                "table_metrics": dict(uni.table_metrics or {}),
            }
        )
    path.write_text(__import__("json").dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
