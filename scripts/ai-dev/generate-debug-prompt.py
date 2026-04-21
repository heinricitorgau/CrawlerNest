from __future__ import annotations

import sys
from pathlib import Path


def classify_issue(content: str) -> list[str]:
    lowered = content.lower()
    classes: list[str] = []

    if "modulenotfounderror" in lowered or "importerror" in lowered:
        classes.append("import/path issue")
    if "ran 0 tests" in lowered or "start directory is not importable" in lowered:
        classes.append("test discovery issue")
    if "permission denied" in lowered or "no such file or directory" in lowered:
        classes.append("config/environment mismatch")
    if "assert" in lowered or "expected" in lowered or " != " in lowered:
        classes.append("output mismatch")
    if any(token in lowered for token in ("keyerror", "valueerror", "typeerror", "attributeerror")):
        classes.append("logic bug")

    if not classes:
        classes.append("unknown from log alone")

    return classes


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/ai-dev/generate-debug-prompt.py <log_path> <output_path>")
        return 1

    log_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 1

    content = log_path.read_text(encoding="utf-8", errors="replace")
    class_lines = "\n".join(f"   - {item}" for item in classify_issue(content))

    prompt = f"""# CrawlerNest Debug Prompt
Use the `crawlernest-debug-reliability-engineer` role.

Repository context:
- Main project: CrawlerNest
- Typical modules:
  - crawlernest-core
  - crawlernest-api
  - crawlernest-analytics
  - crawlernest-autoeval
  - crawlernest-cli
- Common components:
  - extractor
  - db_writer
  - exporter
  - recommendation_engine
- Entry point often includes:
  - run_pipeline.py

Task:
Analyze this failed test run.

Goals:
1. Identify observed behavior
2. Identify likely reproduction path
3. Find root cause
4. Suggest the minimal safe fix
5. Classify the issue type:
{class_lines}

Constraints:
- Do not guess without evidence
- Prefer the smallest grounded explanation first

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
