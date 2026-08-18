from __future__ import annotations

import sys
from pathlib import Path

from prompt_utils import load_memory_bundle, read_optional_text


REPOSITORY_CONTEXT = """CrawlerNest is a structured data infrastructure system for university intelligence.
Core pipeline: crawler -> extractor -> normalization -> db_writer -> analytics -> recommendation.
Current state: evolving MVP; data correctness and operational evidence matter more than architecture elegance."""


def summarize_failure_kind(content: str) -> list[str]:
    lowered = content.lower()
    hints: list[str] = []

    if "modulenotfounderror" in lowered or "importerror" in lowered:
        hints.append("import/path issue")
    if "ran 0 tests" in lowered or "start directory is not importable" in lowered:
        hints.append("test discovery issue")
    if "assert" in lowered or "!=" in lowered or "expected" in lowered:
        hints.append("data/output mismatch")
    if "keyerror" in lowered or "valueerror" in lowered or "typeerror" in lowered:
        hints.append("logic bug")
    if "permission denied" in lowered or "no such file or directory" in lowered:
        hints.append("environment/config mismatch")

    if not hints:
        hints.append("unknown from log alone")

    return hints


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/generate-debug-prompt.py <log_path> <output_path>")
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    log_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 1

    content = log_path.read_text(encoding="utf-8", errors="replace")
    heuristics = read_optional_text(repo_root / "docs/OPERATIONAL_HEURISTICS.md")
    memory = load_memory_bundle(repo_root)
    hints = summarize_failure_kind(content)
    hint_lines = "\n".join(f"- {hint}" for hint in hints)

    prompt = f"""# CrawlerNest Debug Prompt

## Role

Use crawlernest-debug-reliability-engineer.

## Repository Context

{REPOSITORY_CONTEXT}

Detected failure hints:
{hint_lines}

## Operational Heuristics

{heuristics}

## Memory Context

{memory}

## Task

Analyze this failed test run.

## Required Reasoning Order

1. Check whether the failure matches any operational heuristic.
2. Identify the most likely failure stage.
3. Explain evidence from the log.
4. Suggest the smallest safe next step.
5. Say what should NOT be debugged first.

## Constraints

- Do not guess without citing evidence from the log
- Prefer the smallest grounded explanation first
- Do not auto-fix code

## Test Output

```text
{content}
```
"""

    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote debug prompt to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
