"""
agent.tools.dev_tools
=====================

Tools used exclusively by the *dev agent*.

These tools perform file I/O and code execution and must never be
exposed directly to the web layer.

- resolve_file_path            → map task description → file path
- resolve_function_name        → map task description → function name
- evaluate_extractor           → run extractor quality check
- validate_python_code         → AST syntax check
- apply_patch_to_file          → surgically replace one function in a file
- smoke_test_python_function   → execute function with minimal sample input
- regression_test_python_function → run a fixed set of regression cases
"""

from __future__ import annotations

import ast
import builtins
import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# File / function resolution
# ---------------------------------------------------------------------------

def resolve_file_path(task: str) -> str | None:
    """
    Map a task description to the most likely target file path.
    Returns None when no known file can be inferred.
    """
    task_lower = task.lower()

    if "extractor" in task_lower:
        preferred = Path("crawlernest-extractors/extractor.py")
        if preferred.exists():
            return str(preferred)
        fallback = Path("crawlernest/crawlernest-extractors/extractor.py")
        if fallback.exists():
            return str(fallback)
        return str(preferred)   # return preferred path even if not found

    if "parser" in task_lower:
        path = Path("parser.py")
        return str(path)

    return None


def resolve_function_name(task: str) -> str | None:
    """
    Map a task description to the primary function name to patch or test.
    Returns None when no known function can be inferred.
    """
    task_lower = task.lower()
    if "extractor" in task_lower:
        return "extract"
    if "parser" in task_lower:
        return "build_parser"
    return None


# ---------------------------------------------------------------------------
# Extractor evaluation
# ---------------------------------------------------------------------------

def evaluate_extractor() -> dict[str, Any]:
    """
    Run a quality check on the extractor module.

    Stub implementation — score represents current extractor quality.
    Replace with a real test run when the extractor test suite is wired up.
    """
    return {
        "type": "extractor_eval",
        "score": 0.78,
        "status": "needs improvement",
    }


# ---------------------------------------------------------------------------
# Code validation
# ---------------------------------------------------------------------------

def validate_python_code(code: str) -> dict[str, Any]:
    """
    Parse code with ast.parse and report any SyntaxErrors.
    Does not execute the code.
    """
    try:
        ast.parse(code or "")
    except SyntaxError as exc:
        issue = f"SyntaxError: {exc.msg} at line {exc.lineno}, column {exc.offset}"
        return {
            "type": "code_validation",
            "valid": False,
            "issues": [issue],
            "summary": "Python syntax is invalid.",
        }
    except Exception as exc:
        return {
            "type": "code_validation",
            "valid": False,
            "issues": [f"{exc.__class__.__name__}: {exc}"],
            "summary": "Python syntax is invalid.",
        }

    return {
        "type": "code_validation",
        "valid": True,
        "issues": [],
        "summary": "Python syntax is valid.",
    }


# ---------------------------------------------------------------------------
# Internal execution helpers
# ---------------------------------------------------------------------------

