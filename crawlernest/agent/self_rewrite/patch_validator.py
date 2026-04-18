from __future__ import annotations

import py_compile
from pathlib import Path
from typing import Any


class PatchValidator:
    _FORBIDDEN_PATH_SNIPPETS = (
        "agent/service/agent_service.py",
        "agent/orchestration/",
        "memory_policy.py",
        "agent/autonomous/evaluator.py",
    )

    _ALLOWED_HINT_SNIPPETS = (
        "extractor",
        "parser",
        "formatter",
    )

    _DANGEROUS_HINTS = (
        "delete ",
        "remove ",
        "reset ",
        "drop ",
        "truncate ",
        "os.system",
        "subprocess",
        "rm -",
    )

    def validate(
        self,
        *,
        patch_candidate: dict[str, Any],
        repo_index: dict[str, Any],
        root_dir: str,
    ) -> dict[str, Any]:
        target_file = str(patch_candidate.get("target_file") or "").strip()
        patch_text = str(patch_candidate.get("patch") or "").lower()
        semantic_patch = patch_candidate.get("semantic_patch", {})
        change_count = len(semantic_patch.get("changes", [])) if isinstance(semantic_patch, dict) else 0
        checks: list[dict[str, Any]] = []

        file_exists = any(
            isinstance(item, dict) and item.get("path") == target_file
            for item in repo_index.get("files", [])
        )
        checks.append({"name": "file_exists_in_index", "passed": file_exists})

        forbidden = any(snippet in target_file for snippet in self._FORBIDDEN_PATH_SNIPPETS)
        checks.append({"name": "not_forbidden_target", "passed": not forbidden})

        allowed_scope = False
        if target_file:
            lowered_path = target_file.lower()
            allowed_scope = any(snippet in lowered_path for snippet in self._ALLOWED_HINT_SNIPPETS)
        checks.append({"name": "allowed_scope", "passed": allowed_scope})

        dangerous = any(hint in patch_text for hint in self._DANGEROUS_HINTS)
        checks.append({"name": "no_dangerous_operations", "passed": not dangerous})

        limited_scope = change_count > 0 and change_count <= 4 and patch_candidate.get("scope") in {"function", "file"}
        checks.append({"name": "scope_is_limited", "passed": limited_scope})

        syntax_ok = None
        smoke_ok = None
        resolved_path = Path(root_dir) / target_file if target_file else None
        if resolved_path and resolved_path.suffix == ".py" and resolved_path.exists():
            try:
                py_compile.compile(str(resolved_path), doraise=True)
                syntax_ok = True
            except Exception:
                syntax_ok = False
        checks.append({"name": "python_compile_check", "passed": syntax_ok if syntax_ok is not None else True})

        if file_exists and not forbidden and not dangerous and semantic_patch:
            smoke_ok = True
        checks.append({"name": "basic_smoke_check", "passed": smoke_ok if smoke_ok is not None else False})

        passed_checks = [check for check in checks if bool(check.get("passed"))]
        status = "pass"
        if forbidden or dangerous or not file_exists:
            status = "reject"
        elif len(passed_checks) < len(checks):
            status = "review"

        return {
            "valid": status != "reject",
            "status": status,
            "checks": checks,
            "scope_limited": limited_scope,
            "policy_ok": not forbidden and not dangerous and allowed_scope,
            "syntax_ok": syntax_ok,
            "smoke_ok": smoke_ok,
        }
