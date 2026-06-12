# Stable Degraded Continuity

This document defines how to maintain a stable degraded operational posture
over an extended period. It addresses the specific risks that emerge when a
known degraded state persists for weeks or months: false urgency, warning
desensitization, confidence inflation, and remediation churn.

---

## The Challenge of Long-Duration Degraded Postures

A stable degraded posture is correct, documented, and non-worsening. But
maintaining it well over time is harder than it appears. Two opposite failure
modes emerge:

**Failure mode 1 — False urgency:** The operator sees "freshness: critical" on
every run and treats it as a new alarm requiring investigation. This consumes
attention on stable background context and produces no improvement.

**Failure mode 2 — Desensitization:** The operator sees "freshness: critical"
on every run and stops reading it as meaningful. When a genuine new failure
appears among the familiar "critical" labels, it is missed.

This document defines how to navigate between these failure modes and sustain
a calm, accurate maintenance posture indefinitely.

---

## Healthy Long-Term Maintenance Patterns

### 1. Check for Change, Not Presence

The correct maintenance question is not "Is freshness critical?" but "Has the
freshness state changed since the last session?"

At RC-1, freshness is always critical. Reading it as a current-session alarm
is incorrect. Reading it as a change signal is correct. If the freshness state
has not changed, it is background context.

**How to apply:**
Compare the current maintenance overview output to the previous session's
output. If the signals are the same, maintenance is complete. Do not
investigate stable signals.

### 2. Use the Calm Summary as the First Read

`reports/maintenance_calm_summary.md` explicitly separates:
- RC-1 known stable conditions (background, expected, not actionable)
- New signals (genuinely outside the known stable posture)

Starting every session with the calm summary prevents false urgency from
stable background signals and ensures that genuinely new signals are visible.

### 3. State Caveats Consistently, Not Selectively

Over time, the temptation grows to omit caveats for audiences who have "heard
it before" or who "obviously know about the freshness issue." This is incorrect.

Every audience receives the same caveats. Oral tradition is not a substitute
for the documented disclosure. Read `reports/demo_caveats.md` before every
demo, regardless of how familiar the audience seems.

### 4. Treat Increasing Age as Expected, Not Alarming

At RC-1, QS data age increases with every daily check because no new crawl
runs. A data age of 360 hours is not more alarming than 354 hours — it is the
expected result of the elapsed time since the last crawl.

Do not treat an increasing data age as a worsening signal unless it approaches
a threshold that was not previously expected. The RC-1 posture accepts stale
data as a documented condition.

### 5. Document Handoffs Proactively

Before any operator change, explicitly communicate the stable degraded posture.
Do not assume the new operator will infer it from reading reports. Walk through
`docs/STABLE_DEGRADED_STATE.md` and explain:
- Why the conditions are accepted (not emergency)
- What would escalate them into an active incident
- What the expected daily maintenance check looks like

---

## Unhealthy Long-Term Maintenance Patterns

### 1. Freshness Alarm Spiral

**Pattern:** The operator runs `inspect_source_freshness.py`, reads the
escalating data age, generates a new `freshness_escalation.md`, reads
"critical," generates a new `operational_trust_summary.md`, reads "limited,"
and concludes the session by documenting concern about freshness.

**Why unhealthy:** Every step in this spiral produces output that was already
known. The investigation produces no new information and creates the impression
of active maintenance without any actual change to the system state.

**Healthy alternative:** Daily check = `maintenance_overview.sh` only. If the
calm summary shows no new signals, maintenance is complete. The freshness state
is background.

### 2. Confidence Adjustment Before Demos

**Pattern:** Before a demo, the operator reads that operational trust is
"limited" and decides to adjust the phrasing in the summary, or re-run the
trust builder with different parameters to produce a more favorable result.

**Why unhealthy:** The confidence level reflects the evidence. Adjusting it
disconnects the summary from its evidence base. Future operators reading the
modified summary will make decisions based on false confidence.

**Healthy alternative:** Present the "limited" confidence honestly. Use phrasing
from `docs/DEMO_HONESTY_GUIDELINES.md`. A "limited" confidence that is well-
explained is more credible than an inflated confidence.

