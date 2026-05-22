# Operational Cleanup Guide

Cleanup should be deliberate and conservative. CrawlerNest does not use
aggressive auto-pruning or automatic cleanup daemons.

---

## Artifact Retention Expectations

| Artifact Area | Retention Guidance |
| --- | --- |
| `snapshots/` | Keep dated release/handoff snapshots. Cleanup only after confirming no active comparison depends on them. |
| `reports/` | Keep latest generated reports for handoff and demo context. They are reproducible but useful as current evidence. |
| `releases/` | Keep release bundles as historical evidence. Do not delete milestone bundles casually. |
| `tmp/` | Safe to clean when no active agent/debug prompt workflow is using it. |
| `backups/` | Treat as recovery evidence. Follow backup/restore docs before deletion. |

---

## When Cleanup Is Safe

Cleanup is usually safe when:

- reports have been regenerated and copied into the release bundle
- old `tmp/` prompts are no longer needed
- snapshots are not part of an active before/after comparison
- bundle artifacts have been archived or are no longer needed

---

## What Not To Delete

Do not delete:

- the newest `snapshots/latest_status.json`
- the newest dated snapshot used by reports or bundles
- release bundles needed for handoff
- backup/restore drill artifacts without confirming recovery policy
- docs that define operational vocabulary, index, lineage, or runbooks

---

## Snapshot Cleanup

Manual-only guidance:

```bash
find snapshots -maxdepth 1 -type f -name 'system_snapshot_*.json' -print | sort
```

Review before deleting. Prefer keeping snapshots around release boundaries.

---

## Bundle Cleanup

Release bundles under `releases/` are historical. Keep milestone bundles unless
there is a conscious archival decision.

---

## Tmp Cleanup

`tmp/agent-context/`, `tmp/agent-debug/`, and `tmp/agent-analysis/` are
generated context artifacts. They can be removed after the relevant prompt or
debug session is finished.

---

## Reports Cleanup

Reports are generated and can be rebuilt, but keeping the latest report set is
useful for handoff:

- `operational_index_summary.md`
- `maintenance_readiness_summary.md`
- `operational_summary.md`
- `freshness_escalation.md`
- `drift_timeline.md`
- `snapshot_timeline.md`
- `latest_failure_summary.md`

No automatic cleanup daemon should be added for Phase 1.
