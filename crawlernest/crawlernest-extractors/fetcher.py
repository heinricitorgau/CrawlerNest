#!/usr/bin/env python3


from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import random
import re
import ssl
import threading
import time
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

import requests

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore

# Used in AsyncUniversityFetcher except clauses (must not reference aiohttp.* when aiohttp is None).
_AIOHTTP_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (asyncio.TimeoutError,)
if aiohttp is not None:
    _AIOHTTP_RETRY_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError)  # type: ignore[misc, assignment]

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore

from config import Config
from constants.countries import COUNTRY_CODES, get_available_countries

logger = logging.getLogger("UniversityFetcher")

_SYNC_RATE_LOCK = threading.Lock()
_SYNC_LAST_REQUEST_AT: Dict[str, float] = {}
_ASYNC_HOST_LOCKS: Dict[str, asyncio.Lock] = {}
_ASYNC_LAST_REQUEST_AT: Dict[str, float] = {}


def _package_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_resolution_cache_path() -> str:
    return os.path.join(_package_root(), "crawlernest-kb", "qs_universe_resolution_cache.json")


def _resolution_cache_key(config: Config) -> str:
    source = str(getattr(config, "source_name", "QS") or "QS").strip().upper()
    universe_type = str(getattr(config, "universe_type", "") or "").strip().lower()
    universe_key = str(getattr(config, "universe_key", "") or "").strip().lower()
    ranking_year = str(getattr(config, "ranking_year", "") or "").strip()
    ranking_page_url = str(getattr(config, "ranking_page_url", "") or "").strip()
    if universe_type and universe_key and ranking_year:
        return f"{source}|{ranking_year}|{universe_type}|{universe_key}"
    if ranking_page_url:
        return f"{source}|page|{ranking_page_url}"
    return f"{source}|default"


def _read_resolution_cache_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        return {"entries": {}}
    except Exception:
        logger.debug("Failed to read resolution cache from %s", path, exc_info=True)
    return {"entries": {}}


