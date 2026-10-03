"""
interfaces/web/app.py
=====================

FastAPI application entry point (new interfaces/ layer).

This file only wires together the framework and the routes.
No business logic lives here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI

from interfaces.api.routes import router
from runtime.config import get_config


app = FastAPI(
    title="CrawlerNest Agent API",
    version="0.2.0",
    description="CrawlerNest web agent — university data, rankings, and recommendations.",
)

app.include_router(router)

if __name__ == "__main__":
    cfg = get_config()
    uvicorn.run(
        "interfaces.web.app:app",
        host=cfg.web_host,
        port=cfg.web_port,
        reload=cfg.web_reload,
    )
