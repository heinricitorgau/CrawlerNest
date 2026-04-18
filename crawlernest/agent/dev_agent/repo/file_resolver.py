from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class FileResolver:
    def resolve(
        self,
        *,
        user_input: str,
        context: dict[str, Any],
        repo_index: dict[str, Any],
    ) -> dict[str, Any]:
        explicit_file = self._extract_explicit_file(context)
        explicit_symbol = self._extract_explicit_symbol(context, user_input)
        files = repo_index.get("files", []) if isinstance(repo_index, dict) else []

        if explicit_file:
            matched = self._find_file_by_path(files, explicit_file)
            return {
                "file_path": matched["path"] if matched else explicit_file,
                "symbol": explicit_symbol,
                "confidence": "high" if matched else "medium",
                "reason": "Matched explicit file path from request context."
                if matched
                else "Used explicit file path from request context.",
            }

        if explicit_symbol:
            symbol_match = self._find_best_symbol_match(files, explicit_symbol, user_input)
            if symbol_match:
                return {
                    "file_path": symbol_match["path"],
                    "symbol": explicit_symbol,
                    "confidence": "high",
                    "reason": "Matched function name in repo index.",
                }

        file_match = self._find_best_file_match(files, user_input)
        if file_match:
            inferred_symbol = explicit_symbol or self._infer_primary_symbol(
                file_entry=file_match,
                user_input=user_input,
            )
            reason = (
                "Matched file hint from task wording."
                if explicit_symbol is None
                else "Matched file by task wording after symbol lookup fallback."
            )
            return {
                "file_path": file_match["path"],
                "symbol": inferred_symbol,
                "confidence": "medium" if inferred_symbol is None else "high",
                "reason": (
                    reason if inferred_symbol is None else f"{reason} Inferred primary symbol from repo index."
                ),
            }

        return {
            "file_path": None,
            "symbol": explicit_symbol,
            "confidence": "low",
            "reason": "No reliable file match found in the repo index.",
        }

    def _extract_explicit_file(self, context: dict[str, Any]) -> str | None:
        for key in ("file_path", "target_file", "path"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        target = context.get("target")
        if isinstance(target, str) and target.strip().endswith((".py", ".ts", ".tsx", ".c")):
            return target.strip()
        return None

    def _extract_explicit_symbol(self, context: dict[str, Any], user_input: str) -> str | None:
        for key in ("symbol", "target_symbol"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        symbol_patterns = [
            r"\b([A-Za-z_][A-Za-z0-9_]*)\b",
        ]
        if re.search(r"(improve|fix|refactor|update|modify)", user_input, re.IGNORECASE):
            for pattern in symbol_patterns:
                matches = re.findall(pattern, user_input)
                for candidate in matches:
                    if "_" in candidate or candidate[:1].islower() or candidate[:1].isupper():
                        if candidate.lower() not in {"improve", "fix", "refactor", "update", "modify", "extractor", "failure", "handling"}:
                            return candidate
        return None

    def _find_file_by_path(self, files: list[dict[str, Any]], path_hint: str) -> dict[str, Any] | None:
        normalized = Path(path_hint).as_posix().lower()
        for file_entry in files:
            path = str(file_entry.get("path", "")).lower()
            if path == normalized or path.endswith(normalized):
                return file_entry
        return None

    def _find_best_symbol_match(
        self,
        files: list[dict[str, Any]],
        symbol: str,
        user_input: str,
    ) -> dict[str, Any] | None:
        lowered_input = user_input.lower()
        candidates: list[tuple[int, dict[str, Any]]] = []
        for file_entry in files:
            score = 0
            path = str(file_entry.get("path", ""))
            for item in file_entry.get("symbols", []):
                if str(item.get("name")) == symbol:
                    score += 6
            if "web_agent_engine" in path and "_apply_generation" in lowered_input:
                score += 3
            if "extractor" in lowered_input and "extractor" in path.lower():
                score += 2
            if score > 0:
                candidates.append((score, file_entry))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], len(str(item[1].get("path", "")))))
        return candidates[0][1]

    def _infer_primary_symbol(
        self,
        *,
        file_entry: dict[str, Any],
        user_input: str,
    ) -> str | None:
        lowered_input = user_input.lower()
        symbols = file_entry.get("symbols", [])
        names = [str(item.get("name")) for item in symbols if item.get("name")]

        if "extractor" in lowered_input:
            for preferred in ("extract", "run_extractor", "extract_fields"):
                if preferred in names:
                    return preferred

        if len(names) == 1:
            return names[0]
        return None

    def _find_best_file_match(
        self,
        files: list[dict[str, Any]],
        user_input: str,
    ) -> dict[str, Any] | None:
        lowered_input = user_input.lower()
        candidates: list[tuple[int, dict[str, Any]]] = []
        for file_entry in files:
            path = str(file_entry.get("path", ""))
            lowered_path = path.lower()
            score = 0

            stem = Path(path).stem.lower()
            if stem and stem in lowered_input:
                score += 4
            if "extractor" in lowered_input and "extractor.py" in lowered_path:
                score += 5
            if "web_agent_engine" in lowered_input and "web_agent_engine.py" in lowered_path:
                score += 5
            if "_apply_generation" in lowered_input and "web_agent_engine.py" in lowered_path:
                score += 4
            if "parser" in lowered_input and "parser" in lowered_path:
                score += 3
            if "validation" in lowered_input and "validation" in lowered_path:
                score += 2

            if score > 0:
                candidates.append((score, file_entry))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], len(str(item[1].get("path", "")))))
        return candidates[0][1]
