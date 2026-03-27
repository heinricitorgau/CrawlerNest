from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Union
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
    
                           
    user_agent: str = "CrawlerNestBot/1.0 (+https://github.com/CrawlerNest/UniGraph-University-Knowledge-Graph-Engine)"
    timeout: int = 30  # 增加到 30 秒以避免超時
    request_delay: float = 10.0  # 增加延遲以符合 robots.txt 規範 (10秒)
    max_concurrent_requests: int = 1  # QS robots.txt requires 10s wait, disable concurrency to respect this
    
                         
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
    
    def get_headers(self) -> Dict[str, str]:

        return {
            "User-Agent": self.user_agent
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
