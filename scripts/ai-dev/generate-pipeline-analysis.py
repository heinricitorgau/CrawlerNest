from __future__ import annotations

import sys
from pathlib import Path


def detect_signals(content: str) -> list[str]:
    lowered = content.lower()
    signals: list[str] = []

    if "retry" in lowered or "backoff" in lowered:
        signals.append("retry or fallback behavior appears in the log")
    if "checkpoint" in lowered or "resume" in lowered:
        signals.append("checkpoint behavior may be relevant")
    if "deferred" in lowered or "enqueue" in lowered:
        signals.append("deferred enrichment or queueing may be involved")
    if "error" in lowered or "exception" in lowered or "traceback" in lowered:
        signals.append("hard failure signals appear in the log")
    if "warn" in lowered or "degraded" in lowered or "partial" in lowered:
        signals.append("degradation or partial-success signals appear in the log")

    if not signals:
        signals.append("no obvious operational pattern was detected from keywords alone")

    return signals


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/ai-dev/generate-pipeline-analysis.py <log_path> <output_path>")
        return 1

    log_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not log_path.exists():
        print(f"Log file not found: {log_path}")
        return 1

    content = log_path.read_text(encoding="utf-8", errors="replace")
    signal_lines = "\n".join(f"- {item}" for item in detect_signals(content))

    prompt = f"""# CrawlerNest Pipeline Analysis Prompt
Use:
1. `crawlernest-debug-reliability-engineer` for root cause analysis
2. `crawlernest-data-pipeline-engineer` for structural or pipeline improvements

Repository context:
CrawlerNest is a structured data infrastructure system for university intelligence.

Typical flow:
crawler -> extractor -> normalization -> db_writer -> analytics -> recommendation

Task:
Analyze this pipeline log.

Focus on:
- where failure or degradation occurred
- whether fallback behavior triggered correctly
- whether data loss risk exists
- whether checkpoint behavior is coherent
- whether deferred enrichment logic is consistent
- whether the issue is operational or architectural

Constraints:
- ground all claims in the log
- separate observed facts from inferred causes

Detected signals:
{signal_lines}

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
