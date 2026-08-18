from __future__ import annotations

from pathlib import Path


def read_optional_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return "[Warning] Operational heuristics file not found."


def read_limited_text(path: Path, max_chars: int = 6000) -> str:
    if not path.exists():
        return f"[Warning] {path.name} not found."

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]"
    return text


def load_memory_bundle(repo_root: Path) -> str:
    memory_files = [
        repo_root / "memory/known-issues.md",
        repo_root / "memory/pipeline-pitfalls.md",
        repo_root / "memory/extractor-edge-cases.md",
        repo_root / "memory/db-decisions.md",
    ]

    sections = []
    for path in memory_files:
        content = read_limited_text(path)
        sections.append(f"## {path.name}\n{content}")

    return "\n\n".join(sections)
