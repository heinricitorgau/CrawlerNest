from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional, List, Union
import json
from pathlib import Path


@dataclass
class Config:

    

    api_url: str = "https://www.topuniversities.com/rankings/endpoint"
    base_url: str = "https://www.topuniversities.com"

    # --------------------------------------------------
    # Data warehouse / crawler metadata
    # --------------------------------------------------
    source_name: str = "QS"
    ranking_year: Optional[int] = None
    enable_database: bool = True
    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_database: str = "clawer"
    pg_user: str = "test"
    pg_password: str = ""
    pg_pool_minconn: int = 1
    pg_pool_maxconn: int = 8
    
                       
    ranking_id: str = "4023722"                                               
    ranking_page_url: Optional[str] = None
    region_name: Optional[str] = None
    universe_type: Optional[str] = None
    universe_key: Optional[str] = None
    country: Union[str, List[str], None] = None
    items_per_page: int = 500
    page: int = 0
    
                           
    # Browser-like UA reduces trivial bot filtering; still identify as automated via CrawlerNest suffix.
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 CrawlerNest/1.0 (+https://github.com/CrawlerNest)"
    )
    timeout: int = 30  # 增加到 30 秒以避免超時
    request_delay: float = 10.0  # 增加延遲以符合 robots.txt 規範 (10秒)
    # Uniform jitter in [-ratio*base, +ratio*base] applied to each inter-request wait (reduces burst patterns).
    request_delay_jitter_ratio: float = 0.2
    max_concurrent_requests: int = 1  # QS robots.txt requires 10s wait, disable concurrency to respect this

    # QS list API: try REST path first vs generic /rankings/endpoint first (both may be tried; order affects success latency).
    qs_endpoint_order: Literal["api_first", "endpoint_first"] = "api_first"
    # Legacy knobs (kept for config file compatibility; ranking fetches use qs_network_retry_* only).
    qs_transient_retry_max_attempts: int = 3
    qs_transient_retry_backoff_seconds: float = 3.0
    qs_transient_retry_max_sleep_seconds: float = 45.0
    # Retries only for transport failures (timeout, connection error) — not for 403/5xx/maintenance.
    qs_network_retry_max_attempts: int = 3
    qs_network_retry_sleep_seconds: List[float] = field(default_factory=lambda: [1.0, 3.0])
    
                         
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    
                          
    output_format: str = "console"                             
    output_file: Optional[str] = None
    export_raw_json: bool = False
    console_width: int = 150
    ranking_limit: int = 100
    sort_ascending: bool = False
    
                   
    use_async: bool = True  # 預設啟用async模式，極速抓取
    local_parse_workers: int = 4  # Local CPU workers for HTML requirement parsing (no network fan-out)
    fetch_details: bool = True  # True: fetch university detail pages for requirements; False: rankings-only mode
    detail_forbidden_streak_threshold: int = 8  # Auto-degrade when consecutive detail 403 reaches this value
    detail_chunk_size: int = 20  # Async detail fetch chunk size for faster degrade reaction
    show_progress: bool = True
    progress_label: str = ""
    enable_cache: bool = True
    cache_ttl: int = 3600          
    resolution_cache_path: Optional[str] = None
    resolution_cache_ttl_seconds: int = 60 * 60 * 24 * 30
    
                              
    master_section_keywords: List[str] = field(default_factory=lambda: [
        "Master", "graduate", "postgraduate", "MS", "MSc", "MA", "MBA"
    ])
    _prefetched_payload: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _subregion_id: str = field(default="", init=False, repr=False)
    _ranking_id_candidates: List[str] = field(default_factory=list, init=False, repr=False)
    _resolved_ranking_page_url: str = field(default="", init=False, repr=False)
    _used_prefetched_payload: bool = field(default=False, init=False, repr=False)
    
    def get_api_params(self) -> Dict[str, str]:

        params = {
            "nid": self.ranking_id,
            "page": str(self.page),
            "items_per_page": str(self.items_per_page),
            "tab": "indicators",
        }
        
        # 處理單個或多個國家代碼
        if self.country is not None:
            if isinstance(self.country, list):
                # 多個國家時用逗號分隔
                params["countries"] = ",".join(self.country)
            else:
                params["countries"] = self.country
        
        return {k: v for k, v in params.items() if v is not None}
    
    def get_headers(self, context: Literal["default", "page", "api", "detail"] = "default") -> Dict[str, str]:
        """
        Browser-like headers for QS. Context separates HTML ranking pages vs JSON API vs detail HTML.
        ``default`` matches legacy behavior (XHR-style JSON requests).
        """
        referer = self.ranking_page_url or self.base_url
        common = {
            "User-Agent": self.user_agent,
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            # Avoid "br" unless brotli is installed — otherwise urllib3 may leave bodies compressed
            # and logs/error strings show binary garbage (e.g. 403 challenge pages).
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if context == "page":
            return {
                **common,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Cache-Control": "max-age=0",
                "Pragma": "no-cache",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Referer": referer,
                "Origin": self.base_url,
            }
        if context == "detail":
            return {
                **common,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Cache-Control": "max-age=0",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Referer": referer,
                "Origin": self.base_url,
            }
        # api + default: XHR / JSON (legacy default)
        return {
            **common,
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": referer,
            "Origin": self.base_url,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Requested-With": "XMLHttpRequest",
        }
    
    @classmethod
    def from_file(cls, config_path: str) -> 'Config':

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def to_file(self, config_path: str):

        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
                                            
        data = {
            k: v for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def update(self, **kwargs):

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Import from constants module and re-export for backward compatibility
from constants import SUBJECT_PRESETS, COUNTRY_CODES

__all__ = ["Config", "SUBJECT_PRESETS", "COUNTRY_CODES"]
