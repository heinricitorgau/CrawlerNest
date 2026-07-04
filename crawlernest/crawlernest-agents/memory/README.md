# CrawlerNest Memory System (Lightweight)

This is a local, markdown-based memory system for CrawlerNest.

## Goals
- Capture real engineering knowledge
- Avoid repeating the same debugging work
- Preserve decisions and trade-offs
- Keep memory human-readable

## Non-Goals
- No vector DB
- No embeddings
- No automation dependency
- No AI-only format

## Rules

1. Only record real, verified information
2. Prefer short, structured entries
3. Always include:
   - context
   - what happened
   - why
   - outcome

## Categories

- known-issues.md → recurring bugs
- current-system-model.md → current agent-side understanding of CrawlerNest modules, data flow, and constraints
- pipeline-pitfalls.md → system-level problems
- extractor-edge-cases.md → data parsing issues
- db-decisions.md → schema & query decisions
- incident-log/ → specific events
- decisions/ → architectural decisions

## Philosophy

Memory is not for AI.

Memory is for:
- future you
- debugging speed
- system stability
