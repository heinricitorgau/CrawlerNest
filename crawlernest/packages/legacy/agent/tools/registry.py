"""
agent.tools.registry
====================

Tool discovery and default tool-set construction.

get_default_tools() returns the full map of tool name → callable
that the agent engine can dispatch to.

Extending the tool set
----------------------
Add a new tool function to either query_tools or dev_tools, then
register it here.  The engine picks it up automatically on next run.
"""

from __future__ import annotations

from typing import Any, Callable

from agent.tools.dev_tools import (
    apply_patch_to_file,
    evaluate_extractor,
    regression_test_python_function,
    resolve_file_path,
    resolve_function_name,
    smoke_test_python_function,
    validate_python_code,
)
from agent.tools.query_tools import query_database, run_recommender


# ---------------------------------------------------------------------------
# Default tool registry
# ---------------------------------------------------------------------------

def get_default_tools() -> dict[str, Callable[..., Any]]:
    """
    Return the full map of available tools for the agent engine.

    Keys are tool names (used in task routing and logging).
    Values are callables.
    """
    return {
        # --- query tools (web agent) ---
        "query_database": query_database,
        "run_recommender": run_recommender,
        # --- dev tools (dev agent) ---
        "evaluate_extractor": evaluate_extractor,
        "validate_python_code": validate_python_code,
        "apply_patch_to_file": apply_patch_to_file,
        "smoke_test_python_function": smoke_test_python_function,
        "regression_test_python_function": regression_test_python_function,
        "resolve_file_path": resolve_file_path,
        "resolve_function_name": resolve_function_name,
    }


def get_web_tools() -> dict[str, Callable[..., Any]]:
    """Subset of tools safe to use in web-agent mode."""
    return {
        "query_database": query_database,
        "run_recommender": run_recommender,
    }


def get_dev_tools() -> dict[str, Callable[..., Any]]:
    """Full tool set for dev-agent mode."""
    return get_default_tools()
