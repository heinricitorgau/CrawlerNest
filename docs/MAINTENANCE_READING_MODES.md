# Maintenance Reading Modes

This document defines structured reading paths for each maintenance context.
Each mode specifies: what to read first, the escalation path, optional deeper
reads, and which reports to skip initially.

Using a mode prevents over-reading on routine checks and ensures thorough
coverage during incidents.

---

## Mode 1: Quick Status Check

**When to use:** Routine daily check, between maintenance sessions, or when
you have 5 minutes and want to confirm nothing changed.

**First report:**

```bash
./scripts/maintenance_overview.sh
```

Scan for three things only:
1. Smoke result line: `Results: N passed, 0 failed` — must match the last session
2. Aggregated count — must match the last session (expected: 1,499)
3. Any NEW escalation language not seen in the last session

**Escalation path:**

- If smoke changed → switch to Mode 5 (Incident Investigation)
- If aggregation count dropped → switch to Mode 4 (Freshness Investigation)
- If nothing new → done

**Optional deeper reads:** None needed if nothing changed.

**Skip initially:**
- `reports/operational_trust_summary.md`
- `reports/drift_timeline.md`
- `reports/maintenance_readiness_summary.md`
- All `docs/` files

---

## Mode 2: Release / Demo Preparation

**When to use:** Before any demo, handoff, or release packaging.

**Reading order:**

1. `reports/maintenance_calm_summary.md` — calm posture overview first
2. `reports/demo_caveats.md` — required reading; confirms what you must state
3. `reports/operational_trust_summary.md` — confidence dimensions and release posture
4. `releases/v0.1-demo/smoke_release_output.txt` — confirm smoke passed
5. `docs/DEMO_HONESTY_GUIDELINES.md` — phrasing compliance check

**Escalation path:**

- If caveats are missing or outdated → run `./scripts/build_demo_caveats.py`
- If smoke shows failures → pause demo prep; switch to Mode 5
- If confidence levels changed since last release → read `reports/freshness_escalation.md`

**Optional deeper reads:**
- `reports/maintenance_readiness_summary.md` — if you need detail behind a caveat
- `reports/operational_summary.md` — if a stakeholder asks about specific source coverage

**Skip initially:**
- `reports/drift_timeline.md`
- `reports/snapshot_timeline.md`
- `reports/operational_index_summary.md`
- Phase maintenance docs

---

## Mode 3: Freshness Investigation

**When to use:** When source freshness state has changed, when a new snapshot
shows different counts, or when planning source recovery.

**Reading order:**

1. `reports/freshness_escalation.md` — escalation state and source-level detail
2. `reports/maintenance_readiness_summary.md` — source coverage breakdown
3. `reports/operational_summary.md` — per-source counts and state
4. `reports/drift_timeline.md` — historical drift context

**Escalation path:**

- If a source that was previously healthy is now stale → Priority 1 per
  `docs/MAINTENANCE_PRIORITY_MATRIX.md`
- If the freshness state matches the last check → note it is a stable known
  limitation; no action needed
- If recovery is planned → read `docs/SOURCE_FRESHNESS_RECOVERY.md`

**Optional deeper reads:**
- `docs/SOURCE_HEALTH_MODEL.md` — freshness state definitions
- `docs/SOURCE_STATE_EXPLAINABILITY.md` — explainability for demo/release contexts

**Skip initially:**
- `reports/operational_trust_summary.md`
- `reports/demo_caveats.md`
- Smoke output

---

## Mode 4: Incident Investigation

**When to use:** Smoke fails, aggregation count drops significantly, auth
breaks, or any signal that was previously healthy becomes degraded.

**Reading order:**

1. `./scripts/maintenance_overview.sh` — immediate readout of all signals
2. `releases/v0.1-demo/smoke_release_output.txt` — specific failure detail
3. `reports/freshness_escalation.md` — check if freshness changed
4. `reports/operational_trust_summary.md` — confidence delta since last check
5. `docs/MAINTENANCE_PRIORITY_MATRIX.md` — triage classification

**Escalation path:**

- Priority 0 (smoke, auth, aggregation corruption): same-day response;
  preserve evidence before acting
- Priority 1 (freshness, source gaps): 1-2 day window; readonly investigation first
- Priority 2 (docs, UX polish): batch for next maintenance window

