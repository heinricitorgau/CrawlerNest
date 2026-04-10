from __future__ import annotations

import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.engine import Agent
print("USING MAIN AGENT ENGINE")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    task: str
    steps: list[dict[str, object]]
    mode: str
    file_resolution: dict[str, object]
    patch_execution: dict[str, object]
    generated: str
    initial_score: float
    initial_reason: str
    refined: str
    final_score: float
    final_reason: str
    improved: bool
    iterations: int
    improvement_history: list[dict[str, float]]
    final_result: str


app = FastAPI(title="CrawlerNest Agent Web API", version="0.1.0")
agent = Agent()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict[str, object]:
    return agent.run(request.message)


if __name__ == "__main__":
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=False)