### 3. Remediation Theater

**Pattern:** Because freshness is critical and source availability is
incomplete, the operator repeatedly investigates whether the data could be
refreshed, documents plans for running new crawlers, schedules theoretical
crawler runs, and prepares "remediation notes" — but takes no actual action
because the sources are not available.

**Why unhealthy:** Remediation theater consumes operator attention, produces
documentation overhead, and creates a false sense of progress. The stable
degraded posture has not changed. Documenting the intention to fix it is not
the same as accepting it.

**Healthy alternative:** Accept the posture. Document it once in
`docs/STABLE_DEGRADED_STATE.md`. Refer to it when asked. Move on.

### 4. Warning Desensitization Through Normalization

**Pattern:** The operator begins mentally filtering out all "critical" labels
because they appear on every run. Eventually, a new "critical" signal (e.g.,
aggregated count drops unexpectedly) is missed because it appears alongside the
familiar background "critical" labels.

**Why unhealthy:** Desensitization to labels is the inverse of false urgency,
but equally dangerous. The maintenance system depends on the operator being
able to detect new signals among familiar background.

**Healthy alternative:** The calm summary explicitly lists "No New Signals" or
"Signals Requiring Attention." Read the calm summary, not the raw report labels.
The calm summary does the signal-vs-background discrimination for you.

### 5. Documentation Churn Without State Change

**Pattern:** Because nothing has changed, the operator generates new reports,
exports a fresh snapshot, updates the steadiness summary, and commits the
result — creating the appearance of active maintenance without any actual
operational event having occurred.

**Why unhealthy:** This produces redundant timestamps in the git history,
consumes operator time, and makes it harder to find meaningful operational
events in the commit log. A commit that regenerates reports without any signal
change is noise.

**Healthy alternative:** Run `maintenance_overview.sh`. If the output is the
same as the previous session, commit nothing. The absence of new commits during
a stable period is correct and expected.

---

## Posture Acceptance vs Posture Approval

Accepting the stable degraded posture does not mean approving of it.

**Acceptance** means:
- Reading the caveats and understanding them
- Communicating them honestly to audiences
- Not attempting to resolve them without a specific, agreed action

**Approval** would mean:
- Declaring the posture ideal or desirable
- Removing the caveats because the posture is "fine"
- Adjusting confidence levels to hide the known limitations

The maintenance system is designed for acceptance, not approval. The caveats
remain. The "limited" confidence remains. The "critical" freshness label
remains. These are correct reflections of the system state. Accepting them
maintains operational continuity; approving or suppressing them breaks it.

---

## When the Posture Changes

The stable degraded posture described in `docs/STABLE_DEGRADED_STATE.md` will
change when:

- A new QS crawl is run and data is refreshed
- THE or ARWU source files are acquired and ingested
- Subject ranking data is loaded

When any of these changes occur:
1. Run `export_system_snapshot.py` to capture the new state
2. Run `build_drift_timeline.py` to classify the change
3. Regenerate all summaries
4. Update `docs/STABLE_DEGRADED_STATE.md` to reflect the new posture
5. Update `reports/demo_caveats.md` if any caveat is resolved

Until those actions are taken, the current posture is correct and the long-term
maintenance discipline described in this document applies.

---

## Boundary

This document provides behavioral guidance for long-duration stable degraded
posture maintenance. It does not suppress any signal, change any threshold, or
modify any report.

See also:
- [STABLE_DEGRADED_STATE.md](STABLE_DEGRADED_STATE.md) — current RC-1 degraded conditions
- [MAINTENANCE_DISCIPLINE.md](../operational/MAINTENANCE_DISCIPLINE.md) — general healthy/unhealthy patterns
- [MAINTENANCE_CONTINUITY_MODEL.md](../operational/MAINTENANCE_CONTINUITY_MODEL.md) — stable degraded continuity definition
- [DEMO_HONESTY_GUIDELINES.md](../demo/DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
- [MAINTENANCE_CADENCE_REVIEW.md](../operational/MAINTENANCE_CADENCE_REVIEW.md) — when to run what