**Optional deeper reads:**
- `reports/drift_timeline.md` — if count drift is the issue
- `docs/LOCAL_TROUBLESHOOTING.md` — if service startup is the issue
- `docs/OPERATIONAL_RECOVERY.md` — if rollback is needed

**Skip initially:**
- Phase review docs
- `MAINTENANCE_READING_MODES.md` (this doc)
- `docs/README.md`

---

## Mode 5: Long-Term Audit

**When to use:** Before a version bump, at the start of a new development
phase, or when assessing system maturity for a stakeholder review.

**Reading order:**

1. `docs/PROJECT_STATE_REVIEW.md` — overall maturity and next priorities
2. `reports/operational_index_summary.md` — full operational state inventory
3. `reports/operational_trust_summary.md` — current confidence posture
4. `docs/MAINTENANCE_SUSTAINABILITY_REVIEW.md` — maintenance debt analysis
5. `docs/OPERATIONAL_COHERENCE_REVIEW.md` — coherence and cleanup opportunities
6. `reports/drift_timeline.md` — historical trend

**Escalation path:**

- If new technical debt items are identified → log in backlog; do not act in
  the audit session
- If confidence levels have regressed from the previous audit → investigate
  the contributing report

**Optional deeper reads:**
- `docs/RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md` — if bundle cleanup is on the agenda
- `docs/MAINTENANCE_FATIGUE_REVIEW.md` — if operator workflow is being reviewed
- `docs/RC1_FREEZE_SCOPE.md` — if scope changes are being considered

**Skip initially:**
- Individual report files under `reports/`
- Phase validation scripts
- `docs/LOCAL_TROUBLESHOOTING.md`

---

## Mode 6: Onboarding

**When to use:** First day with the project, or returning after a long absence.

**Reading order:**

1. `README.md` — project overview and quick start
2. `docs/README.md` — documentation hub and reading order
3. `docs/ARCHITECTURE_OVERVIEW.md` — system structure
4. `docs/OPERATIONAL_RUNBOOK.md` — startup, smoke, daily ops
5. `reports/maintenance_calm_summary.md` — current state in calm framing
6. `reports/operational_index_summary.md` — operational state inventory
7. `docs/MAINTENANCE_READING_MODES.md` — this document (bookmark for future use)

**After onboarding, use Mode 1 for daily checks.**

**Escalation path:**

- If the system won't start → `docs/LOCAL_TROUBLESHOOTING.md`
- If smoke fails → `docs/MAINTENANCE_PRIORITY_MATRIX.md` for triage
- If data looks wrong → Mode 3 (Freshness Investigation)

**Optional deeper reads:**
- `docs/DATA_FLOW.md` — if you're working on the data pipeline
- `docs/API_SURFACE.md` — if you're working on the API layer
- `docs/AUTH_LIMITATIONS.md` — if you're working on auth

**Skip initially:**
- Phase review docs (Phase 1–5 maintenance docs)
- `docs/REPORT_RELATIONSHIPS.md`
- `docs/SNAPSHOT_LINEAGE.md`

---

## Mode Selection Quick Reference

| Situation | Mode |
| --- | --- |
| Routine 5-minute check | Mode 1: Quick Status |
| About to give a demo | Mode 2: Release/Demo Prep |
| Data freshness question | Mode 3: Freshness Investigation |
| Something broke | Mode 4: Incident Investigation |
| Pre-phase or audit review | Mode 5: Long-Term Audit |
| First time with the project | Mode 6: Onboarding |

---

## Reports Common to All Modes

These reports should be consulted regardless of mode when their content is
explicitly referenced by another report:

- `docs/MAINTENANCE_PRIORITY_MATRIX.md` — triage levels
- `docs/DEMO_HONESTY_GUIDELINES.md` — before any demo
- `docs/SOURCE_FRESHNESS_RECOVERY.md` — if source recovery is needed

---

## Boundary

These reading modes are guidance, not enforcement. They do not change report
content, gate operations, or require tool support. They exist to structure
human decisions and reduce maintenance fatigue.

See also:
- [SIGNAL_TO_NOISE_REVIEW.md](SIGNAL_TO_NOISE_REVIEW.md) — signal value hierarchy
- [MAINTENANCE_FATIGUE_REVIEW.md](MAINTENANCE_FATIGUE_REVIEW.md) — fatigue reduction
- [REPORT_CRITICALITY.md](REPORT_CRITICALITY.md) — criticality reference
