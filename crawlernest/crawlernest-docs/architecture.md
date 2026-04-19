# CrawlerNest Architecture

This file previously carried a longer architecture narrative for the inner workspace.
It is now kept as a **compatibility document** so old links do not point to stale architecture text.

## Canonical Sources

  current executable system
- `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md`
  long-term vision
- `docs/architecture/REPO_STRUCTURE.md`
  actual repo / module structure

## Current Engineering Reality

The active system is intentionally narrower than the long-term platform vision.

### Active now

- ingestion and crawl
- ranking crawler
- limited admission crawler
- shared extractors
- basic normalization
- controlled DB write path
- minimal viable entity resolution
- warehouse-backed API serving
- Java REST API + web frontend

### Controlled / partial

- admission enrichment
- basic rule-based recommendation

### Not part of production data path

- full multi-source aggregation
- full ranking aggregation layer
- agent auto-improvement loop
- autoeval-driven patching
- mini-agent runtime

## Design Reminder

- Agent is not part of production data path.
- Admission crawler is still a controlled pilot.
- Data correctness is more important than automation breadth.
