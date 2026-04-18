from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class RepoIndexer:
    _cached_index: dict[str, Any] | None = None

    _SUPPORTED_SUFFIXES = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
        ".c": "c",
        ".h": "c",
    }
    _SKIP_DIRS = {
        ".git",
        ".next",
        "node_modules",
        "dist",
        "build",
        "target",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
    }

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parents[3]

    def build_index(self) -> dict[str, Any]:
        if RepoIndexer._cached_index is not None:
            return RepoIndexer._cached_index

        files: list[dict[str, Any]] = []
        for path in self._root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in self._SKIP_DIRS for part in path.parts):
                continue
            language = self._SUPPORTED_SUFFIXES.get(path.suffix.lower())
            if not language:
                continue

            relative = path.relative_to(self._root).as_posix()
            symbols = self._extract_symbols(path, language)
            files.append(
                {
                    "path": relative,
                    "language": language,
                    "symbols": symbols,
                }
            )

        RepoIndexer._cached_index = {"files": files}
        return RepoIndexer._cached_index

    def _extract_symbols(
        self,
        path: Path,
        language: str,
    ) -> list[dict[str, str]]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        symbols: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        patterns: list[tuple[str, str]]
        if language == "python":
            patterns = [
                (r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
                (r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)", "function"),
            ]
        else:
            patterns = [
                (r"^\s*(?:export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", "class"),
                (
                    r"^\s*(?:export\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)",
                    "function",
                ),
                (
                    r"^\s*(?:export\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(",
                    "function",
                ),
            ]

        for pattern, symbol_type in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1)
                key = (name, symbol_type)
                if key in seen:
                    continue
                seen.add(key)
                symbols.append({"name": name, "type": symbol_type})

        return symbols
