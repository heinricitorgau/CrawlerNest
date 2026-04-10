from __future__ import annotations

from typing import Any


def evaluate_extractor() -> dict[str, Any]:
    return {"score": 0.8, "notes": "Mock extractor evaluation returned stable structure."}


def query_database() -> dict[str, Any]:
    return {"data": [], "notes": "Mock database returned no rows."}


TOOLS = {
    "evaluate_extractor": evaluate_extractor,
    "query_database": query_database,
}