def _write_resolution_cache_file(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _read_cached_resolution(config: Config) -> Optional[Dict[str, Any]]:
    cache_path = str(getattr(config, "resolution_cache_path", "") or _default_resolution_cache_path())
    key = _resolution_cache_key(config)
    payload = _read_resolution_cache_file(cache_path)
    entries = payload.get("entries", {})
    if not isinstance(entries, dict):
        return None
    entry = entries.get(key)
    if not isinstance(entry, dict):
        return None
    ttl_seconds = int(getattr(config, "resolution_cache_ttl_seconds", 0) or 0)
    resolved_at = str(entry.get("resolved_at", "") or "").strip()
    if ttl_seconds > 0 and resolved_at:
        try:
            resolved_dt = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
            age_seconds = (datetime.now(timezone.utc) - resolved_dt.astimezone(timezone.utc)).total_seconds()
            if age_seconds > ttl_seconds:
                return None
        except Exception:
            return None
    ranking_id = str(entry.get("ranking_id", "") or "").strip()
    if not ranking_id:
        return None
    return {
        "ranking_id": ranking_id,
        "ranking_id_candidates": [str(v) for v in entry.get("ranking_id_candidates", []) if str(v).strip()],
        "subregion_id": str(entry.get("subregion_id", "") or "").strip(),
        "resolved_ranking_page_url": str(entry.get("resolved_ranking_page_url", "") or "").strip(),
        "api_url": str(entry.get("api_url", "") or "").strip(),
        "resolved_at": resolved_at,
    }


def _write_cached_resolution(
    config: Config,
    *,
    ranking_id: str,
    ranking_id_candidates: List[str],
    resolved_ranking_page_url: str,
) -> None:
    cache_path = str(getattr(config, "resolution_cache_path", "") or _default_resolution_cache_path())
    key = _resolution_cache_key(config)
    payload = _read_resolution_cache_file(cache_path)
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        entries = {}
        payload["entries"] = entries
    entries[key] = {
        "source": str(getattr(config, "source_name", "QS") or "QS").strip().upper(),
        "ranking_year": getattr(config, "ranking_year", None),
        "universe_type": getattr(config, "universe_type", None),
        "universe_key": getattr(config, "universe_key", None),
        "ranking_page_url": getattr(config, "ranking_page_url", None),
        "ranking_id": str(ranking_id or "").strip(),
        "ranking_id_candidates": [str(v) for v in ranking_id_candidates if str(v).strip()],
        "subregion_id": str(getattr(config, "_subregion_id", "") or "").strip(),
        "resolved_ranking_page_url": str(resolved_ranking_page_url or "").strip(),
        "api_url": str(getattr(config, "api_url", "") or "").strip(),
        "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    _write_resolution_cache_file(cache_path, payload)


def _set_failure_classification(config: Config, classification: str, message: str) -> None:
    setattr(config, "_last_failure_classification", classification)
    setattr(config, "_last_failure_message", message)


def _clear_failure_classification(config: Config) -> None:
    setattr(config, "_last_failure_classification", "")
    setattr(config, "_last_failure_message", "")


def _classify_http_block(url: str, status_code: int, text: str = "") -> tuple[str, str]:
    if status_code == 403 or _is_cloudflare_blocked(text):
        return "upstream_blocked", f"QS blocked request to {url} (HTTP {status_code})"
    return "fetch_failed", f"QS request failed at {url} (HTTP {status_code})"


def _safe_response_preview(text: str, max_len: int = 200) -> str:
    """Readable snippet for logs when body may be binary, brotli/gzip mishandled, or HTML."""
    if text is None:
        return ""
    s = str(text)
    if not s:
        return ""
    sample = s[:4096]
    ctrl = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    if len(sample) > 24 and ctrl > len(sample) * 0.22:
        b = s.encode("utf-8", errors="replace")
        return f"[non_text_or_compressed len={len(b)} hex24={b[:24].hex()}]"
    out = s[:max_len].replace("\r", "\\r")
    if len(s) > max_len:
        out += "…"
    return out


def _log_qs_acquire_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    parts: List[str] = [f"event={event}"]
    for key in sorted(fields.keys()):
        val = fields[key]
        if val is None:
            continue
        s = str(val).replace("\n", " ").strip()
        if len(s) > 220:
            s = s[:217] + "..."
        parts.append(f"{key}={s}")
    logger.info("qs_acquire %s", " ".join(parts))


def _jittered_request_delay_seconds(config: Config) -> float:
    base = float(getattr(config, "request_delay", 0.0) or 0.0)
    ratio = float(getattr(config, "request_delay_jitter_ratio", 0.0) or 0.0)
    ratio = max(0.0, min(0.9, ratio))
    if base <= 0.0 or ratio <= 0.0:
        return max(0.0, base)
    span = base * ratio
    return max(0.0, base + random.uniform(-span, span))


def _is_transient_http_status(status_code: int) -> bool:
    return status_code in (408, 425, 429, 500, 502, 503, 504)


def _parse_retry_after_seconds(resp: Any) -> Optional[float]:
    raw = None
    if resp is not None and hasattr(resp, "headers") and resp.headers is not None:
        raw = resp.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _retry_after_from_header_map(headers: Dict[str, str]) -> Optional[float]:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def _qs_ranking_fetch_urls(config: Config, cand_nid: str) -> List[str]:
    api_rest = f"https://www.topuniversities.com/rankings/api/ranking/{cand_nid}"
    endpoint = str(getattr(config, "api_url", "") or "").strip() or "https://www.topuniversities.com/rankings/endpoint"
    order = str(getattr(config, "qs_endpoint_order", "api_first") or "api_first").strip().lower()
    if order == "endpoint_first":
        return [endpoint, api_rest]
    return [api_rest, endpoint]


def _apply_cached_resolution(config: Config, cached: Dict[str, Any]) -> str:
    ranking_id = str(cached.get("ranking_id", "") or "").strip()
    config.ranking_id = ranking_id
    config._ranking_id_from_cache = True
    config._used_resolution_cache = True
    config._ranking_id_candidates = list(cached.get("ranking_id_candidates", []) or [])
    config._subregion_id = str(cached.get("subregion_id", "") or "").strip()
    config._resolved_ranking_page_url = str(cached.get("resolved_ranking_page_url", "") or "").strip()
    config._ranking_id_source = "cache"
    config._page_resolution_skipped = True
    config._page_resolution_attempted = False
    return ranking_id


def _apply_direct_ranking_id(config: Config, ranking_id: str) -> str:
    direct_ranking_id = str(ranking_id or "").strip()
    config.ranking_id = direct_ranking_id
    config._ranking_id_from_cache = False
    config._used_resolution_cache = False
    config._ranking_id_candidates = [direct_ranking_id] if direct_ranking_id else []
    config._resolved_ranking_page_url = ""
    config._ranking_id_source = "direct"
    config._page_resolution_skipped = True
    config._page_resolution_attempted = False
    return direct_ranking_id


def _clear_cached_resolution_state(config: Config) -> None:
    config.ranking_id = ""
    config._ranking_id_from_cache = False
    config._used_resolution_cache = False
    config._ranking_id_candidates = []
    config._prefetched_payload = None
    config._used_prefetched_payload = False
    config._ranking_id_source = ""
    config._page_resolution_skipped = False
    config._page_resolution_attempted = False


def _is_cloudflare_blocked(text: str) -> bool:
    lower = str(text or "").lower()
    return "just a moment" in lower or "cloudflare" in lower or "attention required" in lower

if TYPE_CHECKING:
    import aiohttp as aiohttp_module


def _host_key_from_url(url: Optional[str]) -> str:
    if not url:
        return "_default"
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower() or "_default"
    except Exception:
        return "_default"


def _global_wait_sync(url: Optional[str], delay: float) -> None:
    if delay <= 0:
        return
    host = _host_key_from_url(url)
    with _SYNC_RATE_LOCK:
        now = time.time()
        last = _SYNC_LAST_REQUEST_AT.get(host, 0.0)
        remain = delay - (now - last)
        if remain > 0:
            time.sleep(remain)
            now = time.time()
        _SYNC_LAST_REQUEST_AT[host] = now


async def _global_wait_async(url: Optional[str], delay: float) -> None:
    if delay <= 0:
        return
    host = _host_key_from_url(url)
    lock = _ASYNC_HOST_LOCKS.get(host)
    if lock is None:
        lock = asyncio.Lock()
        _ASYNC_HOST_LOCKS[host] = lock

    async with lock:
        now = time.time()
        last = _ASYNC_LAST_REQUEST_AT.get(host, 0.0)
        remain = delay - (now - last)
        if remain > 0:
            await asyncio.sleep(remain)
            now = time.time()
        _ASYNC_LAST_REQUEST_AT[host] = now


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
    blob = _build_payload_haystack(data)
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


def _build_payload_haystack(data: Dict[str, Any], max_texts: int = 300, max_chars: int = 20000) -> str:

    out: List[str] = []
    char_count = 0

    def add_text(v: Any) -> bool:
        nonlocal char_count
        if v is None:
            return False
        if not isinstance(v, str):
            v = str(v)
        txt = v.strip().lower()
        if not txt:
            return False
        if len(out) >= max_texts:
            return True
        out.append(txt)
        char_count += len(txt)
        return char_count >= max_chars

    candidate_keys = {
        "region",
        "regions",
        "subregion",
        "subregions",
        "sub_region",
        "sub_regions",
        "country",
        "country_name",
        "location",
        "name",
        "title",
        "label",
        "path",
        "url",
        "link",
        "ranking_type",
        "ranking_name",
        "slug",
    }

    queue: List[Any] = [data]
    while queue and len(out) < max_texts and char_count < max_chars:
        obj = queue.pop(0)
        if isinstance(obj, dict):
            for k, v in obj.items():
                kk = str(k).strip().lower()
                if kk in candidate_keys:
                    if add_text(v):
                        break
                if isinstance(v, (dict, list)):
                    queue.append(v)
        elif isinstance(obj, list):
            for it in obj[:300]:
                if isinstance(it, (dict, list)):
                    queue.append(it)
                else:
                    if add_text(it):
                        break

    return " ".join(out)


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


def _hint_key(cand_nid: str, url: str) -> str:

    return f"{cand_nid}|{url}"


def _get_request_hint(config: Config, key: str) -> Optional[Dict[str, Any]]:

    store = getattr(config, "_request_param_hints", None)
    if not isinstance(store, dict):
        return None
    hint = store.get(key)
    if not isinstance(hint, dict):
        return None
    extra = hint.get("extra", {})
    country_v = hint.get("country", None)
    if not isinstance(extra, dict):
        return None
    if country_v is not None and not isinstance(country_v, str):
        return None
    return {"extra": dict(extra), "country": country_v}


def _set_request_hint(config: Config, key: str, extra: Dict[str, str], country_v: Optional[str]) -> None:

    store = getattr(config, "_request_param_hints", None)
    if not isinstance(store, dict):
        store = {}
        setattr(config, "_request_param_hints", store)
    store[key] = {"extra": dict(extra), "country": country_v}


def _ordered_param_pairs(
    region_variants: List[Dict[str, str]],
    country_variants: List[Optional[str]],
    hint: Optional[Dict[str, Any]],
) -> List[tuple[Dict[str, str], Optional[str]]]:

    pairs: List[tuple[Dict[str, str], Optional[str]]] = [
        (extra, country_v)
        for extra in region_variants
        for country_v in country_variants
    ]
    if not hint:
        return pairs

    hint_extra = hint.get("extra", {})
    hint_country = hint.get("country", None)

    preferred: List[tuple[Dict[str, str], Optional[str]]] = []
    others: List[tuple[Dict[str, str], Optional[str]]] = []
    for pair in pairs:
        extra, country_v = pair
        if extra == hint_extra and country_v == hint_country:
            preferred.append(pair)
        else:
            others.append(pair)
    return preferred + others


def _pair_key(cand_nid: str, url: str, extra: Dict[str, str], country_v: Optional[str]) -> str:
    extra_key = tuple(sorted(extra.items()))
    return f"{cand_nid}|{url}|{extra_key}|{country_v or ''}"


def _get_failure_ttl(config: Config) -> float:
    try:
        ttl = float(getattr(config, "failed_param_ttl_seconds", 1800.0) or 0.0)
    except Exception:
        ttl = 1800.0
    return max(1.0, ttl)


def _is_pair_blacklisted(config: Config, key: str) -> bool:
    store = getattr(config, "_failed_param_pairs", None)
    if not isinstance(store, dict):
        return False
    expiry = store.get(key)
    now = time.time()
    if isinstance(expiry, (int, float)) and expiry > now:
        return True
    if key in store:
        store.pop(key, None)
    return False


def _mark_pair_failed(config: Config, key: str) -> None:
    store = getattr(config, "_failed_param_pairs", None)
    if not isinstance(store, dict):
        store = {}
        setattr(config, "_failed_param_pairs", store)
    store[key] = time.time() + _get_failure_ttl(config)


class UniversityFetcher:


    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self._last_request_time = 0.0

    def _wait_for_delay(self, url: Optional[str] = None):
        delay = _jittered_request_delay_seconds(self.config)
        if delay > 0:
            _global_wait_sync(url, delay)
        self._last_request_time = time.time()

    def _session_get_transient_retry(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        purpose: str = "qs",
    ) -> Any:
        """GET with rate limiting on first attempt; soft retries only for transient HTTP/network errors (not 403)."""
        timeout = getattr(self.config, "timeout", 15)
        max_attempts = int(getattr(self.config, "qs_transient_retry_max_attempts", 3) or 1)
        max_attempts = max(1, min(8, max_attempts))
        backoff = float(getattr(self.config, "qs_transient_retry_backoff_seconds", 3.0) or 3.0)
        max_sleep = float(getattr(self.config, "qs_transient_retry_max_sleep_seconds", 45.0) or 45.0)
        headers = headers if headers is not None else self.config.get_headers("api")
        params = params or {}
        last_exc: Optional[BaseException] = None
        for attempt in range(max_attempts):
            if attempt == 0:
                self._wait_for_delay(url)
            else:
                sleep_s = min(backoff * (2 ** (attempt - 1)), max_sleep)
                _log_qs_acquire_event(
                    logger,
                    "retry_attempted",
                    url=url,
                    purpose=purpose,
                    attempt=attempt + 1,
                    sleep_seconds=f"{sleep_s:.2f}",
                )
                time.sleep(sleep_s)
            try:
                resp = self.session.get(url, timeout=timeout, headers=headers, params=params)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    _log_qs_acquire_event(
                        logger,
                        "retry_attempted",
                        url=url,
                        purpose=purpose,
                        attempt=attempt + 1,
                        reason=type(exc).__name__,
                    )
                    continue
                raise
            if resp.status_code == 403 or _is_cloudflare_blocked(getattr(resp, "text", "") or ""):
                return resp
            if _is_transient_http_status(resp.status_code) and attempt < max_attempts - 1:
                ra = _parse_retry_after_seconds(resp)
                sleep_s = min(backoff * (2 ** attempt), max_sleep)
                if ra is not None and ra > 0:
                    sleep_s = min(max(ra, sleep_s), max_sleep)
                _log_qs_acquire_event(
                    logger,
                    "retry_attempted",
                    url=url,
                    purpose=purpose,
                    attempt=attempt + 1,
                    http_status=resp.status_code,
                    sleep_seconds=f"{sleep_s:.2f}",
                )
                time.sleep(sleep_s)
                continue
            return resp
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("transient retry exhausted without response")

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def _ensure_ranking_id(self, *, force_refresh: bool = False) -> str:
        direct_ranking_id = str(
            getattr(self.config, "_stable_ranking_id", "") or getattr(self.config, "ranking_id", "") or ""
        ).strip()

        ranking_page_url = getattr(self.config, "ranking_page_url", None)
        if not ranking_page_url and not direct_ranking_id:
            raise ValueError("ranking_id or ranking_page_url is required")

        if not force_refresh:
            cached = _read_cached_resolution(self.config)
            if cached:
                logger.info(
                    "Using cached ranking resolution for %s/%s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                )
                _clear_failure_classification(self.config)
                return _apply_cached_resolution(self.config, cached)
            if direct_ranking_id:
                logger.info(
                    "Using direct ranking_id for %s/%s: %s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                    direct_ranking_id,
                )
                _clear_failure_classification(self.config)
                return _apply_direct_ranking_id(self.config, direct_ranking_id)

        if not ranking_page_url:
            raise ValueError("ranking_page_url is required when cached/direct ranking_id is unavailable")

        tried: List[str] = []
        resolve_blocked = False
        self.config._page_resolution_attempted = True
        self.config._page_resolution_skipped = False
        for page_url in _ranking_page_fallbacks(ranking_page_url):
            tried.append(page_url)
            try:
                resp = self._session_get_transient_retry(
                    page_url,
                    params=None,
                    headers=self.config.get_headers("page"),
                    purpose="page_resolve",
                )
                if resp.status_code == 403 and _is_cloudflare_blocked(resp.text):
                    resolve_blocked = True
                    _set_failure_classification(
                        self.config,
                        "upstream_blocked",
                        f"QS entry resolution blocked by Cloudflare on {page_url}",
                    )
                    logger.warning("QS entry resolution blocked by Cloudflare on %s", page_url)
                    continue
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
                self.config._ranking_id_from_cache = False
                self.config._used_resolution_cache = False
                self.config._ranking_id_source = "page_resolution"
                _write_cached_resolution(
                    self.config,
                    ranking_id=str(nid2),
                    ranking_id_candidates=nids or [str(nid2)],
                    resolved_ranking_page_url=page_url,
                )
                _clear_failure_classification(self.config)
                return nid2
            except requests.RequestException as exc:
                if getattr(exc.response, "status_code", None) == 403:
                    resolve_blocked = True
                    _set_failure_classification(
                        self.config,
                        "upstream_blocked",
                        f"QS entry resolution blocked on {page_url} (HTTP 403)",
                    )
                continue
            except Exception:
                continue
        # If nid cannot be resolved but page contains prefetched score_nodes,
        # allow caller to use that payload for page 0.
        if getattr(self.config, "_prefetched_payload", None):
            self.config.ranking_id = "0"
            self.config._ranking_id_from_cache = False
            self.config._used_resolution_cache = False
            self.config._ranking_id_source = "page_prefetch"
            _clear_failure_classification(self.config)
            return "0"
        if resolve_blocked:
            msg = f"Failed to resolve ranking_id: entry resolution blocked while fetching {ranking_page_url}"
            _set_failure_classification(self.config, "resolve_blocked", msg)
        else:
            msg = f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
            _set_failure_classification(self.config, "resolve_not_found", msg)
        raise ValueError(
            f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
        )

    def fetch_rankings(self) -> Optional[Dict[str, Any]]:
        return self._fetch_rankings_impl(allow_cache_refresh=True)

    def _fetch_rankings_impl(self, *, allow_cache_refresh: bool) -> Optional[Dict[str, Any]]:
        nid = self._ensure_ranking_id()
        prefetched = getattr(self.config, "_prefetched_payload", None)
        if prefetched and int(getattr(self.config, "page", 0) or 0) == 0:
            self.config._used_prefetched_payload = True
            _clear_failure_classification(self.config)
            _log_qs_acquire_event(
                logger,
                "live_success",
                universe_type=getattr(self.config, "universe_type", ""),
                universe_key=getattr(self.config, "universe_key", ""),
                note="html_prefetch_score_nodes",
                page="0",
            )
            return prefetched
        if nid == "0":
            _clear_failure_classification(self.config)
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
        region_variants = _region_param_variants(self.config)
        country_variants = _country_param_variants(self.config)
        self._abort_ranking_fetch = False
        self._upstream_block_warning_emitted = False
        for cand_nid in candidate_nids:
            urls = _qs_ranking_fetch_urls(self.config, str(cand_nid))
            for url in urls:
                key = _hint_key(str(cand_nid), url)
                hint = _get_request_hint(self.config, key)
                for extra, country_v in _ordered_param_pairs(region_variants, country_variants, hint):
                            if self._abort_ranking_fetch:
                                break
                            pair_key = _pair_key(str(cand_nid), url, extra, country_v)
                            if _is_pair_blacklisted(self.config, pair_key):
                                continue
                            params = self.config.get_api_params().copy()
                            params["nid"] = str(cand_nid)
                            params.update(extra)
                            if country_v is None:
                                params.pop("countries", None)
                            else:
                                params["countries"] = country_v

                            try:
                                resp = self._session_get_transient_retry(
                                    url,
                                    params=params,
                                    headers=self.config.get_headers("api"),
                                    purpose="ranking_api",
                                )
                                if resp.status_code >= 400:
                                    classification, message = _classify_http_block(
                                        url,
                                        resp.status_code,
                                        resp.text,
                                    )
                                    _mark_pair_failed(self.config, pair_key)
                                    _set_failure_classification(self.config, classification, message)
                                    preview = _safe_response_preview(resp.text)
                                    error_msg = (
                                        f"{url!r}: HTTP {resp.status_code}; "
                                        f"params={params}; body_preview={preview!r}"
                                    )
                                    errors.append(error_msg)
                                    if classification == "upstream_blocked":
                                        _log_qs_acquire_event(
                                            logger,
                                            "upstream_blocked",
                                            url=url,
                                            http_status=resp.status_code,
                                            universe_type=getattr(self.config, "universe_type", ""),
                                            universe_key=getattr(self.config, "universe_key", ""),
                                            nid=str(cand_nid),
                                        )
                                        if not self._upstream_block_warning_emitted:
                                            self._upstream_block_warning_emitted = True
                                            logger.warning("%s", message)
                                        self._abort_ranking_fetch = True
                                        break
                                    logger.warning("%s", message)
                                    continue
                                resp.raise_for_status()
                            except requests.RequestException as e:
                                _mark_pair_failed(self.config, pair_key)
                                status_code = getattr(getattr(e, "response", None), "status_code", None)
                                if status_code is not None:
                                    classification, message = _classify_http_block(
                                        url,
                                        int(status_code),
                                        getattr(getattr(e, "response", None), "text", "") or "",
                                    )
                                else:
                                    classification, message = (
                                        "fetch_failed",
                                        f"QS request failed at {url}: {e}",
                                    )
                                _set_failure_classification(self.config, classification, message)
                                error_msg = f"{url!r}: {e}"
                                errors.append(error_msg)
                                logger.debug(f"Request failed: {error_msg}")
                                continue

                            try:
                                data = resp.json()
                            except ValueError:
                                _mark_pair_failed(self.config, pair_key)
                                _set_failure_classification(
                                    self.config,
                                    "parse_failed",
                                    f"Non-JSON response from {url!r}",
                                )
                                ct = resp.headers.get("Content-Type", "")
                                snippet = _safe_response_preview(resp.text)
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
                            _set_request_hint(self.config, key, extra, country_v)

                            nodes = data.get("score_nodes", []) if isinstance(data, dict) else []
                            if isinstance(nodes, list) and len(nodes) > 0:
                                self.config.ranking_id = str(cand_nid)
                                self.config._ranking_id_from_cache = False
                                if from_page_url:
                                    _write_cached_resolution(
                                        self.config,
                                        ranking_id=str(cand_nid),
                                        ranking_id_candidates=candidate_nids,
                                        resolved_ranking_page_url=str(
                                            getattr(self.config, "_resolved_ranking_page_url", "") or getattr(self.config, "ranking_page_url", "") or ""
                                        ),
                                    )
                                _clear_failure_classification(self.config)
                                _log_qs_acquire_event(
                                    logger,
                                    "live_success",
                                    url=url,
                                    nid=str(cand_nid),
                                    universe_type=getattr(self.config, "universe_type", ""),
                                    universe_key=getattr(self.config, "universe_key", ""),
                                    endpoint_kind=("rest" if "/rankings/api/ranking/" in url else "endpoint"),
                                    page=str(getattr(self.config, "page", "")),
                                )
                                return data
                            if not country_requested and first_success is None:
                                first_success = data
                            elif first_success is None:
                                first_success = data

                if self._abort_ranking_fetch:
                    break
            if self._abort_ranking_fetch:
                break

        if (
            allow_cache_refresh
            and bool(getattr(self.config, "_used_resolution_cache", False))
            and from_page_url
        ):
            direct_ranking_id = str(getattr(self.config, "_stable_ranking_id", "") or "").strip()
            if direct_ranking_id and direct_ranking_id != str(nid):
                logger.warning(
                    "Cached ranking resolution failed during list fetch for %s/%s; falling back to direct ranking_id=%s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                    direct_ranking_id,
                )
                _apply_direct_ranking_id(self.config, direct_ranking_id)
                return self._fetch_rankings_impl(allow_cache_refresh=False)
            logger.warning(
                "Cached ranking resolution failed during list fetch for %s/%s; skipping page resolution fallback under stable-entry policy",
                getattr(self.config, "universe_type", "unknown"),
                getattr(self.config, "universe_key", "unknown"),
            )

        if first_success is not None:
            _clear_failure_classification(self.config)
            _log_qs_acquire_event(
                logger,
                "live_success",
                universe_type=getattr(self.config, "universe_type", ""),
                universe_key=getattr(self.config, "universe_key", ""),
                note="payload_mismatch_or_empty_nodes",
                page=str(getattr(self.config, "page", "")),
            )
            return first_success
        if errors:
            if str(getattr(self.config, "_last_failure_classification", "") or "").strip() == "":
                _set_failure_classification(self.config, "fetch_failed", " | ".join(errors))
            raise RuntimeError(f"Failed to fetch ranking data using all endpoints for nid={nid}: {' | '.join(errors)}")
        return None

    def fetch_university_detail(self, path: str) -> Optional[str]:

        if not path:
            return None
        url = _abs_url(getattr(self.config, "base_url", "https://www.topuniversities.com"), path)
        resp = self._session_get_transient_retry(
            url,
            params=None,
            headers=self.config.get_headers("detail"),
            purpose="detail_page",
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
        self._last_request_time = 0.0

    async def _wait_for_delay(self, url: Optional[str] = None):
        delay = _jittered_request_delay_seconds(self.config)
        if delay > 0:
            await _global_wait_async(url, delay)
        self._last_request_time = time.time()

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

    async def _async_session_get_transient_retry(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        purpose: str = "qs",
    ) -> tuple[int, str, Dict[str, str]]:
        await self._ensure_session()
        assert self.session is not None
        aiohttp_mod = cast("aiohttp_module", aiohttp)
        timeout = aiohttp_mod.ClientTimeout(total=float(getattr(self.config, "timeout", 15) or 15))
        max_attempts = int(getattr(self.config, "qs_transient_retry_max_attempts", 3) or 1)
        max_attempts = max(1, min(8, max_attempts))
        backoff = float(getattr(self.config, "qs_transient_retry_backoff_seconds", 3.0) or 3.0)
        max_sleep = float(getattr(self.config, "qs_transient_retry_max_sleep_seconds", 45.0) or 45.0)
        headers = headers if headers is not None else self.config.get_headers("api")
        params = params if params is not None else {}
        last_exc: Optional[BaseException] = None
        for attempt in range(max_attempts):
            if attempt == 0:
                await self._wait_for_delay(url)
            else:
                sleep_s = min(backoff * (2 ** (attempt - 1)), max_sleep)
                _log_qs_acquire_event(
                    logger,
                    "retry_attempted",
                    url=url,
                    purpose=purpose,
                    attempt=attempt + 1,
                    sleep_seconds=f"{sleep_s:.2f}",
                )
                await asyncio.sleep(sleep_s)
            try:
                async with self.session.get(
                    url,
                    params=params or None,
                    headers=headers,
                    ssl=self._ssl_context,
                    timeout=timeout,
                ) as resp:
                    status = resp.status
                    hdr_dict = {str(k): str(v) for k, v in resp.headers.items()}
                    text = await resp.text()
            except _AIOHTTP_RETRY_EXCEPTIONS as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    _log_qs_acquire_event(
                        logger,
                        "retry_attempted",
                        url=url,
                        purpose=purpose,
                        attempt=attempt + 1,
                        reason=type(exc).__name__,
                    )
                    continue
                raise
            if status == 403 or _is_cloudflare_blocked(text):
                return status, text, hdr_dict
            if _is_transient_http_status(status) and attempt < max_attempts - 1:
                ra = _retry_after_from_header_map(hdr_dict)
                sleep_s = min(backoff * (2 ** attempt), max_sleep)
                if ra is not None and ra > 0:
                    sleep_s = min(max(ra, sleep_s), max_sleep)
                _log_qs_acquire_event(
                    logger,
                    "retry_attempted",
                    url=url,
                    purpose=purpose,
                    attempt=attempt + 1,
                    http_status=status,
                    sleep_seconds=f"{sleep_s:.2f}",
                )
                await asyncio.sleep(sleep_s)
                continue
            return status, text, hdr_dict
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("async transient retry exhausted without response")

    async def _ensure_ranking_id(self, *, force_refresh: bool = False) -> str:
        direct_ranking_id = str(
            getattr(self.config, "_stable_ranking_id", "") or getattr(self.config, "ranking_id", "") or ""
        ).strip()

        ranking_page_url = getattr(self.config, "ranking_page_url", None)
        if not ranking_page_url and not direct_ranking_id:
            raise ValueError("ranking_id or ranking_page_url is required")

        if not force_refresh:
            cached = _read_cached_resolution(self.config)
            if cached:
                logger.info(
                    "Using cached ranking resolution for %s/%s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                )
                _clear_failure_classification(self.config)
                return _apply_cached_resolution(self.config, cached)
            if direct_ranking_id:
                logger.info(
                    "Using direct ranking_id for %s/%s: %s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                    direct_ranking_id,
                )
                _clear_failure_classification(self.config)
                return _apply_direct_ranking_id(self.config, direct_ranking_id)

        if not ranking_page_url:
            raise ValueError("ranking_page_url is required when cached/direct ranking_id is unavailable")

        await self._ensure_session()
        assert self.session is not None
        tried: List[str] = []
        resolve_blocked = False
        self.config._page_resolution_attempted = True
        self.config._page_resolution_skipped = False
        for page_url in _ranking_page_fallbacks(ranking_page_url):
            tried.append(page_url)
            try:
                status, text, _hdrs = await self._async_session_get_transient_retry(
                    page_url,
                    params=None,
                    headers=self.config.get_headers("page"),
                    purpose="page_resolve",
                )
                if status == 403 and _is_cloudflare_blocked(text):
                    resolve_blocked = True
                    _set_failure_classification(
                        self.config,
                        "upstream_blocked",
                        f"QS entry resolution blocked by Cloudflare on {page_url}",
                    )
                    logger.warning("QS entry resolution blocked by Cloudflare on %s", page_url)
                    continue
                if status >= 400:
                    classification, message = _classify_http_block(page_url, status, text)
                    _set_failure_classification(self.config, classification, message)
                    continue
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
                self.config._ranking_id_from_cache = False
                self.config._used_resolution_cache = False
                self.config._ranking_id_source = "page_resolution"
                _write_cached_resolution(
                    self.config,
                    ranking_id=str(nid2),
                    ranking_id_candidates=nids or [str(nid2)],
                    resolved_ranking_page_url=page_url,
                )
                _clear_failure_classification(self.config)
                return nid2
            except Exception:
                continue

        if getattr(self.config, "_prefetched_payload", None):
            self.config.ranking_id = "0"
            self.config._ranking_id_from_cache = False
            self.config._used_resolution_cache = False
            self.config._ranking_id_source = "page_prefetch"
            _clear_failure_classification(self.config)
            return "0"
        if resolve_blocked:
            msg = f"Failed to resolve ranking_id: entry resolution blocked while fetching {ranking_page_url}"
            _set_failure_classification(self.config, "resolve_blocked", msg)
        else:
            msg = f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
            _set_failure_classification(self.config, "resolve_not_found", msg)
        raise ValueError(
            f"Failed to resolve ranking_id (nid) from ranking_page_url. Tried: {tried}"
        )

    async def fetch_rankings(self) -> Optional[Dict[str, Any]]:
        return await self._fetch_rankings_impl(allow_cache_refresh=True)

    async def _fetch_rankings_impl(self, *, allow_cache_refresh: bool) -> Optional[Dict[str, Any]]:
        nid = await self._ensure_ranking_id()
        prefetched = getattr(self.config, "_prefetched_payload", None)
        if prefetched and int(getattr(self.config, "page", 0) or 0) == 0:
            self.config._used_prefetched_payload = True
            _clear_failure_classification(self.config)
            _log_qs_acquire_event(
                logger,
                "live_success",
                universe_type=getattr(self.config, "universe_type", ""),
                universe_key=getattr(self.config, "universe_key", ""),
                note="html_prefetch_score_nodes",
                page="0",
            )
            return prefetched
        if nid == "0":
            _clear_failure_classification(self.config)
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
        region_variants = _region_param_variants(self.config)
        country_variants = _country_param_variants(self.config)
        self._abort_ranking_fetch = False
        self._upstream_block_warning_emitted = False
        for cand_nid in candidate_nids:
            urls = _qs_ranking_fetch_urls(self.config, str(cand_nid))
            for url in urls:
                key = _hint_key(str(cand_nid), url)
                hint = _get_request_hint(self.config, key)
                for extra, country_v in _ordered_param_pairs(region_variants, country_variants, hint):
                            if self._abort_ranking_fetch:
                                break
                            pair_key = _pair_key(str(cand_nid), url, extra, country_v)
                            if _is_pair_blacklisted(self.config, pair_key):
                                continue
                            params = self.config.get_api_params().copy()
                            params["nid"] = str(cand_nid)
                            params.update(extra)
                            if country_v is None:
                                params.pop("countries", None)
                            else:
                                params["countries"] = country_v

                            try:
                                status, text, hdrs = await self._async_session_get_transient_retry(
                                    url,
                                    params=params,
                                    headers=self.config.get_headers("api"),
                                    purpose="ranking_api",
                                )
                                ct = hdrs.get("Content-Type", "") or hdrs.get("content-type", "")
                                if status >= 400:
                                    classification, message = _classify_http_block(
                                        url,
                                        status,
                                        text,
                                    )
                                    _mark_pair_failed(self.config, pair_key)
                                    _set_failure_classification(self.config, classification, message)
                                    preview = _safe_response_preview(text)
                                    errors.append(
                                        f"QS API error from {url!r} (status={status}, content-type={ct}). "
                                        f"params={params}; body_preview={preview!r}"
                                    )
                                    if classification == "upstream_blocked":
                                        _log_qs_acquire_event(
                                            logger,
                                            "upstream_blocked",
                                            url=url,
                                            http_status=status,
                                            universe_type=getattr(self.config, "universe_type", ""),
                                            universe_key=getattr(self.config, "universe_key", ""),
                                            nid=str(cand_nid),
                                        )
                                        if not self._upstream_block_warning_emitted:
                                            self._upstream_block_warning_emitted = True
                                            logger.warning("%s", message)
                                        self._abort_ranking_fetch = True
                                        break
                                    logger.warning("%s", message)
                                    continue
                                try:
                                    data = json.loads(text)
                                except ValueError as e:
                                    _mark_pair_failed(self.config, pair_key)
                                    _set_failure_classification(
                                        self.config,
                                        "parse_failed",
                                        f"Non-JSON response from {url!r}: {e}",
                                    )
                                    errors.append(
                                        f"QS API did not return JSON from {url!r} "
                                        f"(status={status}, content-type={ct}). "
                                        f"First 200 chars: {_safe_response_preview(text)!r}; parser_error={e}"
                                    )
                                    continue
                            except Exception as e:
                                _mark_pair_failed(self.config, pair_key)
                                _set_failure_classification(
                                    self.config,
                                    "fetch_failed",
                                    f"QS request failed at {url}: {e}",
                                )
                                error_msg = f"{url!r}: {e}"
                                errors.append(error_msg)
                                logger.debug("Async request failed: %s", error_msg)
                                continue

                            if not _payload_matches_page(data, getattr(self.config, "ranking_page_url", None)):
                                if first_success is None:
                                    first_success = data
                                continue
                            _set_request_hint(self.config, key, extra, country_v)

                            nodes = data.get("score_nodes", []) if isinstance(data, dict) else []
                            if isinstance(nodes, list) and len(nodes) > 0:
                                self.config.ranking_id = str(cand_nid)
                                self.config._ranking_id_from_cache = False
                                if from_page_url:
                                    _write_cached_resolution(
                                        self.config,
                                        ranking_id=str(cand_nid),
                                        ranking_id_candidates=candidate_nids,
                                        resolved_ranking_page_url=str(
                                            getattr(self.config, "_resolved_ranking_page_url", "") or getattr(self.config, "ranking_page_url", "") or ""
                                        ),
                                    )
                                _clear_failure_classification(self.config)
                                _log_qs_acquire_event(
                                    logger,
                                    "live_success",
                                    url=url,
                                    nid=str(cand_nid),
                                    universe_type=getattr(self.config, "universe_type", ""),
                                    universe_key=getattr(self.config, "universe_key", ""),
                                    endpoint_kind=("rest" if "/rankings/api/ranking/" in url else "endpoint"),
                                    page=str(getattr(self.config, "page", "")),
                                )
                                return data
                            if not country_requested and first_success is None:
                                first_success = data
                            elif first_success is None:
                                first_success = data

                if self._abort_ranking_fetch:
                    break
            if self._abort_ranking_fetch:
                break

        if (
            allow_cache_refresh
            and bool(getattr(self.config, "_used_resolution_cache", False))
            and from_page_url
        ):
            direct_ranking_id = str(getattr(self.config, "_stable_ranking_id", "") or "").strip()
            if direct_ranking_id and direct_ranking_id != str(nid):
                logger.warning(
                    "Cached ranking resolution failed during list fetch for %s/%s; falling back to direct ranking_id=%s",
                    getattr(self.config, "universe_type", "unknown"),
                    getattr(self.config, "universe_key", "unknown"),
                    direct_ranking_id,
                )
                _apply_direct_ranking_id(self.config, direct_ranking_id)
                return await self._fetch_rankings_impl(allow_cache_refresh=False)
            logger.warning(
                "Cached ranking resolution failed during list fetch for %s/%s; skipping page resolution fallback under stable-entry policy",
                getattr(self.config, "universe_type", "unknown"),
                getattr(self.config, "universe_key", "unknown"),
            )

        if first_success is not None:
            _clear_failure_classification(self.config)
            _log_qs_acquire_event(
                logger,
                "live_success",
                universe_type=getattr(self.config, "universe_type", ""),
                universe_key=getattr(self.config, "universe_key", ""),
                note="payload_mismatch_or_empty_nodes",
                page=str(getattr(self.config, "page", "")),
            )
            return first_success
        if errors:
            if str(getattr(self.config, "_last_failure_classification", "") or "").strip() == "":
                _set_failure_classification(self.config, "fetch_failed", " | ".join(errors))
            raise RuntimeError(f"Failed to fetch ranking data using all endpoints for nid={nid}: {' | '.join(errors)}")
        return None

    async def fetch_all_details(self, paths: List[str]) -> List[Optional[str]]:
        await self._ensure_session()
        assert self.session is not None
        session = self.session
        error_records: List[Dict[str, Any]] = []
        forbidden_count = 0

        base_url = getattr(self.config, "base_url", "https://www.topuniversities.com")
        # 【技術細節：異步閘門併發控制】
        # 使用 asyncio.Semaphore 嚴格限制最大併發連接數。
        # 這是防止被伺服器 WAF (防火牆) 判定為 DDoS 攻擊並封鎖 IP 的關鍵設計。
        sem = asyncio.Semaphore(self.config.max_concurrent_requests)

        async def _fetch_one(path: str) -> Optional[str]:
            nonlocal forbidden_count
            if not path:
                return None
            url = _abs_url(base_url, path)
            async with sem:
                try:
                    await self._wait_for_delay(url)
                    async with session.get(
                        url,
                        timeout=getattr(self.config, "timeout", 15),
                        ssl=self._ssl_context,
                        headers=self.config.get_headers("detail"),
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.text()
                except Exception as e:
                    status = getattr(e, "status", None)
                    if status is None:
                        msg = str(e).lower()
                        if "403" in msg or "forbidden" in msg:
                            status = 403
                    if status == 403:
                        forbidden_count += 1
                    error_records.append(
                        {
                            "path": path,
                            "url": url,
                            "status": status,
                            "error": str(e),
                        }
                    )
                    logger.warning(f"Failed to fetch details for {url}: {e}")
                    return None

        tasks = [_fetch_one(p) for p in paths]
        result = await asyncio.gather(*tasks)
        setattr(self.config, "_detail_last_errors", error_records)
        existing_forbidden = int(getattr(self.config, "_detail_forbidden_count", 0) or 0)
        setattr(self.config, "_detail_forbidden_count", existing_forbidden + forbidden_count)
        return result

    # crawler.py may call fetch_university_detail in sync mode only, but keep for completeness
    async def fetch_university_detail(self, path: str) -> Optional[str]:
        res = await self.fetch_all_details([path])
        return res[0] if res else None
