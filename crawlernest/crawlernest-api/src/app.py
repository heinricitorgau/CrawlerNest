from fastapi import FastAPI
from pydantic import BaseModel
import subprocess
from pathlib import Path

app = FastAPI(title="CrawlerNest API")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_PIPELINE = PROJECT_ROOT / "run_pipeline.py"


class RunPipelineRequest(BaseModel):
    limit: int = 30
    ranking_year: int = 2026
    workers: int = 1
    request_delay: int = 10
    rankings_only: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run-crawler")
def run_crawler(payload: RunPipelineRequest):
    cmd = [
        "python3",
        str(RUN_PIPELINE),
        "run",
        "--limit",
        str(payload.limit),
        "--ranking-year",
        str(payload.ranking_year),
        "--workers",
        str(payload.workers),
        "--request-delay",
        str(payload.request_delay),
    ]

    if payload.rankings_only:
        cmd.append("--rankings-only")

    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )

    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "command": cmd,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }