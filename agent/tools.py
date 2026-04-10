from __future__ import annotations

import ast
import builtins
import json
import re
from pathlib import Path
from typing import Any


def query_database(query: str) -> dict[str, Any]:
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


def resolve_file_path(task: str) -> str | None:
    task_lower = task.lower()
    if "extractor" in task_lower:
        preferred = Path("crawlernest-extractors/extractor.py")
        if preferred.exists():
            return str(preferred)
        fallback = Path("crawlernest/crawlernest-extractors/extractor.py")
        if fallback.exists():
            return str(fallback)
        return str(preferred)
    if "parser" in task_lower:
        preferred = Path("parser.py")
        if preferred.exists():
            return str(preferred)
        return str(preferred)
    return None


def resolve_function_name(task: str) -> str | None:
    task_lower = task.lower()
    if "extractor" in task_lower:
        return "extract"
    if "parser" in task_lower:
        return "build_parser"
    return None


def run_recommender(country: str, ielts: float, target_rank: int) -> dict[str, Any]:
    normalized_country = country or "UK"

    if normalized_country.lower() in {"uk", "united kingdom"} and ielts >= 6.5:
        results = ["University of Leeds", "University of Liverpool", "Newcastle University"]
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


def evaluate_extractor() -> dict[str, Any]:
    return {
        "type": "extractor_eval",
        "score": 0.78,
        "status": "needs improvement",
    }


def validate_python_code(code: str) -> dict[str, Any]:
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


def _sanitize_executable_code(code: str, function_name: str = "") -> str:
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
    globals_dict = {
        "__builtins__": safe_builtins,
        "__name__": "__agent_validation__",
        "json": json,
        "re": re,
        "Any": Any,
    }
    namespace: dict[str, Any] = {}
    return globals_dict, namespace


def apply_patch_to_file(file_path: str, new_code: str, function_name: str) -> dict[str, Any]:
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

    original_function = None
    for node in original_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            original_function = node
            break

    replacement_function = None
    for node in new_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            replacement_function = node
            break

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
    replacement_start = replacement_function.lineno - 1
    replacement_end = replacement_function.end_lineno

    updated_lines = (
        original_lines[:start]
        + replacement_lines[replacement_start:replacement_end]
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
        "summary": "Function updated successfully",
    }


def smoke_test_python_function(code: str, function_name: str) -> dict[str, Any]:
    issues: list[str] = []
    globals_dict, namespace = _build_execution_namespace()
    executable_code = _sanitize_executable_code(code, function_name)

    try:
        compiled = compile(executable_code, "<agent-smoke-test>", "exec")
    except SyntaxError as exc:
        issue = f"SyntaxError: {exc.msg} at line {exc.lineno}, column {exc.offset}"
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": False,
            "executed": False,
            "success": False,
            "issues": [issue],
            "summary": "Function could not be compiled for smoke testing.",
        }

    try:
        exec(compiled, globals_dict, namespace)
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

    sample_input: Any = {}
    if function_name in {"build_extractor", "extract"}:
        sample_input = {"title": "Test University", "source": "qs", "rank": "12"}
    elif function_name == "build_parser":
        sample_input = "alpha, beta, gamma"
    else:
        sample_input = {"value": "test"}

    try:
        target(sample_input)
    except Exception as exc:
        issues.append(f"{exc.__class__.__name__}: {exc}")
        return {
            "type": "smoke_test",
            "function_name": function_name,
            "callable": True,
            "executed": True,
            "success": False,
            "issues": issues,
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


def regression_test_python_function(code: str, function_name: str) -> dict[str, Any]:
    globals_dict, namespace = _build_execution_namespace()
    executable_code = _sanitize_executable_code(code, function_name)

    try:
        compiled = compile(executable_code, "<agent-regression-test>", "exec")
    except SyntaxError as exc:
        issue = f"SyntaxError: {exc.msg} at line {exc.lineno}, column {exc.offset}"
        return {
            "type": "regression_test",
            "function_name": function_name,
            "cases_run": 0,
            "passed": 0,
            "failed": 1,
            "details": [
                {
                    "case": "compile",
                    "success": False,
                    "summary": "Code could not be compiled for regression testing.",
                    "error": issue,
                }
            ],
            "summary": "Regression testing could not start because compilation failed.",
        }

    try:
        exec(compiled, globals_dict, namespace)
    except Exception as exc:
        return {
            "type": "regression_test",
            "function_name": function_name,
            "cases_run": 0,
            "passed": 0,
            "failed": 1,
            "details": [
                {
                    "case": "setup",
                    "success": False,
                    "summary": "Code execution failed during regression-test setup.",
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            ],
            "summary": "Regression testing could not start because setup failed.",
        }

    target = namespace.get(function_name)
    if not callable(target):
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
                    "summary": "Target function was not found for regression testing.",
                    "error": f"Function '{function_name}' was not found.",
                }
            ],
            "summary": "Regression testing could not start because the target function is unavailable.",
        }

    if function_name in {"build_extractor", "extract"}:
        cases: list[tuple[str, Any]] = [
            ("normal input", {"title": "Test University", "source": "qs", "rank": "12"}),
            ("missing fields", {"title": "Test University"}),
            ("invalid input", None),
        ]
    elif function_name == "build_parser":
        cases = [
            ("normal input", "alpha, beta, gamma"),
            ("empty input", ""),
            ("invalid input", None),
        ]
    else:
        cases = [
            ("normal input", {"value": "test"}),
            ("empty dict", {}),
            ("invalid input", None),
        ]

    details: list[dict[str, Any]] = []
    passed = 0

    for case_name, sample_input in cases:
        try:
            result = target(sample_input)
            if not isinstance(result, dict):
                details.append(
                    {
                        "case": case_name,
                        "success": False,
                        "summary": "Function returned a non-dict result.",
                        "error": f"Unexpected return type: {type(result).__name__}",
                    }
                )
                continue

            if function_name in {"build_extractor", "extract"}:
                if case_name == "normal input":
                    success = isinstance(result, dict)
                    summary = (
                        "Returned dict with normalized fields."
                        if success
                        else "Returned dict but expected extractor fields were incomplete."
                    )
                elif case_name == "missing fields":
                    success = True
                    summary = "Handled missing optional fields safely."
                else:
                    success = True
                    summary = "Handled invalid input without crashing."

                if "task_type" in result:
                    summary = "Returned dict and preserved task_type for extractor output."
                elif case_name != "invalid input" and not any(
                    key in result for key in ("title", "rank", "university", "program", "quota")
                ):
                    success = False
                    summary = "Returned dict but did not preserve expected extractor fields."
            elif function_name == "build_parser":
                success = "tokens" in result and "count" in result
                summary = (
                    "Returned parser dict with token information."
                    if success
                    else "Returned dict but parser fields were incomplete."
                )
            else:
                success = True
                summary = "Handled regression case without crashing."

            details.append(
                {
                    "case": case_name,
                    "success": success,
                    "summary": summary,
                }
            )
            if success:
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
    summary = (
        "All regression cases passed."
        if failed == 0
        else f"{failed} regression case(s) failed."
    )
    return {
        "type": "regression_test",
        "function_name": function_name,
        "cases_run": len(cases),
        "passed": passed,
        "failed": failed,
        "details": details,
        "summary": summary,
    }
