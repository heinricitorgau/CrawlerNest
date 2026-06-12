# Operational Intelligence Automation

Operational Intelligence Automation Phase 1 adds readonly report generation on
top of existing snapshots and validation evidence. The goal is to make release
and demo state easier to understand without adding runtime autonomy.

---

## Philosophy

CrawlerNest already records operational evidence through snapshots, smoke
checks, diagnostics, and release reports. Phase 1 turns that evidence into
timeline and escalation summaries:

- What changed across snapshots?
- Is freshness improving or decaying?
- Did source coverage disappear?
- Did unresolved entities trend up or down?
- Is the current state demo-safe, stale, degraded, or critical?

The automation is intentionally conservative. It observes and summarizes; it
does not repair.

---

## Readonly Guarantees

The Phase 1 scripts read from:

- `snapshots/*.json`
- generated reports under `reports/`
- release validation docs under `docs/`

They write only generated report files under `reports/`:

- `snapshot_timeline.md`
- `snapshot_timeline.json`
- `drift_timeline.md`
- `freshness_escalation.md`
- `operational_summary.md`

They do not connect to production services, modify PostgreSQL, rerun crawlers,
change ranking output, update recommendations, or change application runtime
state.

---

## Non-Goals

Phase 1 does not add:

- autonomous engineering
- automatic source retry
- automatic pipeline rerun
- automatic selector repair
- automatic scoring changes
- automatic recommendation mutation
- runtime mutation
- scheduler daemons
- background workers
- autonomous PRs or commits

---

## Observability Boundaries

The reports classify operational signals using existing snapshot fields. Missing
fields are tolerated and defaulted conservatively. Malformed snapshots are
reported as warnings and skipped so one bad file does not block the whole
reporting flow.

This boundary keeps the automation useful during messy handoffs: it can still
summarize partial evidence without pretending that missing evidence is healthy.

---

## Escalation Semantics

Freshness and drift reports use human-readable escalation states:

| State | Meaning |
| --- | --- |
| `healthy` / `info` | No release-blocking operational signal was found. |
| `degraded` / `warning` | The system remains usable, but the state should be explained before a demo or release. |
| `stale` | Data age crossed freshness thresholds; cached data may still serve correctly. |
| `critical` | Evidence suggests missing aggregation, severe source gaps, major count collapse, or very old data. |

Escalation is advisory. It does not trigger remediation.

---

## Why Autonomous Repair Is Avoided

CrawlerNest ranking, recommendation, and diagnostics behavior are frozen for
RC-style release work. Automatic repair would blur the line between observing a
problem and changing the system that produced it. For early-stage release
confidence, preserving evidence is more valuable than hiding instability behind
an automatic rerun or mutation.

Phase 1 therefore improves operator awareness while leaving all corrective
actions explicit, reviewable, and human-directed.
