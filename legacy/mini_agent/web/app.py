from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from engine import Agent


class ChatRequest(BaseModel):
    message: str


app = FastAPI(title="CrawlerNest Mini Agent")
agent = Agent()


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    result = agent.run(request.message)
    return {"result": result["result"], "score": result["score"]}