def _sanitize_executable_code(code: str, function_name: str = "") -> str:
    """Strip imports and helper classes that would break sandboxed exec."""
    if function_name == "extract" and "\nclass ScoreValidator:" in code:
        code = code.split("\nclass ScoreValidator:", 1)[0]

    cleaned_lines: list[str] = []
    for line in (code or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("from __future__ import"):
            continue
        if stripped.startswith("import json"):
            continue
        if stripped.startswith("import re"):
            continue
        if stripped.startswith("from typing import"):
            continue
        if stripped.startswith("from models import"):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _build_execution_namespace() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a minimal sandboxed globals + empty namespace for exec."""
    safe_builtins = {
        "__build_class__": builtins.__build_class__,
        "str": str,
        "int": int,
        "float": float,
        "len": len,
        "isinstance": isinstance,
        "dict": dict,
        "list": list,
        "bool": bool,
        "type": type,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "Exception": Exception,
        "any": any,
    }
    globals_dict: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__agent_validation__",
        "json": json,
        "re": re,
        "Any": Any,
    }
    namespace: dict[str, Any] = {}
    return globals_dict, namespace


# ---------------------------------------------------------------------------
# File patching
# ---------------------------------------------------------------------------

def apply_patch_to_file(
    file_path: str,
    new_code: str,
    function_name: str,
) -> dict[str, Any]:
    """
    Surgically replace one named function inside an existing file.

    Uses AST to locate the function boundaries and performs a line-level
    splice.  Aborts and returns changed=False if the patched file would
    have invalid syntax.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": "Target file was not found.",
        }

    try:
        original_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": f"Failed to read target file: {exc}",
        }

    try:
        original_tree = ast.parse(original_text)
        new_tree = ast.parse(new_code or "")
    except SyntaxError as exc:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": f"Patch code is invalid: {exc.msg}",
        }

    original_function = next(
        (
            node
            for node in original_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    replacement_function = next(
        (
            node
            for node in new_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )

    if original_function is None:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": "Target function was not found in the file.",
        }
    if replacement_function is None:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": "Replacement function was not found in the candidate code.",
        }

    original_lines = original_text.splitlines()
    replacement_lines = (new_code or "").splitlines()

    start = original_function.lineno - 1
    end = original_function.end_lineno
    rep_start = replacement_function.lineno - 1
    rep_end = replacement_function.end_lineno

    updated_lines = (
        original_lines[:start]
        + replacement_lines[rep_start:rep_end]
        + original_lines[end:]
    )
    updated_text = "\n".join(updated_lines)
    if original_text.endswith("\n"):
        updated_text += "\n"

    try:
        ast.parse(updated_text)
    except SyntaxError as exc:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": f"Patched file would be invalid: {exc.msg}",
        }

    if updated_text == original_text:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": "Function content was already up to date.",
        }

    try:
        path.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        return {
            "type": "file_patch",
            "file": file_path,
            "function": function_name,
            "changed": False,
            "summary": f"Failed to write patched file: {exc}",
        }

    return {
        "type": "file_patch",
        "file": file_path,
        "function": function_name,
        "changed": True,
        "summary": "Function updated successfully.",
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def smoke_test_python_function(code: str, function_name: str) -> dict[str, Any]:
    """
    Compile and execute code in a sandbox, then call the named function
    with a minimal sample input.  Reports any exceptions.
    """
    globals_dict, namespace = _build_execution_namespace()
    executable_code = _sanitize_executable_code(code, function_name)

    try:
        compiled = compile(executable_code, "<agent-smoke-test>", "exec")
    except SyntaxError as exc:
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": False,
            "executed": False,
            "success": False,
            "issues": [f"SyntaxError: {exc.msg} at line {exc.lineno}, column {exc.offset}"],
            "summary": "Function could not be compiled for smoke testing.",
        }

    try:
        exec(compiled, globals_dict, namespace)  # noqa: S102
    except Exception as exc:
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": False,
            "executed": False,
            "success": False,
            "issues": [f"{exc.__class__.__name__}: {exc}"],
            "summary": "Code execution failed during smoke-test setup.",
        }

    target = namespace.get(function_name)
    if not callable(target):
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": False,
            "executed": False,
            "success": False,
            "issues": [f"Function '{function_name}' was not found."],
            "summary": "Target function is not available for smoke testing.",
        }

    # Minimal sample input per known function
    if function_name in {"build_extractor", "extract"}:
        sample_input: Any = {"title": "Test University", "source": "qs", "rank": "12"}
    elif function_name == "build_parser":
        sample_input = "alpha, beta, gamma"
    else:
        sample_input = {"value": "test"}

    try:
        target(sample_input)
    except Exception as exc:
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": True,
            "executed": True,
            "success": False,
            "issues": [f"{exc.__class__.__name__}: {exc}"],
            "summary": "Function execution failed with sample input.",
        }

    return {
        "type": "smoke_test",
        "function_name": function_name,
        "callable": True,
        "executed": True,
        "success": True,
        "issues": [],
        "summary": "Function executed successfully with sample input.",
    }


# ---------------------------------------------------------------------------
# Regression test
# ---------------------------------------------------------------------------

