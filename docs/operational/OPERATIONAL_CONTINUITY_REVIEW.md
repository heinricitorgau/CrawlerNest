# Operational Continuity Review

This document analyzes the CrawlerNest maintenance system for long-term
operational continuity. It identifies which knowledge endures, which drifts,
and which report relationships most require continuity attention.

---

## Continuity Strengths

These aspects of the maintenance system are well-suited for long-term continuity.

### 1. Snapshot-Anchored Historical Evidence

Named snapshots (`snapshots/system_snapshot_YYYYMMDD_HHMMSS.json`) are
append-only and never overwritten. A future operator reading any named snapshot
can reconstruct what the system state was at that moment without relying on
operational memory or institutional recall.

**Why durable:** The evidence is in the file, not in someone's head.

### 2. Bundle-Frozen Release Evidence

The `releases/v0.1-demo/` bundle captures the release posture at bundle-build
time. Future operators can read it to understand the v0.1 confidence basis,
accepted limitations, and communication posture without needing to understand
the current live state.

**Why durable:** The bundle is self-contained and semantically frozen.

### 3. Documented Stable Degraded Posture

`docs/STABLE_DEGRADED_STATE.md` names every RC-1 degraded condition explicitly,
gives the rationale for accepting it, and defines what would escalate it into
an active incident. This prevents future operators from treating known
background conditions as new incidents.

**Why durable:** The conditions are named, categorized, and bounded.

### 4. Single-Entry Maintenance Workflow

`maintenance_overview.sh` is a single-entry orchestration script. A future
operator who knows only this one command can run a complete maintenance check.
All other scripts are reachable from hints in the overview output.

**Why durable:** Low cognitive overhead to enter the maintenance workflow.

### 5. Readonly Boundary Consistency

All maintenance scripts enforce a readonly boundary: no PostgreSQL mutation,
no application state change, no autonomous remediation. This boundary is
consistent across all scripts and documented in every new script's Readonly
Guarantee section.

**Why durable:** The boundary does not require per-script decisions by future
operators — it is a systemic property.

### 6. Operational Vocabulary

`docs/OPERATIONAL_VOCABULARY.md` provides a shared vocabulary for terms like
"stale," "degraded," "critical," "freshness," and "drift." Future operators who
read this document can interpret maintenance reports without needing to learn
by example.

**Why durable:** Vocabulary is decoupled from runtime state.

---

## Continuity Risks

These aspects of the maintenance system are at risk of drifting, degrading, or
becoming misinterpreted over time.

### 1. Report Naming Proliferation

**Risk:** Each maintenance phase adds new report files. Without a naming
discipline or consolidation policy, future operators face an increasing number
of reports with overlapping scope.

**Continuity impact:** New operators will not know which reports to read, which
are current, and which are historical.

**Mitigation:** `docs/REPORT_CRITICALITY.md` and `docs/REPORT_LIFECYCLE.md`
classify all existing reports. These must be updated whenever a new report is
added. See `docs/OPERATIONAL_RESTRAINT_GUIDELINES.md` for the safe-addition
criteria.

### 2. Stale Label Desensitization

**Risk:** Because `freshness_escalation.md` shows "critical" on every run, and
`operational_trust_summary.md` consistently shows "limited," future operators
may stop reading these signals as meaningful.

**Continuity impact:** A genuine new escalation (e.g., aggregation count drop)
may be missed because the operator has habituated to seeing "critical" labels.

**Mitigation:** `docs/MAINTENANCE_DISCIPLINE.md` §2 and `docs/STABLE_DEGRADED_CONTINUITY.md`
address this explicitly. The maintenance overview distinguishes stable
background from new signals via the calm summary step.

### 3. Caveat Drift

**Risk:** Over time, operators presenting demos may soften caveats informally,
stop reading `demo_caveats.md` before demos, or omit caveats because "everyone
already knows." This is an oral-tradition risk — the documented caveats remain
correct, but the practice of stating them degrades.

**Continuity impact:** Audiences receive incorrect confidence in the system.
The "release honesty contract" becomes undocumented assumption.

**Mitigation:** `docs/DEMO_HONESTY_GUIDELINES.md` defines required caveats and
unacceptable phrasing. The maintenance overview and steadiness summary both
include release honesty reminders.

### 4. Bundle Archival Ambiguity

**Risk:** Future operators may not distinguish between live `reports/*.md`
(current state, regenerated) and bundle copies in `releases/v0.1-demo/`
(historical, frozen). Reading a bundle copy as current-state authority leads
to incorrect operational decisions.

**Continuity impact:** Decisions made on stale bundle evidence as if it were
live state.

**Mitigation:** `docs/OPERATIONAL_MEMORY_PRESERVATION.md` defines the archival
vs current distinction. `docs/REPORT_LIFECYCLE.md` classifies every report by
lifecycle category.

### 5. Handoff Knowledge Gap

**Risk:** When the primary maintainer changes, the new operator inherits the
maintenance system without the context of why decisions were made. Git history
captures what changed but not why the posture was accepted, why certain
capabilities were intentionally not implemented, or what constitutes an active
incident vs stable background.

**Continuity impact:** New operators may try to resolve stable degraded
conditions, add automation the system intentionally avoided, or escalate
non-incidents.

