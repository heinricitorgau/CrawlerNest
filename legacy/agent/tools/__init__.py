"""
agent.tools subpackage
======================

Structured tool library for the CrawlerNest agent system.

Sub-modules
-----------
query_tools  — user-facing data tools: run_recommender, query_database
dev_tools    — developer tools: file patching, code validation, test runners
registry     — tool discovery / default tool set

Backward compatibility
----------------------
All symbols previously importable from ``agent.tools`` (the flat module)
remain importable from here.  Callers that already do::

    from agent.tools import run_recommender, validate_python_code

continue to work without changes.
"""

from agent.tools.query_tools import query_database, run_recommender
from agent.tools.dev_tools import (
    apply_patch_to_file,
    evaluate_extractor,
    regression_test_python_function,
    resolve_file_path,
    resolve_function_name,
    smoke_test_python_function,
    validate_python_code,
)
from agent.tools.registry import get_default_tools

__all__ = [
    # query tools
    "query_database",
    "run_recommender",
    # dev tools
    "apply_patch_to_file",
    "evaluate_extractor",
    "regression_test_python_function",
    "resolve_file_path",
    "resolve_function_name",
    "smoke_test_python_function",
    "validate_python_code",
    # registry
    "get_default_tools",
]
