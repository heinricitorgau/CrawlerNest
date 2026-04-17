"""
interfaces/api/routes.py
========================

Clean FastAPI router definition.

This module owns nothing but route handlers.  It imports AgentService
and the shared Config, and converts HTTP ↔ TaskRequest / TaskResponse.

Mount this router in interfaces/web/app.py with::

    from interfaces.api.routes import router
    app.include_router(router)
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agent.contracts import TaskRequest
from agent.service import create_web_service
from runtime.config import get_config


router = APIRouter()
_cfg = get_config()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message for the agent.")


class ChatResponse(BaseModel):
    task: str
    result: str
    score: float
    passed: bool
    iterations: int
    mode: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Main agent endpoint.

    Accepts a user message, runs it through AgentService, and returns
    the structured response.  A new service instance is created per
    request here; replace with a session-scoped service when session
    management is added.
    """
    service = create_web_service(threshold=_cfg.agent_threshold)
    task_request = TaskRequest(
        prompt=request.message,
        task_type="web",
    )
    response = service.run(task_request)
    return ChatResponse(
        task=response.task,
        result=response.result,
        score=response.score,
        passed=response.passed,
        iterations=response.iterations,
        mode=response.mode,
        error=response.error,
    )
