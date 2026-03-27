from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config import Config
from crawler import UniversityCrawler
from models import University

from qs_universe_registry import QSUniverseSpec


def _persist_resolution_cache(config: Config) -> None:
    cache_path = str(getattr(config, "resolution_cache_path", "") or "").strip()
    ranking_id = str(getattr(config, "ranking_id", "") or "").strip()
    if not cache_path or not ranking_id:
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
        "resolved_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
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
        return Config(
            ranking_id=self.spec.ranking_id or "3990755",
            ranking_page_url=self.spec.ranking_page_url,
            region_name=self.spec.region_name,
            universe_type=self.spec.universe_type,
            universe_key=self.spec.universe_key,
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

    def crawl(self) -> tuple[list[University], dict[str, Any]]:
        config = self.build_config()
        crawler = UniversityCrawler(config)
        universities = asyncio.run(crawler.crawl_async()) if self.use_async else crawler.crawl()
        self.interrupted = getattr(crawler, "interrupted", False)
        if universities:
            _persist_resolution_cache(config)
        crawl_meta = {
            "detail_fallback_triggered": bool(getattr(config, "_detail_fallback_triggered", False)),
            "detail_deferred_paths": list(getattr(config, "_detail_deferred_paths", []) or []),
            "detail_forbidden_count": int(getattr(config, "_detail_forbidden_count", 0) or 0),
            "failure_classification": str(getattr(config, "_last_failure_classification", "") or ""),
            "failure_message": str(getattr(config, "_last_failure_message", "") or ""),
            "used_resolution_cache": bool(getattr(config, "_used_resolution_cache", False)),
            "resolved_ranking_id": str(getattr(config, "ranking_id", "") or ""),
            "ranking_id_candidates": list(getattr(config, "_ranking_id_candidates", []) or []),
            "resolved_ranking_page_url": str(getattr(config, "_resolved_ranking_page_url", "") or ""),
            "subregion_id": str(getattr(config, "_subregion_id", "") or ""),
            "resolution_cache_path": str(getattr(config, "resolution_cache_path", "") or ""),
            "universe": asdict(self.spec),
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
