from __future__ import annotations

import sys
from pathlib import Path

from prompt_utils import load_memory_bundle, read_optional_text


PIPELINE_CONTEXT = "crawler -> extractor -> normalization -> db_writer -> analytics -> recommendation"


def detect_log_signals(content: str) -> list[str]:
    lowered = content.lower()
    signals: list[str] = []

    if "retry" in lowered or "backoff" in lowered:
        signals.append("retry or fallback behavior is present in the log")
    if "checkpoint" in lowered or "resume" in lowered:
        signals.append("checkpoint or resume behavior appears relevant")
    if "deferred" in lowered or "enqueue" in lowered:
        signals.append("deferred processing may be part of the failure path")
    if "error" in lowered or "exception" in lowered or "traceback" in lowered:
        signals.append("hard failure signals appear in the log")
    if "warn" in lowered or "degraded" in lowered or "partial" in lowered:
        signals.append("degradation or partial-success signals appear in the log")

    if not signals:
        signals.append("no obvious operational pattern was detected from keywords alone")

    return signals


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/generate-pipeline-analysis.py <log_path> <output_path>")
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
    signals = detect_log_signals(content)
    signal_lines = "\n".join(f"- {signal}" for signal in signals)

    prompt = f"""# CrawlerNest Pipeline Analysis Prompt

## Role

Use:
1. crawlernest-debug-reliability-engineer
2. crawlernest-data-pipeline-engineer

## Pipeline Context

{PIPELINE_CONTEXT}

Detected signals:
{signal_lines}

## Operational Heuristics

{heuristics}

## Memory Context

{memory}

## Task

Analyze this pipeline log.

## Required Analysis

1. Locate the failure stage.
2. Check whether it matches known heuristics.
3. Decide whether the issue is:
   - extractor issue
   - normalization issue
   - db_writer integrity issue
   - orchestration issue
   - analytics issue
   - recommendation issue
   - upstream source change
4. Suggest minimal next action.
5. Identify whether memory should be updated.

## Pipeline Log

```text
{content}
```
"""

    output_path.write_text(prompt, encoding="utf-8")
    print(f"Wrote pipeline analysis prompt to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
