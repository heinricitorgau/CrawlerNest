"""
web/app.py
==========

FastAPI application — original entry point (kept for backward compatibility).

Previously imported Agent directly.  Now delegates to AgentService so that
the web layer no longer knows about engine internals.

To start the server:
    python web/app.py
    uvicorn web.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.contracts import TaskRequest
from agent.service import create_web_service
from runtime.config import get_config


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    task: str
    result: str
    score: float
    passed: bool
    iterations: int
    mode: str
    error: str | None = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="CrawlerNest Agent Web API", version="0.2.0")
_cfg = get_config()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    service = create_web_service(threshold=_cfg.agent_threshold)
    response = service.run(TaskRequest(prompt=request.message, task_type="web"))
    return ChatResponse(
        task=response.task,
        result=response.result,
        score=response.score,
        passed=response.passed,
        iterations=response.iterations,
        mode=response.mode,
        error=response.error,
    )


if __name__ == "__main__":
    uvicorn.run(
        "web.app:app",
        host=_cfg.web_host,
        port=_cfg.web_port,
        reload=_cfg.web_reload,
    )