**Mitigation:** `docs/OPERATIONAL_MEMORY_PRESERVATION.md` defines the 5-item
handoff memory requirement. All intentional non-implementations are in
`docs/OPERATIONAL_BOUNDARY_REINFORCEMENT.md`.

### 6. Phase Validation Accumulation

**Risk:** Phase validation scripts (`validate_maintenance_phase4.py` through
`validate_maintenance_phase7.py`) are milestone evidence, not recurring checks.
A future operator who runs all of them routinely generates redundant output and
may confuse milestone validation with operational health checks.

**Continuity impact:** Increased maintenance surface confusion.

**Mitigation:** `docs/MAINTENANCE_CADENCE_REVIEW.md` specifies that phase
validation scripts are archival-reference cadence — run once during onboarding,
not routinely.

---

## Vulnerable Operational Assumptions

These assumptions underlie the current maintenance design. If any becomes false,
the maintenance posture requires re-evaluation.

| Assumption | Where Relied On | What Changes If False |
| --- | --- | --- |
| RC-1 posture is stable and non-worsening | All calmness/steadiness reports | Stable degraded posture becomes an active incident |
| ~~QS source is the only live data source~~ — **false since 2026-09-04** | Aggregation count baseline (now 10,125) | Already happened: the baseline moved from 1,499 to 10,125 when THE and ARWU were ingested |
| Smoke passes consistently | Maintenance overview interpretation | Smoke failure triggers Mode 4 investigation |
| No new crawl runs between sessions | Freshness age increases predictably | Freshness state could improve unexpectedly; reports would need regeneration |
| ~~THE and ARWU remain unavailable~~ — **false since 2026-09-04** | Source state classification | Already happened: both are active sources, carrying 1,637 THE and 838 ARWU 2026 ranks |
| Bundle creation is a human-triggered action | Bundle freshness semantics | If automated, bundle loses its "point-in-time release evidence" meaning |

---

## Report Relationships Most Requiring Continuity

These report relationships are the highest-continuity-risk connections in the
maintenance system. A future operator who understands these relationships can
interpret all other reports correctly.

### Core Triangle

```
freshness_escalation.md
    → demo_caveats.md
    → operational_trust_summary.md
```

This triangle is the confidence basis for any release claim. The escalation
feeds the caveats, which feed the trust summary. Misreading any one of them
propagates incorrect confidence upstream.

### Stable Background Chain

```
STABLE_DEGRADED_STATE.md
    → maintenance_calm_summary.md
    → maintenance_steadiness_summary.md
    → maintenance_continuity_summary.md
```

This chain contextualizes the stable degraded posture at increasing levels of
abstraction. The first document defines what is degraded; the last three
operationalize how to present it calmly and consistently.

### Release Evidence Chain

```
smoke_release_output.txt (live)
    → releases/v0.1-demo/smoke_release_output.txt (bundle frozen)
    → releases/v0.1-demo/OPERATIONAL_ARTIFACTS.md (reading guide)
```

The live smoke output is authoritative for current health. The bundle copy is
evidence frozen at release time. The artifacts map explains which is which.

---

## Future Continuity Preservation Guidance

### Add Only When There Is a Named, Agreed Need

Resist adding new reports, scripts, or documents during calm maintenance
periods. The maintenance surface is already sufficient. Every addition creates
a future orientation burden.

### Update Classification Docs with Every New Report

When a new report is added, update `docs/REPORT_CRITICALITY.md`,
`docs/REPORT_LIFECYCLE.md`, and `docs/reference/MARKDOWN_INDEX.md`
in the same commit. Do not let classification drift behind the report count.

### Keep the Handoff Checklist Current

`docs/OPERATIONAL_MEMORY_PRESERVATION.md` defines the 5-item handoff
requirement. Review it before any significant maintainer change and verify
that each item is still current and correct.

### Preserve the Readonly Boundary

No maintenance script should connect to PostgreSQL, modify application state,
or make autonomous operational decisions. This boundary is the primary
continuity guarantee for future operators who inherit the system.

### Accept the Stable Degraded Posture

Do not attempt to "fix" the stable degraded conditions by adjusting thresholds,
regenerating reports to look fresher, or adding automation that mimics
freshness improvement. The posture is correct and documented. See
`docs/STABLE_DEGRADED_CONTINUITY.md` for the long-term guidance.

---

## Boundary

This document analyzes continuity risks and provides guidance. It does not
enforce any operational constraint, block any action, or change any report.
All escalation signals remain visible in their respective reports.

See also:
- [MAINTENANCE_CONTINUITY_MODEL.md](MAINTENANCE_CONTINUITY_MODEL.md) — continuity concept definitions
- [OPERATIONAL_MEMORY_DURABILITY.md](OPERATIONAL_MEMORY_DURABILITY.md) — artifact durability classification
- [STABLE_DEGRADED_CONTINUITY.md](../data/STABLE_DEGRADED_CONTINUITY.md) — long-term stable degraded posture guidance
- [STABLE_DEGRADED_STATE.md](../data/STABLE_DEGRADED_STATE.md) — current RC-1 degraded posture
- [OPERATIONAL_MEMORY_PRESERVATION.md](OPERATIONAL_MEMORY_PRESERVATION.md) — preservation intent and handoff
