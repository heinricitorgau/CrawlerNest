
from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
import time
from typing import Any, Dict, List, Optional, Union, cast
from dataclasses import asdict

from config import Config
from extractor import DataExtractor
from fetcher import AsyncUniversityFetcher, UniversityFetcher
from models import University
from exporter import get_exporter
from db_writer import DBWriter
from utils import setup_logging
from constants.regions import (
    REGION_COUNTRIES,
    COUNTRY_NAME_ALIASES,
    COUNTRY_SLUG_ALIASES,
    UNIVERSITY_COUNTRY_HINTS,
)

logger = logging.getLogger("UniversityCrawler")


def _norm_text(v: str) -> str:
    return " ".join((v or "").strip().lower().split())


def _canon_country(v: str) -> str:
    s = _norm_text(v)
    s = COUNTRY_NAME_ALIASES.get(s, s)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"\([^)]*\)", " ", s)                                           
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = " ".join(s.split())
    s = COUNTRY_NAME_ALIASES.get(s, s)
    return s


def _collect_region_strings(obj: Any, out: List[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            if isinstance(v, str) and any(tok in key for tok in ("region", "subregion", "sub_region")):
                vv = _norm_text(v)
                if vv:
                    out.append(vv)
            _collect_region_strings(v, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect_region_strings(it, out)


def _collect_table_metric_pairs(obj: Any, out: Dict[str, str]) -> None:
    if isinstance(obj, dict):
        label_keys = ("label", "title", "name", "indicator", "metric", "indicator_name", "indicator_label")
        value_keys = ("score", "value", "display", "formatted", "result")

        label = None
        for k in label_keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                label = v.strip()
                break

        value = None
        for k in value_keys:
            v = obj.get(k)
            if isinstance(v, (str, int, float)) and str(v).strip():
                value = str(v).strip()
                break

        if label and value:
            out.setdefault(label, value)

        for v in obj.values():
            _collect_table_metric_pairs(v, out)
    elif isinstance(obj, list):
        for it in obj:
            _collect_table_metric_pairs(it, out)


def _find_first_scalar_for_keys(obj: Any, keys: set[str]) -> Optional[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kk = str(k).strip().lower()
            if kk in keys and isinstance(v, (str, int, float)) and str(v).strip():
                return str(v).strip()
            got = _find_first_scalar_for_keys(v, keys)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for it in obj:
            got = _find_first_scalar_for_keys(it, keys)
            if got is not None:
                return got
    return None


def _extract_table_metrics(node: Dict[str, Any]) -> Dict[str, str]:
    metrics: Dict[str, str] = {}
    if "overall_score" in node:
        val = node["overall_score"]
        if isinstance(val, (str, int, float)) and str(val).strip():
            metrics["Overall Score"] = str(val).strip()
            
    scores = node.get("scores")
    if isinstance(scores, dict):
        for _, indicators in scores.items():
            if not isinstance(indicators, list):
                continue
            for item in indicators:
                if not isinstance(item, dict):
                    continue
                name = (
                    item.get("indicator_name")
                    or item.get("indicator_label")
                    or item.get("title")
                    or item.get("label")
                    or item.get("name")
                )
                value = item.get("score") or item.get("value") or item.get("display")
                if isinstance(name, str) and name.strip():
                    label = name.strip()
                    metrics.setdefault(label, str(value).strip() if value is not None else "N/A")
    elif isinstance(scores, list):
        for item in scores:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("indicator_name")
                or item.get("indicator_label")
                or item.get("title")
                or item.get("label")
                or item.get("name")
            )
            value = item.get("score") or item.get("value") or item.get("display")
            if isinstance(name, str) and name.strip():
                label = name.strip()
                metrics.setdefault(label, str(value).strip() if value is not None else "N/A")

    if not metrics:
        _collect_table_metric_pairs(node, metrics)
    return metrics


def _is_forbidden_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "403" in msg or "forbidden" in msg


def _node_country_candidates(node: Dict[str, Any]) -> List[str]:
    vals: List[str] = []
    direct_keys = (
        "country",
        "country_name",
        "location",
        "institution_country",
        "institutionCountry",
        "countryCode",
        "country_code",
    )
    for k in direct_keys:
        v = node.get(k)
        if isinstance(v, str):
            vv = _norm_text(v)
            if vv:
                vals.append(vv)

    def _walk(o: Any) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                key = str(k).lower()
                if isinstance(v, str) and "country" in key:
                    vv = _norm_text(v)
                    if vv:
                        vals.append(vv)
                if isinstance(v, str) and "code" in key:
                    vv = _norm_text(v)
                    if vv:
                        vals.append(vv)
                _walk(v)
        elif isinstance(o, list):
            for it in o:
                _walk(it)
    _walk(node)
    pathish = ""
    for k in ("path", "url", "link"):
        v = node.get(k)
        if isinstance(v, str):
            pathish += " " + _norm_text(v.replace("-", " ").replace("/", " "))
    for slug, country in COUNTRY_SLUG_ALIASES.items():
        if slug in pathish:
            vals.append(country)
    name = _norm_text(str(node.get("title") or node.get("name") or node.get("institution") or ""))
    if name in UNIVERSITY_COUNTRY_HINTS:
        vals.append(UNIVERSITY_COUNTRY_HINTS[name])
    seen = set()
    out: List[str] = []
    for v in vals:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


class UniversityCrawler:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        if self.config.use_async and AsyncUniversityFetcher is not None:
            self.fetcher = AsyncUniversityFetcher(self.config)                            
        else:
            self.fetcher = UniversityFetcher(self.config)
        self.extractor = DataExtractor()
        self.universities: List[University] = []
        self.interrupted = False
        self.logger = logger
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        self.region_name = getattr(self.config, "region_name", None)
        self.is_region = bool(self.region_name is not None)
        self.is_sustainability = bool(getattr(self.config, "ranking_page_url", None) and not self.region_name)

    def _filter_nodes_for_region(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.is_region or not self.region_name:
            return nodes
        requested_page_url = str(getattr(self.config, "ranking_page_url", "") or "").lower()
        resolved_page_url = str(getattr(self.config, "_resolved_ranking_page_url", "") or "").lower()
        used_prefetched = bool(getattr(self.config, "_used_prefetched_payload", False))
        subregion_slug_hints = {
            "arab region": "arab-region-rankings",
            "central asia": "central-asia",
            "southern asia": "southern-asia",
            "eastern asia": "eastern-asia",
            "south-eastern asia": "south-eastern-asia",
            "western asia": "western-asia",
            "the caribbean": "the-caribbean",
            "central america": "central-america",
            "south america": "south-america",
            "northern europe": "northern-europe",
            "western europe": "western-europe",
            "eastern europe": "eastern-europe",
            "southern europe": "southern-europe",
            "oceania": "oceania-university-rankings",
            "africa": "africa-university-rankings",
            "north america": "north-america-university-rankings",
        }
        hint = subregion_slug_hints.get(self.region_name.lower())
        if hint and hint in resolved_page_url:
            return nodes
        if used_prefetched and hint and hint in requested_page_url:
            return nodes
        allowed = REGION_COUNTRIES.get(self.region_name)
        if not allowed:
            return nodes
        target = self.region_name.lower()
        allowed_norm = {_canon_country(c) for c in allowed}
        def get_country(n: Dict[str, Any]) -> str:
            c = n.get("country") or n.get("country_name") or n.get("location") or ""
            return str(c)
        def get_regionish_values(n: Dict[str, Any]) -> List[str]:
            vals: List[str] = []
            for k in ("region", "region_name", "subregion", "sub_region", "subregion_name", "sub_region_name"):
                v = n.get(k)
                if isinstance(v, str) and v.strip():
                    vals.append(_norm_text(v))
            _collect_region_strings(n, vals)
            seen = set()
            out: List[str] = []
            for v in vals:
                if v in seen:
                    continue
                seen.add(v)
                out.append(v)
            return out
        region_filtered = [n for n in nodes if target in get_regionish_values(n)]
        country_filtered = []
        for n in nodes:
            candidates = [c for c in _node_country_candidates(n)]
            direct = _norm_text(get_country(n))
            if direct:
                candidates = [direct] + candidates
            ok = False
            for c in candidates:
                cc = _canon_country(c)
                if cc in allowed_norm:
                    ok = True
                    break
                if any((cc and a and (cc in a or a in cc)) for a in allowed_norm):
                    ok = True
                    break
            if ok:
                country_filtered.append(n)
        if region_filtered or country_filtered:
            seen = set()
            merged: List[Dict[str, Any]] = []
            for n in region_filtered + country_filtered:
                key = (
                    str(n.get("rank") or n.get("rank_display") or ""),
                    str(n.get("title") or n.get("name") or n.get("institution") or ""),
                    str(get_country(n)),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(n)
            return merged
        if hint and hint in requested_page_url and hint in resolved_page_url:
            self.logger.warning("Sub-region local filter produced 0 rows for %s; using upstream nodes fallback.", self.region_name)
            return nodes
        if nodes:
            sample_countries = []
            for n in nodes[:15]:
                c = str(n.get("country") or n.get("country_name") or n.get("location") or "")
                if c:
                    sample_countries.append(c)
            self.logger.warning("Sub-region filter yielded 0 for region=%s; requested_url=%s; resolved_url= %s; sample_countries=%s", self.region_name, requested_page_url, resolved_page_url, sample_countries)
        return []

    def _collect_region_nodes_sync(self, fetcher: UniversityFetcher, first_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = self.config.ranking_limit if self.config.ranking_limit > 0 else 1000000
        max_pages = 40
        original_page = self.config.page
        page = original_page
        data: Optional[Dict[str, Any]] = first_data
        collected: List[Dict[str, Any]] = []
        seen = set()
        try:
            for _ in range(max_pages):
                if not isinstance(data, dict) or "score_nodes" not in data:
                    break
                raw_nodes: List[Dict[str, Any]] = data.get("score_nodes", [])
                if not raw_nodes:
                    break
                filtered = self._filter_nodes_for_region(raw_nodes)
                for node in filtered:
                    key = (
                        str(node.get("rank") or node.get("rank_display") or ""),
                        str(node.get("title") or node.get("name") or node.get("institution") or ""),
                        str(node.get("country") or node.get("country_name") or node.get("location") or ""),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(node)
                    if len(collected) >= target:
                        break
                if len(collected) >= target:
                    break
                if not raw_nodes:
                    break
                page += 1
                self.config.page = page
                try:
                    data = fetcher.fetch_rankings()
                except Exception as e:
                    msg = str(e)
                    if "status=404" in msg or "404" in msg:
                        break
                    self.logger.warning("Region pagination fetch failed at page=%s: %s", page, e)
                    break
        finally:
            self.config.page = original_page
        return collected

    def _collect_nodes_sync(self, fetcher: UniversityFetcher, first_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = self.config.ranking_limit if self.config.ranking_limit > 0 else 1000000
        max_pages = 40
        original_page = self.config.page
        page = original_page
        data: Optional[Dict[str, Any]] = first_data
        collected: List[Dict[str, Any]] = []
        seen = set()
        try:
            for _ in range(max_pages):
                if not isinstance(data, dict) or "score_nodes" not in data:
                    break
                raw_nodes: List[Dict[str, Any]] = data.get("score_nodes", [])
                if not raw_nodes:
                    break
                nodes = self._filter_nodes_for_region(raw_nodes)
                for node in nodes:
                    key = (
                        str(node.get("rank") or node.get("rank_display") or ""),
                        str(node.get("title") or node.get("name") or node.get("institution") or ""),
                        str(node.get("country") or node.get("country_name") or node.get("location") or ""),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(node)
                    if len(collected) >= target:
                        break
                if len(collected) >= target:
                    break
                if not raw_nodes:
                    break
                page += 1
                self.config.page = page
                try:
                    data = fetcher.fetch_rankings()
                except Exception as e:
                    msg = str(e)
                    if "status=404" in msg or "404" in msg:
                        break
                    self.logger.warning("Pagination fetch failed at page=%s: %s", page, e)
                    break
        finally:
            self.config.page = original_page
        return collected

    async def _collect_region_nodes_async(self, fetcher: AsyncUniversityFetcher, first_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = self.config.ranking_limit if self.config.ranking_limit > 0 else 1000000
        max_pages = 40
        original_page = self.config.page
        page = original_page
        data: Optional[Dict[str, Any]] = first_data
        collected: List[Dict[str, Any]] = []
        seen = set()
        try:
            for _ in range(max_pages):
                if not isinstance(data, dict) or "score_nodes" not in data:
                    break
                raw_nodes: List[Dict[str, Any]] = data.get("score_nodes", [])
                if not raw_nodes:
                    break
                filtered = self._filter_nodes_for_region(raw_nodes)
                for node in filtered:
                    key = (
                        str(node.get("rank") or node.get("rank_display") or ""),
                        str(node.get("title") or node.get("name") or node.get("institution") or ""),
                        str(node.get("country") or node.get("country_name") or node.get("location") or ""),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(node)
                    if len(collected) >= target:
                        break
                if len(collected) >= target:
                    break
                if not raw_nodes:
                    break
                page += 1
                self.config.page = page
                try:
                    data = await fetcher.fetch_rankings()
                except Exception as e:
                    msg = str(e)
                    if "status=404" in msg or "404" in msg:
                        break
                    self.logger.warning("Region pagination fetch failed at page=%s: %s", page, e)
                    break
        finally:
            self.config.page = original_page
        return collected

    async def _collect_nodes_async(self, fetcher: AsyncUniversityFetcher, first_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = self.config.ranking_limit if self.config.ranking_limit > 0 else 1000000
        max_pages = 40
        original_page = self.config.page
        page = original_page
        data: Optional[Dict[str, Any]] = first_data
        collected: List[Dict[str, Any]] = []
        seen = set()
        try:
            for _ in range(max_pages):
                if not isinstance(data, dict) or "score_nodes" not in data:
                    break
                raw_nodes: List[Dict[str, Any]] = data.get("score_nodes", [])
                if not raw_nodes:
                    break
                nodes = self._filter_nodes_for_region(raw_nodes)
                for node in nodes:
                    key = (
                        str(node.get("rank") or node.get("rank_display") or ""),
                        str(node.get("title") or node.get("name") or node.get("institution") or ""),
                        str(node.get("country") or node.get("country_name") or node.get("location") or ""),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(node)
                    if len(collected) >= target:
                        break
                if len(collected) >= target:
                    break
                if not raw_nodes:
                    break
                page += 1
                self.config.page = page
                try:
                    data = await fetcher.fetch_rankings()
                except Exception as e:
                    msg = str(e)
                    if "status=404" in msg or "404" in msg:
                        break
                    self.logger.warning("Pagination fetch failed at page=%s: %s", page, e)
                    break
        finally:
            self.config.page = original_page
        return collected

    def _process_university(self, node: Dict[str, Any]) -> Optional[University]:
        if not isinstance(node, dict):
            return None
        rank = (
            node.get("rank")
            or node.get("rank_display")
            or node.get("rank_text")
            or node.get("rank_sort")
            or node.get("rank_order")
            or "N/A"
        )
        name = node.get("title") or node.get("name") or node.get("institution") or "N/A"
        path = node.get("path") or node.get("url") or node.get("link") or ""
        country = node.get("country") or node.get("country_name") or node.get("location") or "N/A"
        table_metrics = _extract_table_metrics(node)
        for noisy in ("Rank", "University", "Country", "Location"):
            table_metrics.pop(noisy, None)
            table_metrics.pop(noisy.lower(), None)
        return University(
            rank=str(rank),
            name=str(name),
            path=str(path),
            country=str(country),
            table_metrics=table_metrics,
        )

    def crawl(self) -> List[University]:
        self.logger.info("Starting university crawl (sync)")
        try:
            fetcher = cast(UniversityFetcher, self.fetcher)
            detail_deferred_paths: List[str] = []
            detail_fallback_triggered = False
            detail_forbidden_streak = 0
            detail_forbidden_hits = 0
            detail_forbidden_threshold = max(1, int(getattr(self.config, "detail_forbidden_streak_threshold", 8) or 8))
            details_enabled = bool(getattr(self.config, "fetch_details", True))

            try:
                data = fetcher.fetch_rankings()
            except Exception as e:
                self.logger.error(f"Failed to fetch rankings: {e}")
                print("✗ Failed to fetch ranking data")
                return []

            if not isinstance(data, dict) or "score_nodes" not in data:
                self.logger.error("No ranking data found")
                print("✗ Failed to fetch ranking data")
                return []

            if self.is_region:
                nodes = self._collect_region_nodes_sync(fetcher, data)
            else:
                nodes = self._collect_nodes_sync(fetcher, data)

            if self.config.ranking_limit:
                nodes = nodes[: self.config.ranking_limit]
            if self.config.sort_ascending:
                nodes.reverse()

            if self.is_region and len(nodes) == 0:
                print(f"{self._progress_prefix()}Note: 0 rows after sub-region filtering. Check source route/nid mapping.")
            if self.is_region and self.config.ranking_limit and len(nodes) < self.config.ranking_limit:
                print(f"{self._progress_prefix()}Note: only {len(nodes)} rows matched sub-region filter (requested top {self.config.ranking_limit}).")

            self.stats["total"] = len(nodes)
            self.logger.info(f"Found {len(nodes)} universities to process")

            for i, node in enumerate(nodes, start=1):
                if self.config.show_progress:
                    pct = int(i / max(1, len(nodes)) * 100)
                    filled = pct // 5
                    bar = "█" * filled + "░" * (20 - filled)
                    print(f"\r{self._progress_prefix()}[crawl] [{bar}] {pct:>3}%  {i}/{len(nodes)} universities", end="", flush=True)

                uni = self._process_university(node)
                if uni is None:
                    self.stats["failed"] += 1
                    continue
                self.universities.append(uni)

                if self.is_sustainability:
                    self.stats["success"] += 1
                    continue

                if not details_enabled:
                    if detail_fallback_triggered and uni.path:
                        detail_deferred_paths.append(uni.path)
                    self.stats["success"] += 1
                    continue

                if not uni.path:
                    self.stats["skipped"] += 1
                    continue

                try:
                    html = fetcher.fetch_university_detail(uni.path)                              
                    if html:
                        uni.requirements = self.extractor.extract_requirements(html)
                        self.stats["success"] += 1
                        detail_forbidden_streak = 0
                    else:
                        self.stats["failed"] += 1
                        detail_forbidden_streak = 0
                except Exception as e:
                    self.stats["failed"] += 1
                    if _is_forbidden_error(e):
                        detail_forbidden_streak += 1
                        detail_forbidden_hits += 1
                        detail_deferred_paths.append(uni.path)
                        if detail_forbidden_streak >= detail_forbidden_threshold and details_enabled:
                            details_enabled = False
                            detail_fallback_triggered = True
                            print(f"\n{self._progress_prefix()}[degrade] detected consecutive detail 403 (>= {detail_forbidden_threshold}), switching to rankings-only for remaining schools.")
                    else:
                        detail_forbidden_streak = 0
        except KeyboardInterrupt:
            self.interrupted = True
            self.logger.warning("KeyboardInterrupt caught during university crawl. Returning partial results.")
            print(f"\n{self._progress_prefix()} [interrupt] Graceful skip triggered. Processing partially collected universities...")

        if self.config.show_progress:
            print()

        try:
            fetcher.close()                              
        except Exception:
            pass

        setattr(self.config, "_detail_fallback_triggered", detail_fallback_triggered)
        unique_deferred = list(dict.fromkeys([p for p in detail_deferred_paths if p]))
        setattr(self.config, "_detail_deferred_paths", unique_deferred)
        existing_forbidden = int(getattr(self.config, "_detail_forbidden_count", 0) or 0)
        setattr(self.config, "_detail_forbidden_count", existing_forbidden + detail_forbidden_hits)
        return self.universities

    async def crawl_async(self) -> List[University]:
        if AsyncUniversityFetcher is None:
            self.logger.warning("aiohttp not installed, falling back to sync crawl")
            return self.crawl()

        self.logger.info("Starting university crawl (async)")
        fetcher = cast(AsyncUniversityFetcher, self.fetcher)
        detail_deferred_paths: List[str] = []
        detail_fallback_triggered = False
        detail_forbidden_streak = 0
        detail_forbidden_threshold = max(1, int(getattr(self.config, "detail_forbidden_streak_threshold", 8) or 8))

        try:
            try:
                data = await fetcher.fetch_rankings()
            except KeyboardInterrupt:
                self.interrupted = True
                return []
            except Exception as e:
                self.logger.error(f"Failed to fetch rankings: {e}")
                print("✗ Failed to fetch ranking data")
                return []

            if not isinstance(data, dict) or "score_nodes" not in data:
                self.logger.error("No ranking data found")
                print("✗ Failed to fetch ranking data")
                return []

            if self.is_region:
                nodes = await self._collect_region_nodes_async(fetcher, data)
            else:
                nodes = await self._collect_nodes_async(fetcher, data)

            if self.config.ranking_limit:
                nodes = nodes[: self.config.ranking_limit]
            if self.config.sort_ascending:
                nodes.reverse()

            if self.is_region and len(nodes) == 0:
                print(f"{self._progress_prefix()}Note: 0 rows after sub-region filtering. Check source route/nid mapping.")
            if self.is_region and self.config.ranking_limit and len(nodes) < self.config.ranking_limit:
                print(f"{self._progress_prefix()}Note: only {len(nodes)} rows matched sub-region filter (requested top {self.config.ranking_limit}).")

            self.stats["total"] = len(nodes)
            self.logger.info(f"Found {len(nodes)} universities to process (async)")

            if self.is_sustainability or not bool(getattr(self.config, "fetch_details", True)):
                try:
                    for i, node in enumerate(nodes, start=1):
                        uni = self._process_university(node)
                        if uni is None:
                            self.stats["failed"] += 1
                            continue
                        self.universities.append(uni)
                        self.stats["success"] += 1
                        if self.config.show_progress:
                            pct = int(i / max(1, len(nodes)) * 100)
                            filled = pct // 5
                            bar = "█" * filled + "░" * (20 - filled)
                            print(f"\r{self._progress_prefix()}[crawl] [{bar}] {pct:>3}%  {i}/{len(nodes)} universities", end="", flush=True)
                except KeyboardInterrupt:
                    self.interrupted = True
                    self.logger.warning("KeyboardInterrupt caught during university processing (async/basic). Returning partial results.")
                    print(f"\n{self._progress_prefix()} [interrupt] Graceful skip triggered. Processing partially collected universities...")

                if self.config.show_progress:
                    print()
                setattr(self.config, "_detail_fallback_triggered", False)
                setattr(self.config, "_detail_deferred_paths", [])
                return self.universities

            local_parse_workers = max(1, int(getattr(self.config, "local_parse_workers", 1) or 1))
            detail_chunk_size = max(1, int(getattr(self.config, "detail_chunk_size", 20) or 20))
            pending_parse: List[tuple[University, str]] = []
            details_enabled = True
            i = 0

            try:
                for chunk_start in range(0, len(nodes), detail_chunk_size):
                    chunk_nodes = nodes[chunk_start:chunk_start + detail_chunk_size]
                    paths = [str(node.get("path", "")) for node in chunk_nodes]
                    if details_enabled:
                        setattr(self.config, "_detail_last_errors", [])
                        html_list = await fetcher.fetch_all_details(paths)
                        raw_errors = getattr(self.config, "_detail_last_errors", []) or []
                        err_status_by_path = {
                            str(err.get("path", "")): err.get("status")
                            for err in raw_errors
                            if isinstance(err, dict) and err.get("path")
                        }
                    else:
                        html_list = [None for _ in chunk_nodes]
                        err_status_by_path = {}

                    for node, html in zip(chunk_nodes, html_list):
                        i += 1
                        uni = self._process_university(node)
                        if uni is None:
                            self.stats["failed"] += 1
                            continue
                        self.universities.append(uni)
                        path = str(node.get("path", ""))
                        if not details_enabled:
                            if path:
                                detail_deferred_paths.append(path)
                            self.stats["success"] += 1
                        elif html:
                            detail_forbidden_streak = 0
                            if local_parse_workers > 1:
                                pending_parse.append((uni, html))
                            else:
                                try:
                                    uni.requirements = self.extractor.extract_requirements(html)
                                    self.stats["success"] += 1
                                except Exception:
                                    self.stats["failed"] += 1
                        elif not path:
                            self.stats["skipped"] += 1
                        else:
                            status = err_status_by_path.get(path)
                            if status == 403:
                                detail_forbidden_streak += 1
                                detail_deferred_paths.append(path)
                                if detail_forbidden_streak >= detail_forbidden_threshold and details_enabled:
                                    details_enabled = False
                                    detail_fallback_triggered = True
                                    print(f"\n{self._progress_prefix()}[degrade] detected consecutive detail 403 (>= {detail_forbidden_threshold}), switching to rankings-only for remaining schools.")
                            else:
                                detail_forbidden_streak = 0
                            self.stats["failed"] += 1
                        if self.config.show_progress:
                            pct = int(i / max(1, len(nodes)) * 100)
                            filled = pct // 5
                            bar = "█" * filled + "░" * (20 - filled)
                            print(f"\r{self._progress_prefix()}[crawl] [{bar}] {pct:>3}%  {i}/{len(nodes)} universities", end="", flush=True)
            except KeyboardInterrupt:
                self.interrupted = True
                self.logger.warning("KeyboardInterrupt caught during university processing (async/chunked). Returning partial results.")
                print(f"\n{self._progress_prefix()} [interrupt] Graceful skip triggered. Processing partially collected universities...")

            if pending_parse:
                sem = asyncio.Semaphore(local_parse_workers)
                async def _parse_one(uni: University, html_text: str) -> bool:
                    async with sem:
                        try:
                            req = await asyncio.to_thread(self.extractor.extract_requirements, html_text)
                            uni.requirements = req
                            return True
                        except Exception:
                            return False
                parsed = await asyncio.gather(*[_parse_one(uni, html) for uni, html in pending_parse])
                ok_count = sum(1 for x in parsed if x)
                self.stats["success"] += ok_count
                self.stats["failed"] += (len(parsed) - ok_count)

            if self.config.show_progress:
                print()
            setattr(self.config, "_detail_fallback_triggered", detail_fallback_triggered)
            unique_deferred = list(dict.fromkeys([p for p in detail_deferred_paths if p]))
            setattr(self.config, "_detail_deferred_paths", unique_deferred)
            return self.universities
        except KeyboardInterrupt:
            self.interrupted = True
            self.logger.warning("KeyboardInterrupt caught during university crawl (async). Returning partial results.")
            print(f"\n{self._progress_prefix()} [interrupt] Graceful skip triggered. Processing partially collected universities...")
            return self.universities
        finally:
            try:
                await fetcher.close()
            except Exception:
                pass

    def _progress_prefix(self) -> str:
        label = str(getattr(self.config, "progress_label", "") or "").strip()
        if not label:
            return ""
        return f"[{label}] "


def run_crawler(
    ranking_id: Optional[Union[str, List[str]]] = None,
    ranking_page_url: Optional[str] = None,
    region_name: Optional[str] = None,
    country: Union[str, List[str], None] = None,
    output_format: str = "console",
    output_file: Optional[str] = None,
    ranking_limit: int = 0,
    sort_ascending: bool = False,
    use_async: bool = False,
    show_progress: bool = True,
    log_file: Optional[str] = None,
    log_level: str = "INFO",
) -> List[University]:
    level = getattr(logging, (log_level or "INFO").upper(), logging.INFO)
    setup_logging(level=level, log_file=log_file)
    config_args: Dict[str, Any] = {
        "country": country,
        "ranking_page_url": ranking_page_url,
        "region_name": region_name,
        "output_format": output_format,
        "output_file": output_file,
        "ranking_limit": ranking_limit,
        "sort_ascending": sort_ascending,
        "use_async": use_async,
        "show_progress": show_progress,
    }

    def _run_one(rid: Optional[str]) -> List[University]:
        if rid:
            config_args["ranking_id"] = rid
        else:
            config_args["ranking_id"] = None
        config = Config(**config_args)
        crawler = UniversityCrawler(config)
        if config.use_async:
            return asyncio.run(crawler.crawl_async())
        return crawler.crawl()

    if isinstance(ranking_id, list):
        target = int(ranking_limit) if ranking_limit is not None else 0
        if target <= 0:
            return []
        unique: List[University] = []
        seen = set()
        original_limit = config_args.get("ranking_limit", target)
        for rid in ranking_id:
            remaining = target - len(unique)
            if remaining <= 0:
                break
            config_args["ranking_limit"] = remaining
            rows = _run_one(rid)
            for uni in rows:
                key = (uni.name, uni.country)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(uni)
                if len(unique) >= target:
                    break
        config_args["ranking_limit"] = original_limit
        unique = unique[:target]
        exporter = get_exporter(output_format, width=Config().console_width)
        db_writer = DBWriter()
        ranking_type_value = "multi" if ranking_id else "world"
        crawl_run_id = db_writer.start_crawl_run(
            source_name="QS",
            ranking_type=ranking_type_value,
            notes="run_crawler multi-ranking batch",
        )
        try:
            for uni in unique:
                raw_id = db_writer.insert_raw_record(
                    source_name="QS",
                    ranking_type=ranking_type_value,
                    raw_json=json.dumps(uni.to_dict(), ensure_ascii=False),
                    raw_text=None,
                    source_url=uni.qs_profile_path or uni.path or None,
                    crawl_run_id=crawl_run_id,
                    record_type="university_object",
                )
                db_writer.ingest_university(
                    uni,
                    ranking_source="QS",
                    ranking_type=ranking_type_value,
                    ranking_year=None,
                    raw_id=raw_id,
                )
            db_writer.finish_crawl_run(crawl_run_id, status="finished")
            db_writer.commit()
        except Exception:
            db_writer.finish_crawl_run(crawl_run_id, status="failed")
            db_writer.commit()
            raise
        finally:
            db_writer.close()
        exporter.export(unique, output_file)
        return unique

    universities = _run_one(ranking_id if isinstance(ranking_id, str) else None)
    exporter = get_exporter(output_format, width=Config().console_width)
    db_writer = DBWriter()
    ranking_type_value = str(ranking_id) if isinstance(ranking_id, str) else "world"
    crawl_run_id = db_writer.start_crawl_run(
        source_name="QS",
        ranking_type=ranking_type_value,
        notes="run_crawler single-ranking batch",
    )
    try:
        for uni in universities:
            raw_id = db_writer.insert_raw_record(
                source_name="QS",
                ranking_type=ranking_type_value,
                raw_json=json.dumps(uni.to_dict(), ensure_ascii=False),
                raw_text=None,
                source_url=uni.qs_profile_path or uni.path or None,
                crawl_run_id=crawl_run_id,
                record_type="university_object",
            )
            db_writer.ingest_university(
                uni,
                ranking_source="QS",
                ranking_type=ranking_type_value,
                ranking_year=None,
                raw_id=raw_id,
            )
        db_writer.finish_crawl_run(crawl_run_id, status="finished")
        db_writer.commit()
    except Exception:
        db_writer.finish_crawl_run(crawl_run_id, status="failed")
        db_writer.commit()
        raise
    finally:
        db_writer.close()
    exporter.export(universities, output_file)
    return universities
