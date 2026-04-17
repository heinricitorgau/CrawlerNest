"""
runtime/config.py
=================

Centralised configuration for the CrawlerNest system.

All configurable values live here.  Other modules import from this file
instead of using scattered constants or os.environ calls.

Usage
-----
    from runtime.config import Config

    cfg = Config()
    print(cfg.agent_threshold)
    print(cfg.web_host)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """
    Runtime configuration.

    Values are read from environment variables with sensible defaults.
    Override by setting the corresponding env var before launching.

    Environment variables
    ---------------------
    AGENT_THRESHOLD     : float   — minimum score to mark a run as passed (default 0.75)
    AGENT_DEV_THRESHOLD : float   — higher threshold for dev tasks (default 0.85)
    AGENT_MAX_ITER      : int     — max refinement iterations (default 3)
    AGENT_MEMORY_LIMIT  : int     — max memory entries per session (default 20)
    WEB_HOST            : str     — FastAPI bind host (default 127.0.0.1)
    WEB_PORT            : int     — FastAPI bind port (default 8000)
    WEB_RELOAD          : bool    — hot-reload in dev mode (default False)
    LOG_LEVEL           : str     — logging level (default INFO)
    DB_URL              : str     — database connection URL (default empty)
    """

    # Agent tunables
    agent_threshold: float = field(
        default_factory=lambda: float(os.environ.get("AGENT_THRESHOLD", "0.75"))
    )
    agent_dev_threshold: float = field(
        default_factory=lambda: float(os.environ.get("AGENT_DEV_THRESHOLD", "0.85"))
    )
    agent_max_iterations: int = field(
        default_factory=lambda: int(os.environ.get("AGENT_MAX_ITER", "3"))
    )
    agent_memory_limit: int = field(
        default_factory=lambda: int(os.environ.get("AGENT_MEMORY_LIMIT", "20"))
    )

    # Web server
    web_host: str = field(
        default_factory=lambda: os.environ.get("WEB_HOST", "127.0.0.1")
    )
    web_port: int = field(
        default_factory=lambda: int(os.environ.get("WEB_PORT", "8000"))
    )
    web_reload: bool = field(
        default_factory=lambda: os.environ.get("WEB_RELOAD", "").lower() in ("1", "true", "yes")
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO").upper()
    )

    # Database
    db_url: str = field(
        default_factory=lambda: os.environ.get("DB_URL", "")
    )


# ---------------------------------------------------------------------------
# Module-level singleton — import and reuse instead of constructing repeatedly
# ---------------------------------------------------------------------------

_config: Config | None = None


def get_config() -> Config:
    """
    Return the shared Config singleton.
    Constructed on first call; cached for all subsequent calls.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
