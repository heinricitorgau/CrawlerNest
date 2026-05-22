# Maintenance Continuity Model

This document defines the maintenance continuity concepts for CrawlerNest at
RC-1. It specifies what continuity means for each operational dimension,
describes continuity-preserving and continuity-breaking behaviors, and provides
guidance for maintaining operational coherence over time.

---

## Continuity Concept Definitions

### Stable Degraded Continuity

**Definition:** The ability to sustain a known, documented, non-worsening
degraded operational posture without introducing false urgency, attempting
unsolicited remediation, or drifting the communication posture.

**What it means in practice:**
- Freshness will remain critical until a new crawl runs. This is expected.
- THE and ARWU will remain unavailable until source files are acquired.
- The maintenance operator reads the same degraded signals on every run and
  treats them as background context, not new incidents.

**Continuity is preserved when:** The operator reads the signals calmly,
documents the posture accurately, and communicates it honestly to audiences.

**Continuity breaks when:** The operator adjusts thresholds, softens caveats,
artificially inflates confidence, or treats stable background as new incidents.

See `docs/STABLE_DEGRADED_CONTINUITY.md` for the full long-term guidance.

---

### Report Continuity

**Definition:** The ability of generated reports to maintain consistent
semantics, naming, and interpretation across sessions and operators.

**What it means in practice:**
- `reports/freshness_escalation.md` always means the same thing: the current
  freshness state as classified against the escalation policy.
- `reports/maintenance_calm_summary.md` always distinguishes RC-1 stable
  conditions from genuinely new signals.
- Each report's meaning does not change between regenerations.

**Continuity is preserved when:** Scripts regenerate reports with stable
structure, consistent field names, and semantically unchanged classification
logic.

**Continuity breaks when:** A script is modified to change the classification
criteria without updating the consuming documents, or when a report is renamed
without updating all references.

See `docs/REPORT_LIFECYCLE.md` for lifecycle categories per report.

---

### Snapshot Continuity

**Definition:** The ability of named snapshots to serve as reliable historical
evidence without modification, deletion, or reinterpretation.

**What it means in practice:**
- Named snapshots (`system_snapshot_YYYYMMDD_HHMMSS.json`) are written once and
  never overwritten.
- `latest_status.json` is the current-state pointer. It is not historical.
- A snapshot read years from now should produce the same interpretation as when
  it was created.

**Continuity is preserved when:** The append-only principle is respected and
named snapshots are treated as evidence, not current authority.

**Continuity breaks when:** Named snapshots are deleted, overwritten, or used
as the authoritative source of current system state.

See `docs/OPERATIONAL_MEMORY_DURABILITY.md` for durability classification.

---

### Confidence Continuity

**Definition:** The ability of confidence levels and release posture claims to
remain consistent with the observable evidence over time.

**What it means in practice:**
- `operational_trust_summary.md` derives its confidence dimensions from
  observable signals (freshness state, source availability, smoke status).
- Confidence levels should change only when the underlying signals change.
- A "limited" confidence that has been stable for weeks is not a problem to
  resolve — it is the correct reflection of the system posture.

**Continuity is preserved when:** Confidence levels are not adjusted manually
to look better before demos, and the summary accurately reflects the derivation
from observed signals.

**Continuity breaks when:** Confidence dimensions are inflated manually, or
when the summary language is softened to reduce audience discomfort rather than
to reflect a genuine improvement in system state.

---

### Release Honesty Continuity

**Definition:** The ability of the demo/release communication posture to remain
honest over time, even as the posture becomes familiar and the temptation to
soften caveats grows.

**What it means in practice:**
- `demo_caveats.md` defines the required disclosures. These must be stated to
  every audience, not just new audiences.
- "Everyone already knows" is not a valid reason to omit a caveat.
- The release honesty contract is preserved in writing, not in oral tradition.

**Continuity is preserved when:** The operator reads `demo_caveats.md` before
every demo, states the caveats explicitly, and updates the caveat document if
the posture changes.

**Continuity breaks when:** Caveats are omitted, softened, or stated less
precisely than the document requires because the presenter assumes shared
understanding.

See `docs/DEMO_HONESTY_GUIDELINES.md` for required phrasing.

---

### Operational Vocabulary Continuity

**Definition:** The ability of all operators and audiences to interpret
operational terms consistently across time, documents, and contexts.

