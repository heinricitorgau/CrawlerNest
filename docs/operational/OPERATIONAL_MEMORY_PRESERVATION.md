# Operational Memory Preservation

This document defines what operational knowledge must be preserved long-term,
what is only temporary operational state, how reports serve as historical
evidence, and what the "known stable degraded state" concept means for memory
and handoff.

---

## Preservation Philosophy

CrawlerNest operational memory serves two purposes:

1. **Evidence preservation** — Record what the system state was at release time,
   so future operators or stakeholders can reconstruct the confidence basis for
   any demo or handoff.

2. **Knowledge preservation** — Record decisions, accepted limitations, and
   posture explanations so a future operator who never attended the original
   work session can understand why the system behaves as it does.

The goal is not to preserve everything indefinitely. It is to preserve the
minimum set of facts that cannot be re-derived from the code or git history,
with enough context to interpret them correctly.

---

## Knowledge That Must Be Preserved Long-Term

These facts cannot be re-derived from code or git history and must persist in
documentation:

| Knowledge Item | Preserved In |
| --- | --- |
| RC-1 scope decisions (what was explicitly excluded) | `docs/RC1_FREEZE_SCOPE.md`, `docs/VERSION_SCOPE_v0.1.md` |
| Accepted limitations at release time | `releases/v0.1-demo/demo_caveats.md` |
| Source availability posture at RC-1 | `docs/STABLE_DEGRADED_STATE.md` |
| Intentional non-implementations | `docs/OPERATIONAL_BOUNDARY_REINFORCEMENT.md` |
| Demo honesty requirements | `docs/DEMO_HONESTY_GUIDELINES.md` |
| Confidence basis for the release claim | `releases/v0.1-demo/operational_trust_summary.md` (bundle copy) |
| Build and runtime validation evidence | `releases/v0.1-demo/smoke_release_output.txt` |
| Snapshot state at release time | `releases/v0.1-demo/system_snapshot_*.json` |

These documents are the institutional memory of the RC-1 release. They answer
the question: "Why did we say it was releasable, and what were the known
limitations?"

---

## Temporary Operational State (Not Long-Term Memory)

These artifacts represent the current operational state. They are regenerated
regularly and are not archival:

| Artifact | Why Temporary |
| --- | --- |
| `reports/maintenance_calm_summary.md` | Regenerated every session; reflects current posture, not history |
| `reports/operational_trust_summary.md` (live) | Regenerated before each release decision |
| `reports/freshness_escalation.md` | Reflects current snapshot; overwritten on each run |
| `reports/demo_caveats.md` (live) | Regenerated before each demo |
| `reports/maintenance_readiness_summary.md` | Overwritten on each inspection |
| `reports/maintenance_steadiness_summary.md` | Regenerated each session |
| `tmp/agent-context/` | Ephemeral AI reasoning context; never authoritative |

Temporary state is useful for current-session decisions. It should not be
treated as archival evidence. The release bundle copies provide the archival
record.

---

## Reports as Historical Evidence

When a report is copied into a release bundle, it becomes historical evidence.
The distinction:

| Report Location | Role |
| --- | --- |
| `reports/*.md` | Current operational state; regenerated regularly |
| `releases/v0.1-demo/*.md` | Historical evidence frozen at bundle-build time |

**Reading rule:** When assessing the current system state, read `reports/`.
When reconstructing the state at the time of a specific release, read the
bundle copy in `releases/v0.1-demo/`.

A bundle copy that shows `release confidence: limited` is not a current problem
— it is historical documentation of the posture at release time.

---

## Bundle Archival Semantics

The `releases/v0.1-demo/` directory is the primary archival record for the v0.1
demo milestone. It was created by `build_demo_bundle.sh` at a specific point in
time and should not be modified after creation.

**Archival properties:**

- Files in the bundle are frozen at the bundle-build timestamp in `MANIFEST.txt`
- The bundle is self-contained: a reader of the bundle does not need the live
  `reports/` directory to understand the release posture
- The bundle captures confidence, caveats, smoke, freshness, and snapshot
  evidence as a coherent point-in-time record
- Future bundles (v0.2, etc.) will create new directories; v0.1 remains unchanged

**What the bundle does NOT capture:**

- Source code changes made after bundle creation
- New snapshots exported after bundle creation
- Report regenerations after bundle creation
- Post-bundle operational events

---

## Snapshot Historical Semantics

Snapshots under `snapshots/` serve as the raw evidence layer. Their semantics:

| File | Semantic |
| --- | --- |
| `snapshots/system_snapshot_YYYYMMDD_HHMMSS.json` | Point-in-time state capture; never modified after creation |
| `snapshots/latest_status.json` | Current-state pointer; overwritten when a new snapshot is taken |

**Append-only principle:** Named snapshots are never deleted or overwritten.
They accumulate as an append-only historical record. `latest_status.json` is
the current pointer, not a historical record.

**Reading named snapshots:** A named snapshot represents what the operator
observed at a specific time. It is evidence, not authority. If it contradicts
the current live state, the live state is correct.

---

## The "Known Stable Degraded State" Concept

A known stable degraded state is an operational posture where:

1. One or more signals show a degraded or critical level
2. The degradation is documented, accepted, and non-worsening
3. The runtime is functioning correctly within the degraded posture
4. No corrective action is pending or expected in the near term

This is distinct from:

- An **active incident**: a new, unexpected, worsening signal requiring immediate response
- A **healthy state**: all signals nominal
- A **hidden degradation**: a degraded state that is not documented or disclosed

CrawlerNest at RC-1 is in a known stable degraded state. This posture is
preserved in documentation and must be communicated honestly in any demo or
handoff context. See `docs/STABLE_DEGRADED_STATE.md` for the specific current
degraded conditions.

**Memory preservation requirement:** When a known stable degraded state exists,
future operators must be able to learn:
- What the degraded conditions are
- That they are accepted and documented (not an emergency)
- What would escalate the situation into an active incident
- Where the evidence of the posture is preserved

All four of these are documented for the RC-1 posture.

---

## Handoff Memory Requirements

When handing off the project to a new operator, the following memory must
be explicitly communicated:

1. **Current operational posture** — Refer to `reports/maintenance_calm_summary.md`
   and `docs/STABLE_DEGRADED_STATE.md`.
2. **Why limitations exist** — Refer to `docs/RC1_FREEZE_SCOPE.md` and
   `docs/OPERATIONAL_BOUNDARY_REINFORCEMENT.md`.
3. **How to maintain the system** — Refer to `docs/MAINTENANCE_CADENCE_REVIEW.md`
   and `docs/MAINTENANCE_READING_MODES.md`.
4. **What the release evidence is** — Refer to `releases/v0.1-demo/` bundle.
5. **What NOT to do** — Refer to `docs/MAINTENANCE_DISCIPLINE.md` and
   `docs/OPERATIONAL_RESTRAINT_GUIDELINES.md`.

A handoff that covers these five areas is operationally complete.

---

## Boundary

This document describes preservation intent and semantics. It does not enforce
retention policies, trigger archival, or modify any artifact. For retention and
cleanup guidance, see `docs/OPERATIONAL_CLEANUP_GUIDE.md`.

See also:
- [STABLE_DEGRADED_STATE.md](../data/STABLE_DEGRADED_STATE.md) — current known degraded posture
- [REPORT_LIFECYCLE.md](../data/REPORT_LIFECYCLE.md) — lifecycle per report
- [OPERATIONAL_CLEANUP_GUIDE.md](OPERATIONAL_CLEANUP_GUIDE.md) — retention policy
