#!/usr/bin/env python3
"""Check that every global name the pipeline's functions reference actually exists.

Written for the run_pipeline.py split. When a function moves to another module,
the calls it leaves behind still parse and the module still imports -- the
failure only appears when that command is finally run, as a NameError from a
code path nobody exercises in CI.

This closes that gap statically: import each module, walk every function, and
check each name it loads against the enclosing scopes, the module namespace and
builtins. It is not a type checker and does not follow attribute access; it
answers one question, which is the one a code move gets wrong.

    ./.venv/bin/python scripts/check_pipeline_names.py

Scope handling is the whole difficulty. A nested function reads names bound by
the function around it, so the check walks the scope chain rather than treating
every function as flat -- otherwise every closure in the file reports as broken
and the output becomes noise nobody reads.

Exit 0 when every name resolves, 1 otherwise.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    ("crawlernest.run_pipeline", REPO_ROOT / "crawlernest" / "run_pipeline.py"),
    ("crawlernest.pipeline.commands.admission",
     REPO_ROOT / "crawlernest" / "pipeline" / "commands" / "admission.py"),
]

FunctionNode = (ast.FunctionDef, ast.AsyncFunctionDef)


def _target_names(target: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def bound_in_scope(node: ast.AST) -> set[str]:
    """Names bound directly in this scope, not descending into nested scopes."""
    names: set[str] = set()

    if isinstance(node, FunctionNode):
        args = node.args
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            names.update(a.arg for a in group)
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
        body = node.body
    elif isinstance(node, ast.Lambda):
        args = node.args
        for group in (args.posonlyargs, args.args, args.kwonlyargs):
            names.update(a.arg for a in group)
        return names
    else:
        body = node.body

    def walk(stmts):
        for stmt in stmts:
            for child in ast.walk(stmt):
                # comprehension and lambda scopes bind their own names, but the
                # bindings are visible to the expressions inside them, so collect
                # them here rather than treating them as separate scopes.
                if isinstance(child, ast.comprehension):
                    names.update(_target_names(child.target))
                elif isinstance(child, ast.Lambda):
                    names.update(bound_in_scope(child))
                elif isinstance(child, FunctionNode) and child is not stmt:
                    names.add(child.name)
                elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                    names.add(child.id)
                elif isinstance(child, (ast.Import, ast.ImportFrom)):
                    for a in child.names:
                        names.add((a.asname or a.name).split(".")[0])
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(child.name)
                elif isinstance(child, ast.ExceptHandler) and child.name:
                    names.add(child.name)
                elif isinstance(child, ast.Global):
                    names.update(child.names)

    walk(body)
    return names


def check_scope(node, visible: set[str], module_name: str, failures: list[str], counter: list[int]):
    """Check one function scope, then recurse into the functions nested in it."""
    counter[0] += 1
    local = bound_in_scope(node)
    here = visible | local

    nested = [n for n in ast.walk(node) if isinstance(n, FunctionNode) and n is not node]
    nested_ids = {id(n) for n in nested}

    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            # names inside a nested function are that function's problem
            if any(child in ast.walk(n) for n in nested if id(n) in nested_ids and child is not n):
                continue
            if child.id not in here:
                failures.append(
                    f"{module_name}.{node.name} (line {child.lineno}): "
                    f"{child.id!r} is not defined in any enclosing scope, the module, or builtins"
                )

    for n in nested:
        # only direct children, deeper ones are handled by their own parent
        if any(n in ast.walk(other) for other in nested if other is not n):
            continue
        check_scope(n, here, module_name, failures, counter)


def main() -> int:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    failures: list[str] = []
    counter = [0]

    for module_name, path in TARGETS:
        if not path.is_file():
            print(f"skip {module_name}: {path} does not exist")
            continue
        module = importlib.import_module(module_name)
        namespace = set(vars(module)) | set(dir(builtins))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, FunctionNode):
                check_scope(node, namespace, module_name, failures, counter)

    print(f"checked {counter[0]} function scopes across {len(TARGETS)} modules")
    if failures:
        print(f"\nFAIL -- {len(failures)} unresolved name(s):")
        for f in sorted(set(failures)):
            print(f"  - {f}")
        print("\nThe usual cause is a function that moved to another module while "
              "its callers kept calling the old bare name.")
        return 1

    print("PASS -- every name referenced by every function resolves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