**What it means in practice:**
- "Stale" means beyond the freshness threshold — it does not mean "broken."
- "Critical" in a freshness context means the data age exceeds the escalation
  threshold — it does not mean the system is failing.
- "Degraded" means below the nominal operational posture — it does not mean
  the system is unusable.

**Continuity is preserved when:** Documents use terms consistently with
`docs/OPERATIONAL_VOCABULARY.md` and do not introduce synonyms or redefinitions.

**Continuity breaks when:** New documents use "stale," "degraded," or "critical"
in senses that diverge from the canonical definitions, or when informal
communication uses these terms loosely.

See `docs/OPERATIONAL_VOCABULARY.md` for canonical definitions.

---

## Continuity-Preserving Behaviors

These behaviors protect operational continuity over time:

1. **Reading the calm summary first.** Starting every maintenance session with
   `maintenance_calm_summary.md` prevents false urgency from stable background
   signals.

2. **Stating caveats before every demo.** Not after being asked. Not only for
   new audiences. The caveat is the honesty contract; contracts are not optional.

3. **Updating classification docs when adding reports.** Every new report must
   be added to `docs/REPORT_CRITICALITY.md`, `docs/REPORT_LIFECYCLE.md`, and
   `docs/reference/MARKDOWN_INDEX.md` in the same commit.

4. **Preserving the readonly boundary.** All maintenance operations read
   existing state. None modify PostgreSQL, application state, or ranking data.

5. **Accepting stable degraded conditions without remediation.** A condition
   that has been present for multiple sessions and is not worsening does not
   require correction. See `docs/MAINTENANCE_DISCIPLINE.md` for the full
   rationale.

6. **Completing the handoff checklist before personnel changes.** The 5-item
   handoff requirement in `docs/OPERATIONAL_MEMORY_PRESERVATION.md` ensures
   the next operator can interpret the system correctly.

7. **Not running all scripts because it seems thorough.** Routine scripts have
   a defined cadence. Running change-triggered scripts without a trigger
   clutters the operational record and produces no information gain.

---

## Continuity-Breaking Behaviors

These behaviors degrade operational continuity over time:

1. **Adjusting thresholds to eliminate stale or critical labels.** The labels
   accurately reflect the system state. Adjusting thresholds to hide them is
   evidence falsification, not improvement.

2. **Softening caveats before demos.** Omitting or weakening required
   disclosures transfers accountability to an undocumented assumption. Future
   audiences may not share the assumed context.

3. **Inflating confidence levels before releases.** A confidence level that
   does not reflect the underlying signal state will mislead future operators
   who inherit the summary without inheriting the context.

4. **Treating every "critical" label as an actionable incident.** RC-1 stable
   degraded conditions produce consistent "critical" labels. Treating these as
   new incidents wastes operator attention and produces no improvement.

5. **Deleting or overwriting named snapshots.** Named snapshots are append-only
   historical evidence. Deleting them removes the ability to reconstruct the
   system state at a specific point in time.

6. **Adding automation during calm periods.** The temptation to improve the
   system when nothing is urgent is highest during calm periods. Additions that
   do not meet the safe-addition criteria in
   `docs/OPERATIONAL_RESTRAINT_GUIDELINES.md` increase future orientation burden.

7. **Neglecting the classification documents when adding reports.** An
   unclassified report is invisible to future operators reading the index. It
   also silently increases the cognitive overhead of the next onboarding session.

---

## Boundary

This document defines continuity concepts and behavioral guidance. It does not
enforce any operational constraint, block any action, or modify any report.
The guidance is based on observed continuity risks in the RC-1 maintenance
system and the patterns documented across Phase 4 through Phase 7.

See also:
- [OPERATIONAL_CONTINUITY_REVIEW.md](OPERATIONAL_CONTINUITY_REVIEW.md) — continuity analysis and risks
- [OPERATIONAL_MEMORY_DURABILITY.md](OPERATIONAL_MEMORY_DURABILITY.md) — artifact durability classification
- [STABLE_DEGRADED_CONTINUITY.md](STABLE_DEGRADED_CONTINUITY.md) — long-term stable degraded guidance
- [MAINTENANCE_DISCIPLINE.md](MAINTENANCE_DISCIPLINE.md) — healthy and unhealthy maintenance patterns
- [DEMO_HONESTY_GUIDELINES.md](DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
