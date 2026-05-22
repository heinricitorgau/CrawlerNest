# Maintenance Discipline

This document defines the behavioral discipline required to maintain CrawlerNest
well over time. It classifies healthy and unhealthy maintenance patterns and
provides concrete guidance for common temptations during calm maintenance periods.

---

## Core Discipline Principles

1. **Observe before acting.** Read the current state completely before deciding
   to change anything.
2. **Distinguish stable background from new signals.** A condition that appeared
   on the last check is context, not a task.
3. **Do not fix what is not broken.** Stable behavior in a known-degraded posture
   does not require correction.
4. **Preserve evidence.** Operational records, snapshots, and caveats are
   historical evidence. Do not delete or overwrite them prematurely.
5. **Disclose honestly.** All known limitations must be communicated in demo and
   release contexts. The caveat document is not optional.

---

## Unhealthy Maintenance Patterns

### 1. Chasing Every Warning

**Pattern:** The operator reads each escalation signal in the maintenance
overview and feels compelled to investigate or act on every one of them,
including signals that have been present and unchanged for multiple sessions.

**Why unhealthy:** Most recurring signals at RC-1 are stable background context
(see `docs/STABLE_DEGRADED_STATE.md`). Investigating them repeatedly provides
no new information and depletes the operator's attention budget.

**Healthy alternative:** Check whether the signal is new. If it appeared on
the previous session unchanged, note it as stable background and continue.
Reserve active investigation for signals that are genuinely new or worsening.

---

### 2. Changing Semantics to Eliminate Stale Labels

**Pattern:** The operator adjusts freshness thresholds, confidence levels, or
escalation criteria to make the "critical" or "stale" labels disappear, because
seeing them on every run feels bad.

**Why unhealthy:** The labels accurately reflect the data state. Adjusting
thresholds to hide accurate labels is a form of evidence falsification. Future
operators reading the modified reports will have an incorrect picture of the
system.

**Healthy alternative:** Accept the labels as accurate. Document them in the
stable degraded state record. Communicate them honestly in demo contexts.
The discomfort of seeing "critical" is the system working correctly.

---

### 3. Suppressing Caveats

**Pattern:** The operator removes or softens caveats from `demo_caveats.md`
because the presentation audience might react negatively, or because "everyone
already knows" about the limitation.

**Why unhealthy:** Caveats are the presenter's honesty contract. Removing them
transfers the accountability for the known limitation from the documented caveat
to an undocumented assumption. If the audience does not know about the
limitation, they deserve to be told.

**Healthy alternative:** State caveats clearly and professionally. Use phrasing
from `docs/DEMO_HONESTY_GUIDELINES.md`. A caveat that is well-framed does not
undermine a demo — it establishes the presenter's credibility.

---

### 4. Artificially Inflating Confidence

**Pattern:** The operator adds positive language to the operational trust
summary ("confidence is actually higher than reported") or adjusts confidence
dimensions upward to make the summary look better before a demo.

**Why unhealthy:** Confidence levels are derived mechanically from observable
signals. Adjusting them disconnects the summary from the evidence. A future
operator reading an inflated summary will make decisions based on false confidence.

**Healthy alternative:** Let the confidence levels reflect the evidence. Present
the known limitations alongside the confidence summary. A "limited" confidence
that is well-explained is more credible than an inflated confidence that is
internally inconsistent.

---

### 5. Adding Overlapping Automation

**Pattern:** During a calm maintenance period, the operator adds new diagnostic
scripts, monitoring tools, or automation because it seems like a good time for
improvement.

**Why unhealthy:** Every new tool adds to the operational surface complexity.
During calm periods, the temptation to improve the system is highest — but the
maintenance surface is already sufficient. New additions require orientation
time from future operators.

**Healthy alternative:** Before adding any new tool, consult
`docs/OPERATIONAL_RESTRAINT_GUIDELINES.md`. If the tool does not meet the safe
addition criteria, backlog it and leave the surface as is.

---

### 6. Rewriting Stable Architecture During Calm Periods

