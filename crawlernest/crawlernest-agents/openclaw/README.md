# OpenClaw Integration Skeleton

This directory contains repo-tracked prompt skeletons for running CrawlerNest agents in OpenClaw-style tooling.

Current scope:

- one example persona for `crawlernest-code-reviewer`
- files split into identity, behavior, and selection guidance

Recommended expansion pattern:

```text
openclaw/
└── <agent-name>/
    ├── SOUL.md
    ├── AGENTS.md
    └── IDENTITY.md
```

Notes:

- keep these files aligned with the canonical prompt under `agents/`
- use them as transport wrappers, not as a second source of truth
- if an agent changes materially, update both the canonical agent file and this integration copy
