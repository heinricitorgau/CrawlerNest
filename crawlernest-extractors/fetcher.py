#!/usr/bin/env python3


from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import ssl
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

import requests

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore

from config import Config
from constants.countries import COUNTRY_CODES, get_available_countries
from utils import retry

logger = logging.getLogger("UniversityFetcher")

if TYPE_CHECKING:
    import aiohttp as aiohttp_module


def _abs_url(base_url: str, path: str) -> str:
    """整合基礎 URL 與相對路徑，確保路徑銜接處不會出現重複的斜線。"""
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    # Ensure single slash join
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _extract_nid_from_html(html: str) -> Optional[str]:
    """
    【技術細節：NID 探針】
    從 HTML 源碼中提取排名 ID (NID)。
    由於 QS 官網會將數據埋在不同的地方，此處採用多重正則策略：
    1. 尋找嵌入的 JSON 結構中的 "nid" 欄位。
    2. 尋找 HTML 標籤中的 data-nid 屬性。
    3. 尋找腳本中隱含的 API 調用路徑。
    """
    patterns = [
        r'"nid"\s*:\s*"?(\d+)"?',          # JSON-like nid
        r"data-nid=\"(\d+)\"",            # data-nid attribute
        r"/rankings/api/ranking/(\d+)\b",     # direct API url embedded
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return m.group(1)
    return None


def _extract_nids_from_html(html: str) -> List[str]:

    patterns = [
        r'"nid"\s*:\s*"?(\d+)"?',
        r"data-nid=\"(\d+)\"",
        r"/rankings/api/ranking/(\d+)\b",
    ]
    seen = set()
    out: List[str] = []
    for p in patterns:
        for m in re.findall(p, html):
            nid = str(m)
            if nid not in seen:
                seen.add(nid)
                out.append(nid)
    return out


def _find_score_nodes(obj: Any) -> Optional[List[Dict[str, Any]]]:
    """
    【技術細節：遞迴搜尋數據節點】
    在複雜的 JSON 樹狀結構中，深度優先搜尋 (DFS) 名為 'score_nodes' 的列表。
    這用於應對 QS API 返回格式不固定、節點層級可能變動的問題。
    """
    if isinstance(obj, dict):
        v = obj.get("score_nodes")
        if isinstance(v, list):
            return v  # type: ignore[return-value]
        for vv in obj.values():
            got = _find_score_nodes(vv)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for it in obj:
            got = _find_score_nodes(it)
            if got is not None:
                return got
    return None


def _extract_prefetched_score_nodes_from_html(html: str) -> Optional[Dict[str, Any]]:

    script_matches = re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
    for raw in script_matches:
        txt = raw.strip()
        if not txt or "score_nodes" not in txt:
            continue
        # try raw JSON first
        for candidate in (txt, txt.replace("&quot;", '"')):
            try:
                obj = json.loads(candidate)
            except Exception:
                continue
            nodes = _find_score_nodes(obj)
            if nodes is not None:
                return {"score_nodes": nodes}
    return None


def _extract_subregion_id_from_html(html: str, region_name: str) -> Optional[str]:

    if not html or not region_name:
        return None
    target = re.sub(r"\s+", " ", region_name.strip().lower())
    target_compact = target.replace("-", " ").strip()

    patterns = [
        # {"label":"Central America","value":"1234"}
        r'"label"\s*:\s*"([^"]+)"[^{}]{0,200}"value"\s*:\s*"?(\d+)"?',
        # {"name":"Central America","id":"1234"}
        r'"name"\s*:\s*"([^"]+)"[^{}]{0,200}"id"\s*:\s*"?(\d+)"?',
        # {"id":"1234","name":"Central America"}
        r'"id"\s*:\s*"?(\d+)"?[^{}]{0,200}"name"\s*:\s*"([^"]+)"',
        # {"value":"1234","label":"Central America"}
        r'"value"\s*:\s*"?(\d+)"?[^{}]{0,200}"label"\s*:\s*"([^"]+)"',
    ]
    for p in patterns:
        for m in re.finditer(p, html, flags=re.IGNORECASE):
            a, b = m.group(1), m.group(2)
            if a.isdigit():
                sid, name = a, b
            else:
                sid, name = b, a
            n = re.sub(r"\s+", " ", name.strip().lower()).replace("-", " ")
            if n == target_compact:
                return sid
    return None


def _payload_matches_page(data: Dict[str, Any], ranking_page_url: Optional[str]) -> bool:

    if not ranking_page_url:
        return True
    page = ranking_page_url.lower()
    blob = json.dumps(data, ensure_ascii=False).lower()
    page_norm = page.replace("-", " ")
    blob_norm = blob.replace("-", " ")

    if "sustainability" in page:
        return "sustainability" in blob_norm
    hints = [
        "central asia",
        "southern asia",
        "eastern asia",
        "south eastern asia",
        "south-eastern asia",
        "western asia",
        "the caribbean",
        "caribbean",
        "central america",
        "south america",
        "northern europe",
        "western europe",
        "eastern europe",
        "southern europe",
    ]
    for h in hints:
        if h in page_norm:
            if h in blob_norm:
                return True
            return False
    return True


def _ranking_page_fallbacks(ranking_page_url: str) -> List[str]:
    """
    【技術細節：自動降級路徑系統】
    當特定的子排名頁面無法解析出 NID 時，系統會自動向上尋找「父級排名頁」。
    例如：某一學科排名失效時，系統會嘗試抓取該學科的分類首頁，從中偵測相關聯的 NID。
    這大大提高了爬蟲在面對網站改版時的「存活率」。
    """
    url = (ranking_page_url or "").strip()
    if not url:
        return []
    fallbacks = [url]
    parent_markers = [
        "arab-region-rankings",
        "asia-university-rankings",
        "europe-university-rankings",
        "latin-america-caribbean-rankings",
        "latin-america-university-rankings",
        "latin-america-central-america-rankings",
        "latin-america-south-america-rankings",
    ]
    for marker in parent_markers:
        idx = url.find(marker)
        if idx != -1:
            parent = url[: idx + len(marker)]
            if parent not in fallbacks:
                fallbacks.append(parent)
    # Latin America pages exist in multiple slug variants; try sibling variants too.
    if "latin-america-university-rankings" in url:
        alt = url.replace("latin-america-university-rankings", "latin-america-caribbean-rankings")
        if alt not in fallbacks:
            fallbacks.append(alt)
    if "latin-america-caribbean-rankings" in url:
        alt = url.replace("latin-america-caribbean-rankings", "latin-america-university-rankings")
        if alt not in fallbacks:
            fallbacks.append(alt)
    # Ensure parent pages are always included for sub-region urls.
    if "central-america" in url or "south-america" in url or "the-caribbean" in url:
        for p in (
            "https://www.topuniversities.com/latin-america-caribbean-rankings",
            "https://www.topuniversities.com/latin-america-university-rankings",
            "https://www.topuniversities.com/latin-america-central-america-rankings",
            "https://www.topuniversities.com/latin-america-south-america-rankings",
        ):
            if p not in fallbacks:
                fallbacks.append(p)
    return fallbacks


def _region_param_variants(config: Config) -> List[Dict[str, str]]:

    region_name = str(getattr(config, "region_name", "") or "").strip()
    if not region_name:
        return [{}]

    slug = region_name.lower().replace("&", "and").replace("-", " ")
    slug = " ".join(slug.split())
    variants = [
        {},
        {"region": region_name},
        {"regions": region_name},
        {"subregion": region_name},
        {"subregions": region_name},
        {"sub_region": region_name},
        {"sub_regions": region_name},
        {"region": slug},
        {"regions": slug},
        {"subregion": slug},
        {"subregions": slug},
        {"sub_region": slug},
        {"sub_regions": slug},
    ]
    subregion_id = str(getattr(config, "_subregion_id", "") or "").strip()
    if subregion_id.isdigit():
        variants.extend(
            [
                {"subregion": subregion_id},
                {"subregions": subregion_id},
                {"sub_region": subregion_id},
                {"sub_regions": subregion_id},
                {"region": subregion_id},
                {"regions": subregion_id},
                {"filter_subregion": subregion_id},
            ]
        )
    # de-dup
    out: List[Dict[str, str]] = []
    seen = set()
    for v in variants:
        key = tuple(sorted(v.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _country_param_variants(config: Config) -> List[Optional[str]]:

    raw = getattr(config, "country", None)
    if not raw:
        return [None]

    # 支援多個國家
    if isinstance(raw, list):
        if not raw:
            return [None]
        
        # 為每個國家生成變體,然後組合
        all_variants: List[str] = []
        
        for country in raw:
            country_str = str(country).strip()
            if not country_str:
                continue
                
            variants: List[str] = []
            
            def add(v: Optional[str]) -> None:
                if not v:
                    return
                s = str(v).strip()
                if s and s not in variants:
                    variants.append(s)

            add(country_str)
            add(country_str.lower())
            add(country_str.upper())
            add(country_str.title())

            cc = {k.lower(): v for k, v in COUNTRY_CODES.items()}
            iso = get_available_countries()
            reverse: Dict[str, str] = {}
            for code, name in {**iso, **cc}.items():
                reverse.setdefault(name.lower(), code.lower())

            if len(country_str) == 2 and country_str.lower().isalpha():
                code = country_str.lower()
                add(cc.get(code))
                add(iso.get(code))
            else:
                code = reverse.get(country_str.lower())
                if code:
                    add(code)
                    add(code.upper())
                    add(cc.get(code))
                    add(iso.get(code))
            
            # 只取第一個有效變體
            if variants:
                all_variants.append(variants[0])
        
        if not all_variants:
            return [None]
        
        # 用逗號連接所有國家代碼
        return [",".join(all_variants)]
    
    # 單個國家的原始邏輯
    raw_str = str(raw).strip()
    if not raw_str:
        return [None]

    variants: List[str] = []

    def add(v: Optional[str]) -> None:
        if not v:
            return
        s = str(v).strip()
        if s and s not in variants:
            variants.append(s)

    add(raw_str)
    add(raw_str.lower())
    add(raw_str.upper())
    add(raw_str.title())

    cc = {k.lower(): v for k, v in COUNTRY_CODES.items()}
    iso = get_available_countries()
    reverse: Dict[str, str] = {}
    for code, name in {**iso, **cc}.items():
        reverse.setdefault(name.lower(), code.lower())

    if len(raw_str) == 2 and raw_str.lower().isalpha():
        code = raw_str.lower()
        add(cc.get(code))
        add(iso.get(code))
    else:
        code = reverse.get(raw_str.lower())
        if code:
            add(code)
            add(code.upper())
            add(cc.get(code))
            add(iso.get(code))

    return [*variants]


class UniversityFetcher:


    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def _ensure_ranking_id(self) -> str:
        nid = getattr(self.config, "ranking_id", None)
        if nid:
            return str(nid)

        ranking_page_url = getattr(self.config, "ranking_page_url", None)
        if not ranking_page_url:
            raise ValueError("ranking_id or ranking_page_url is required")

        tried: List[str] = []
        for page_url in _ranking_page_fallbacks(ranking_page_url):
            tried.append(page_url)
            try:
                resp = self.session.get(
                    page_url,
                    timeout=getattr(self.config, "timeout", 15),
                    headers=self.config.get_headers(),
                )
                resp.raise_for_status()
                prefetched = _extract_prefetched_score_nodes_from_html(resp.text)
                if prefetched and page_url == ranking_page_url:
                    self.config._prefetched_payload = prefetched
                if page_url == ranking_page_url:
                    sid = _extract_subregion_id_from_html(resp.text, str(getattr(self.config, "region_name", "") or ""))
                    if sid:
                        self.config._subregion_id = sid
                nids = _extract_nids_from_html(resp.text)
                nid2 = nids[0] if nids else _extract_nid_from_html(resp.text)
                if not nid2:
                    continue
                self.config._ranking_id_candidates = nids
                self.config._resolved_ranking_page_url = page_url
                self.config.ranking_id = nid2
                return nid2
            except Exception:
                continue
        # If nid cannot be resolved but page contains prefetched score_nodes,
        # allow caller to use that payload for page 0.
        if getattr(self.config, "_prefetched_payload", None):
            self.config.ranking_id = "0"
            return "0"
        raise ValueError(
            f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
        )

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(requests.RequestException,))
    def fetch_rankings(self) -> Optional[Dict[str, Any]]:
        nid = self._ensure_ranking_id()
        prefetched = getattr(self.config, "_prefetched_payload", None)
        if prefetched and int(getattr(self.config, "page", 0) or 0) == 0:
            self.config._used_prefetched_payload = True
            return prefetched
        if nid == "0":
            return {"score_nodes": []}
        from_page_url = bool(getattr(self.config, "ranking_page_url", None))
        candidate_nids: List[str] = [nid]
        if from_page_url:
            candidate_nids = self.config._ranking_id_candidates or candidate_nids
        if nid not in candidate_nids:
            candidate_nids = [nid] + candidate_nids

        errors: List[str] = []
        first_success: Optional[Dict[str, Any]] = None
        country_requested = bool(str(getattr(self.config, "country", "") or "").strip())
        for cand_nid in candidate_nids:
            urls = [
                f"https://www.topuniversities.com/rankings/api/ranking/{cand_nid}",
                getattr(self.config, "api_url", "https://www.topuniversities.com/rankings/endpoint"),
            ]
            for url in urls:
                try:
                    for extra in _region_param_variants(self.config):
                        for country_v in _country_param_variants(self.config):
                            params = self.config.get_api_params().copy()
                            params["nid"] = str(cand_nid)
                            params.update(extra)
                            if country_v is None:
                                params.pop("countries", None)
                            else:
                                params["countries"] = country_v

                            resp = self.session.get(
                                url,
                                timeout=getattr(self.config, "timeout", 15),
                                headers=self.config.get_headers(),
                                params=params,
                            )
                            resp.raise_for_status()
                            try:
                                data = resp.json()
                            except ValueError:
                                ct = resp.headers.get("Content-Type", "")
                                snippet = resp.text[:200]
                                errors.append(
                                    f"QS API did not return JSON from {url!r} "
                                    f"(status={resp.status_code}, content-type={ct}). "
                                    f"First 200 chars: {snippet!r}"
                                )
                                continue

                            if not _payload_matches_page(data, getattr(self.config, "ranking_page_url", None)):
                                if first_success is None:
                                    first_success = data
                                continue

                            nodes = data.get("score_nodes", []) if isinstance(data, dict) else []
                            if isinstance(nodes, list) and len(nodes) > 0:
                                self.config.ranking_id = str(cand_nid)
                                return data
                            if not country_requested and first_success is None:
                                first_success = data
                            elif first_success is None:
                                first_success = data
                except requests.RequestException as e:
                    error_msg = f"{url!r}: {e}"
                    errors.append(error_msg)
                    logger.debug(f"Request failed: {error_msg}")

        if first_success is not None:
            return first_success
        if errors:
            raise RuntimeError(f"Failed to fetch ranking data using all endpoints for nid={nid}: {' | '.join(errors)}")
        return None

    @retry(max_attempts=3, delay=1.0, backoff=2.0, exceptions=(requests.RequestException,))
    def fetch_university_detail(self, path: str) -> Optional[str]:

        if not path:
            return None
        url = _abs_url(getattr(self.config, "base_url", "https://www.topuniversities.com"), path)
        resp = self.session.get(
            url,
            timeout=getattr(self.config, "timeout", 15),
            headers=self.config.get_headers(),
        )
        resp.raise_for_status()
        return resp.text

    # Backward-compat alias
    def fetch_detail(self, path: str) -> Optional[str]:
        return self.fetch_university_detail(path)


class AsyncUniversityFetcher:


    def __init__(self, config: Config):
        if aiohttp is None:
            raise RuntimeError("aiohttp is not installed")
        self.config = config
        self.session: Optional[Any] = None

        # 【技術細節：SSL 環境自適應】
        # 修正 macOS 或虛擬環境中因缺失根憑證 (root certs) 導致的 SSL 握手失敗。
        if certifi is not None:
            self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            self._ssl_context = ssl.create_default_context()

    async def _ensure_session(self):
        if self.session is None:
            aiohttp_mod = cast("aiohttp_module", aiohttp)
            connector = aiohttp_mod.TCPConnector(
                limit=self.config.max_concurrent_requests,
                ssl=self._ssl_context,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300
            )
            self.session = aiohttp_mod.ClientSession(connector=connector, headers=self.config.get_headers())

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def _ensure_ranking_id(self) -> str:
        nid = getattr(self.config, "ranking_id", None)
        if nid:
            return str(nid)

        ranking_page_url = getattr(self.config, "ranking_page_url", None)
        if not ranking_page_url:
            raise ValueError("ranking_id or ranking_page_url is required")

        await self._ensure_session()
        assert self.session is not None
        tried: List[str] = []
        for page_url in _ranking_page_fallbacks(ranking_page_url):
            tried.append(page_url)
            try:
                async with self.session.get(
                    page_url,
                    timeout=getattr(self.config, "timeout", 15),
                    ssl=self._ssl_context,
                ) as resp:
                    text = await resp.text()
                prefetched = _extract_prefetched_score_nodes_from_html(text)
                if prefetched and page_url == ranking_page_url:
                    self.config._prefetched_payload = prefetched
                if page_url == ranking_page_url:
                    sid = _extract_subregion_id_from_html(text, str(getattr(self.config, "region_name", "") or ""))
                    if sid:
                        self.config._subregion_id = sid
                nids = _extract_nids_from_html(text)
                nid2 = nids[0] if nids else _extract_nid_from_html(text)
                if not nid2:
                    continue
                self.config._ranking_id_candidates = nids
                self.config._resolved_ranking_page_url = page_url
                self.config.ranking_id = nid2
                return nid2
            except Exception:
                continue

        if getattr(self.config, "_prefetched_payload", None):
            self.config.ranking_id = "0"
            return "0"
        raise ValueError(
            f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
        )

    async def fetch_rankings(self) -> Optional[Dict[str, Any]]:
        nid = await self._ensure_ranking_id()
        prefetched = getattr(self.config, "_prefetched_payload", None)
        if prefetched and int(getattr(self.config, "page", 0) or 0) == 0:
            self.config._used_prefetched_payload = True
            return prefetched
        if nid == "0":
            return {"score_nodes": []}
        await self._ensure_session()
        assert self.session is not None

        from_page_url = bool(getattr(self.config, "ranking_page_url", None))
        candidate_nids: List[str] = [nid]
        if from_page_url:
            candidate_nids = self.config._ranking_id_candidates or candidate_nids
        if nid not in candidate_nids:
            candidate_nids = [nid] + candidate_nids

        errors: List[str] = []
        first_success: Optional[Dict[str, Any]] = None
        country_requested = bool(str(getattr(self.config, "country", "") or "").strip())
        for cand_nid in candidate_nids:
            urls = [
                f"https://www.topuniversities.com/rankings/api/ranking/{cand_nid}",
                getattr(self.config, "api_url", "https://www.topuniversities.com/rankings/endpoint"),
            ]
            for url in urls:
                try:
                    for extra in _region_param_variants(self.config):
                        for country_v in _country_param_variants(self.config):
                            params = self.config.get_api_params().copy()
                            params["nid"] = str(cand_nid)
                            params.update(extra)
                            if country_v is None:
                                params.pop("countries", None)
                            else:
                                params["countries"] = country_v

                            async with self.session.get(
                                url,
                                timeout=getattr(self.config, "timeout", 15),
                                ssl=self._ssl_context,
                                params=params,
                            ) as resp:
                                ct = resp.headers.get("Content-Type", "")
                                if resp.status >= 400:
                                    text = await resp.text()
                                    errors.append(
                                        f"QS API error from {url!r} (status={resp.status}, content-type={ct}). "
                                        f"First 200 chars: {text[:200]!r}"
                                    )
                                    continue

                                try:
                                    data = await resp.json()
                                except Exception as e:
                                    text = await resp.text()
                                    errors.append(
                                        f"QS API did not return JSON from {url!r} "
                                        f"(status={resp.status}, content-type={ct}). "
                                        f"First 200 chars: {text[:200]!r}; parser_error={e}"
                                    )
                                    continue

                                if not _payload_matches_page(data, getattr(self.config, "ranking_page_url", None)):
                                    if first_success is None:
                                        first_success = data
                                    continue

                                nodes = data.get("score_nodes", []) if isinstance(data, dict) else []
                                if isinstance(nodes, list) and len(nodes) > 0:
                                    self.config.ranking_id = str(cand_nid)
                                    return data
                                if not country_requested and first_success is None:
                                    first_success = data
                                elif first_success is None:
                                    first_success = data
                except Exception as e:
                    error_msg = f"{url!r}: {e}"
                    errors.append(error_msg)
                    logger.debug(f"Async request failed: {error_msg}")

        if first_success is not None:
            return first_success
        if errors:
            raise RuntimeError(f"Failed to fetch ranking data using all endpoints for nid={nid}: {' | '.join(errors)}")
        return None

    async def fetch_all_details(self, paths: List[str]) -> List[Optional[str]]:
        await self._ensure_session()
        assert self.session is not None
        session = self.session

        base_url = getattr(self.config, "base_url", "https://www.topuniversities.com")
        # 【技術細節：異步閘門併發控制】
        # 使用 asyncio.Semaphore 嚴格限制最大併發連接數。
        # 這是防止被伺服器 WAF (防火牆) 判定為 DDoS 攻擊並封鎖 IP 的關鍵設計。
        sem = asyncio.Semaphore(self.config.max_concurrent_requests)

        async def _fetch_one(path: str) -> Optional[str]:
            if not path:
                return None
            url = _abs_url(base_url, path)
            async with sem:
                try:
                    async with session.get(
                        url,
                        timeout=getattr(self.config, "timeout", 15),
                        ssl=self._ssl_context,
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.text()
                except Exception as e:
                    logger.warning(f"Failed to fetch details for {url}: {e}")
                    return None

        tasks = [_fetch_one(p) for p in paths]
        return await asyncio.gather(*tasks)

    # crawler.py may call fetch_university_detail in sync mode only, but keep for completeness
    async def fetch_university_detail(self, path: str) -> Optional[str]:
        res = await self.fetch_all_details([path])
        return res[0] if res else None