**Pattern:** Because the system is calm and there is no urgent work, the
operator begins refactoring the recommendation engine, rewriting the aggregation
logic, or restructuring the API surface.

**Why unhealthy:** Architecture changes during calm periods introduce risk
without a driving necessity. The RC-1 architecture is frozen intentionally (see
`docs/RC1_FREEZE_SCOPE.md`). Unnecessary changes invalidate operational evidence
and may require re-validation.

**Healthy alternative:** Document architecture improvement ideas as backlog
items. Do not act on them during a calm maintenance period unless there is a
specific, named, agreed requirement for the change.

---

### 7. Running All Scripts Because Nothing Else Is Happening

**Pattern:** The operator runs the full set of build scripts, regenerates all
reports, exports a new snapshot, and re-runs all phase validation scripts
because they are in the repository and it seems thorough.

**Why unhealthy:** Most build scripts are change-triggered, not routine. Running
them when nothing has changed generates identical output to the previous run.
It does not improve the operational record; it clutters it with redundant
timestamps and creates the impression of activity without information gain.

**Healthy alternative:** Follow the cadence defined in
`docs/MAINTENANCE_CADENCE_REVIEW.md`. Run the daily check (`maintenance_overview.sh`
only) unless a specific trigger warrants additional scripts.

---

## Healthy Maintenance Patterns

### 1. Scan for Changes, Not Completeness

On a routine check, look for what is different from the last session.
If nothing is different, maintenance is complete. Do not verify every component
of a stable system for its own sake.

### 2. One Entrypoint, One Read

Start every maintenance session with `maintenance_overview.sh`. Read its output
once. Decide whether any follow-up is needed based on the three key signals
(smoke, aggregated count, new escalation language). Resist the impulse to open
individual report files unless a specific signal warrants it.

### 3. Accept the Posture

The current stable degraded posture at RC-1 is correct and documented. Accepting
it — rather than trying to resolve it — is the right operational stance during
a calm maintenance period. Acceptance means: read the caveats, document the
posture, present it honestly. It does not mean hiding or approving of the
limitations.

### 4. Document Before Acting

Before any operational change, write a one-line note (in a commit message, a
chat log, or a doc comment) explaining why the change is needed and what it
affects. This prevents undocumented mutations that future operators cannot
interpret.

### 5. Prefer Observation Over Modification

When something looks unusual, inspect before modifying. Run
`maintenance_overview.sh`, read the relevant report, and understand the root
cause before changing any file, configuration, or data.

### 6. Let Reports Accumulate Naturally

Do not create snapshots or run report builders on a fixed calendar schedule.
Run them when something meaningful has changed. Natural accumulation produces
an operational record that reflects real state transitions, not clock ticks.

### 7. Communicate Limitations Proactively

When handing off to another operator or presenting to a stakeholder, bring
the limitations to the conversation yourself. Do not wait to be asked. An
operator who surfaces known limitations without prompting demonstrates
operational maturity.

---

## Discipline Under Pressure

When there is pressure to make the system look better before a demo:

- Do not adjust confidence thresholds
- Do not remove caveats
- Do not rerun crawlers without a documented plan for the results
- Do not generate a "fresher" snapshot that overstates the system state

Instead:
- Present `docs/DEMO_HONESTY_GUIDELINES.md` to confirm phrasing
- Read `reports/demo_caveats.md` to ensure the presentation covers all required
  disclosures
- Use the steadiness summary to frame the posture calmly and accurately

A well-framed honest presentation of a limited system is more credible than
a polished presentation of an inflated one.

---

## Boundary

This document defines behavioral guidance. It does not enforce any operational
constraint or block any action. The guidance is based on observed maintenance
anti-patterns in similar systems and the specific posture of CrawlerNest at RC-1.

See also:
- [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md) — when not to add tooling
- [STABLE_DEGRADED_STATE.md](STABLE_DEGRADED_STATE.md) — current known posture
- [MAINTENANCE_CADENCE_REVIEW.md](MAINTENANCE_CADENCE_REVIEW.md) — when to run what
- [DEMO_HONESTY_GUIDELINES.md](DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
