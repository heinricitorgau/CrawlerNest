"""
agent.tools.query_tools
=======================

Tools used by the *web agent* to serve end-user requests.

These tools are safe to expose through the web layer:
- query_database   → search university data
- run_recommender  → filter and recommend universities by criteria

No file I/O, no code execution, no patching.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Database query
# ---------------------------------------------------------------------------

def query_database(query: str) -> dict[str, Any]:
    """
    Query the university database and return matching records.

    Currently uses an in-memory stub.
    Replace the body with a real DB call when the database layer is wired up.
    """
    query_lower = query.lower()

    if "uk" in query_lower or "united kingdom" in query_lower:
        results = ["University of Leeds", "University of Leicester", "University of York"]
    elif "parser" in query_lower:
        results = ["parser_config", "parser_rules", "parser_snapshot"]
    else:
        results = ["University A", "University B"]

    return {
        "type": "db_query",
        "query": query,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Recommender
# ---------------------------------------------------------------------------

def run_recommender(
    country: str,
    ielts: float,
    target_rank: int,
) -> dict[str, Any]:
    """
    Return a list of recommended universities filtered by country, IELTS score,
    and target rank.

    Currently uses a rule-based stub.
    Replace the body with a call to core.recommender when that layer is ready.
    """
    normalized_country = country.strip() if country else "UK"

    if normalized_country.lower() in {"uk", "united kingdom"} and ielts >= 6.5:
        results = [
            "University of Leeds",
            "University of Liverpool",
            "Newcastle University",
        ]
    elif ielts >= 6.0:
        results = ["University of Kent", "Oxford Brookes University"]
    else:
        results = ["University A", "University B"]

    return {
        "type": "recommendation",
        "country": normalized_country,
        "ielts": round(ielts, 1),
        "target_rank": int(target_rank),
        "results": results,
    }