def regression_test_python_function(code: str, function_name: str) -> dict[str, Any]:
    """
    Run a fixed set of regression cases against the named function.
    Returns pass/fail counts and per-case details.
    """
    globals_dict, namespace = _build_execution_namespace()
    executable_code = _sanitize_executable_code(code, function_name)

    try:
        compiled = compile(executable_code, "<agent-regression-test>", "exec")
    except SyntaxError as exc:
        return _regression_compile_error(function_name, exc)

    try:
        exec(compiled, globals_dict, namespace)  # noqa: S102
    except Exception as exc:
        return _regression_setup_error(function_name, exc)

    target = namespace.get(function_name)
    if not callable(target):
        return _regression_lookup_error(function_name)

    cases = _build_regression_cases(function_name)
    details: list[dict[str, Any]] = []
    passed = 0

    for case_name, sample_input in cases:
        try:
            result = target(sample_input)
            case_passed, summary = _evaluate_regression_result(
                result, function_name, case_name
            )
            details.append({"case": case_name, "success": case_passed, "summary": summary})
            if case_passed:
                passed += 1
        except Exception as exc:
            details.append(
                {
                    "case": case_name,
                    "success": False,
                    "summary": "Function raised an exception during regression testing.",
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            )

    failed = len(cases) - passed
    return {
        "type": "regression_test",
        "function_name": function_name,
        "cases_run": len(cases),
        "passed": passed,
        "failed": failed,
        "details": details,
        "summary": (
            "All regression cases passed."
            if failed == 0
            else f"{failed} regression case(s) failed."
        ),
    }


# ---------------------------------------------------------------------------
# Regression helpers
# ---------------------------------------------------------------------------

def _build_regression_cases(function_name: str) -> list[tuple[str, Any]]:
    if function_name in {"build_extractor", "extract"}:
        return [
            ("normal input", {"title": "Test University", "source": "qs", "rank": "12"}),
            ("missing fields", {"title": "Test University"}),
            ("invalid input", None),
        ]
    if function_name == "build_parser":
        return [
            ("normal input", "alpha, beta, gamma"),
            ("empty input", ""),
            ("invalid input", None),
        ]
    return [
        ("normal input", {"value": "test"}),
        ("empty dict", {}),
        ("invalid input", None),
    ]


def _evaluate_regression_result(
    result: Any,
    function_name: str,
    case_name: str,
) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, f"Unexpected return type: {type(result).__name__}"

    if function_name in {"build_extractor", "extract"}:
        if case_name == "normal input":
            success = isinstance(result, dict)
            if "task_type" in result:
                return success, "Returned dict and preserved task_type."
            if not any(k in result for k in ("title", "rank", "university", "program", "quota")):
                return False, "Returned dict but expected extractor fields were missing."
            return success, "Returned dict with normalized fields."
        return True, f"Handled {case_name} safely."

    if function_name == "build_parser":
        success = "tokens" in result and "count" in result
        return success, (
            "Returned parser dict with token information."
            if success
            else "Returned dict but parser fields were incomplete."
        )

    return True, "Handled regression case without crashing."


def _regression_compile_error(function_name: str, exc: SyntaxError) -> dict[str, Any]:
    return {
        "type": "regression_test",
        "function_name": function_name,
        "cases_run": 0,
        "passed": 0,
        "failed": 1,
        "details": [{"case": "compile", "success": False, "error": str(exc)}],
        "summary": "Regression testing could not start because compilation failed.",
    }


def _regression_setup_error(function_name: str, exc: Exception) -> dict[str, Any]:
    return {
        "type": "regression_test",
        "function_name": function_name,
        "cases_run": 0,
        "passed": 0,
        "failed": 1,
        "details": [{"case": "setup", "success": False, "error": str(exc)}],
        "summary": "Regression testing could not start because setup failed.",
    }


def _regression_lookup_error(function_name: str) -> dict[str, Any]:
    return {
        "type": "regression_test",
        "function_name": function_name,
        "cases_run": 0,
        "passed": 0,
        "failed": 1,
        "details": [
            {
                "case": "lookup",
                "success": False,
                "error": f"Function '{function_name}' was not found.",
            }
        ],
        "summary": "Regression testing could not start because the target function is unavailable.",
    }
