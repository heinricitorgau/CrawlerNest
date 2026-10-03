from __future__ import annotations

from pydantic import BaseModel, Field

from agent.memory import Memory
from agent.runner import run_task


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message for the agent.")


class ChatResponse(BaseModel):
    task: str
    response: str
    score: float
    passed: bool
    iterations: int


class ChatHandler:
    """Small shared chat adapter around the core agent runner."""

    def __init__(self) -> None:
        self.memory = Memory()
        self.memory.add("system", "CrawlerNest web-agent session started.")

    def handle(self, request: ChatRequest) -> ChatResponse:
        result = run_task(task_input=request.message, memory=self.memory)
        return ChatResponse(
            task=result.task,
            response=result.output,
            score=result.score,
            passed=result.passed,
            iterations=result.iterations,
        )

