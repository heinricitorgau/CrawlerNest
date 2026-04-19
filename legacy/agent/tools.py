"""
agent/tools.py  — backward compatibility shim
==============================================

All symbols previously defined in this flat module are now organised
under the ``agent/tools/`` subpackage:

    agent.tools.query_tools  → query_database, run_recommender
    agent.tools.dev_tools    → file patching, code validation, test runners
    agent.tools.registry     → get_default_tools

This file re-exports everything so that existing code that does::

    from agent.tools import run_recommender, validate_python_code

continues to work without changes.

New code should import directly from the submodules.
"""

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
from agent.tools.registry import get_default_tools

__all__ = [
    "apply_patch_to_file",
    "evaluate_extractor",
    "get_default_tools",
    "query_database",
    "regression_test_python_function",
    "resolve_file_path",
    "resolve_function_name",
    "run_recommender",
    "smoke_test_python_function",
    "validate_python_code",
]
