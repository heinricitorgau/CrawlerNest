# Maintenance Fatigue Review

This document analyzes current maintainer attention hotspots, repeated warning
exposure patterns, cognitive overload risks, and stale-state exposure in the
CrawlerNest operational surface.

It does not suppress warnings or hide state. It identifies where fatigue
accumulates so that workflows can be structured to reduce it.

---

## Definition: Maintenance Fatigue

Maintenance fatigue occurs when an operator:

- Encounters the same escalation signal on every maintenance run without new
  information or available corrective action.
- Must read through multiple reports carrying the same conclusion before
  reaching actionable information.
- Experiences a mismatch between the severity language used and the actual
  urgency of the situation.
- Is required to verify the same pre-conditions repeatedly without a way to
  affirm "this is the same as last time, nothing new."

Fatigue does not indicate system failure. It indicates a workflow gap between
what the monitoring surface communicates and what the operator needs to know.

---

## Maintainer Attention Hotspots

### Hotspot 1: Freshness State Exposure

Every maintenance run surfaces `Freshness state: **critical**` in
`maintenance_readiness_summary.md`, which propagates into the trust summary and
the overview output. Because no new crawl has run since RC-1 packaging, this
state is permanent until an operator explicitly runs a source update.

**Fatigue mechanism:** The operator reads "critical" on every run, cannot
resolve it through maintenance actions (it requires a new crawl, which is a
deliberate human decision), and therefore accumulates unresolvable alarm
exposure.

**Mitigation:** Read `reports/maintenance_calm_summary.md` first, which
contextualizes freshness state against known RC-1 scope before presenting
escalation language.

---

### Hotspot 2: Missing Sources Repeated Exposure

`THE` and `ARWU` are listed as missing in the snapshot, the operational summary,
the freshness escalation, the maintenance readiness summary, and the demo
caveats — five separate documents. An operator doing a pre-demo check encounters
this fact five times in a single session.

**Fatigue mechanism:** Repetition without new information creates the
impression of unresolved problems accumulating rather than a single known
limitation appearing in multiple views.

**Mitigation:** After the first encounter (in `demo_caveats.md`), treat
subsequent appearances as confirmation rather than new warnings. See the
reading modes in `docs/MAINTENANCE_READING_MODES.md` for how to short-circuit
redundant reads.

---

### Hotspot 3: Confidence-Level Framing

`operational_trust_summary.md` reports multiple dimensions as `low`, `limited`,
or `critical`. For an operator maintaining a stable demo environment where these
values have not changed since the last check, the confidence summary reads as
a failing grade on every read.

**Fatigue mechanism:** Evaluative language applied to a stable known-limitation
state creates the impression of continuous underperformance rather than
documented, accepted posture.

**Mitigation:** Read the confidence summary as posture documentation, not
performance evaluation. `limited` confidence on a localhost demo with known
source gaps is the expected posture, not a regression.

---

### Hotspot 4: Phase Validation Script Accumulation

There are now five phase-specific validation scripts
(`validate_maintenance_mode.py` through `validate_maintenance_phase5.py`).
An operator who wants to validate "is everything okay?" must know which scripts
to run, in which order, or whether all of them are needed.

**Fatigue mechanism:** Growing list of required actions without a clear
"only do this" entry point.

**Mitigation:** The definitive validation entry point for ongoing operations
is `maintenance_overview.sh`. Phase validation scripts are milestone evidence,
not recurring checks.

---

## Cognitive Overload Risks

| Risk | Source | Symptom |
| --- | --- | --- |
| Report proliferation | 10 reports in `reports/`, many with overlapping scope | Operator reads wrong report or reads both when one would suffice |
| Docs sprawl | 50+ files in `docs/` | Operator cannot name the relevant doc for their question |
| Escalation saturation | "critical" and "low" appearing in every session | Operator stops distinguishing signal severity |
| Known-state blindness | Repeated exposure to same known limitations | Operator stops reading caveat details |
| Undefined first stop | Multiple reports could be read first | Operator develops inconsistent workflow |

---

## Stale-State Exposure Pattern

The current system has a fixed-state freshness profile:

- QS: stale (354h as of last snapshot)
- THE: unavailable
- ARWU: unavailable

These states will persist on every maintenance run until an explicit source
update is performed. This is not a failure — it is the expected RC-1 posture.

However, every maintenance session generates language like:

> "Freshness state: critical"
> "Missing sources: THE, ARWU"
> "Release confidence: limited"

For an operator maintaining the system between demos, these signals carry no
new information. They document a known stable state that was already documented
the previous session.

The risk is that when a genuinely new problem appears (e.g., smoke starts
failing, aggregation count drops), the operator has been conditioned to dismiss
escalation language as routine noise.

**Guard:** Reserve active response for signals that are NEW. A signal that
appeared on the last maintenance run and is unchanged does not require action.
A signal that is NEW — or a signal that previously showed a healthy state and
now shows degraded — requires response.

---

## Fatigue Reduction Guidance

### 1. Single-Entry Workflow

Use `maintenance_overview.sh` as the single entry point for every maintenance
session. Read its output once. Do not re-read individual reports that the
overview already surfaced unless you have a specific follow-up question.

### 2. Calm Summary First

Read `reports/maintenance_calm_summary.md` before detailed reports. The calm
summary distinguishes known-stable conditions from conditions that require
attention, reducing the alarm load of the detailed reports.

### 3. Caveat Check, Not Caveat Re-Read

Before a demo, check that `reports/demo_caveats.md` exists and was regenerated
in this session. Read it once. Do not re-read every report that contributed to
the caveats.

### 4. Threshold-Based Follow-Up

Only drill into detailed reports when a specific threshold is crossed:

| Condition | Follow-Up |
| --- | --- |
| Smoke output changes | Read `smoke_release_output.txt` carefully |
| Aggregation count changes | Read `reports/operational_summary.md` |
| New source appears or disappears | Read `reports/freshness_escalation.md` |
| Trust summary confidence level changes | Read `reports/operational_trust_summary.md` |
| Nothing changed from last session | No follow-up needed |

### 5. Healthy Operator Workflow

For a routine maintenance session with no new information:

```
./scripts/maintenance_overview.sh
```

Scan the output for:
- "Results: X passed, 0 failed" (smoke) — confirm it matches the last session
- Aggregated count — confirm it matches the last session
- Freshness state — confirm it matches the last session (critical is expected)
- Any NEW warning that did not appear last session

If everything matches the last session: maintenance is complete. The system
is in known stable posture. No further action is needed.

---

## Recommended Escalation Pacing

| Scenario | Escalation Response |
| --- | --- |
| All signals unchanged from last session | Note completion. No action. |
| One signal worsened from last session | Investigate that signal only. Do not re-read all reports. |
| Smoke fails for first time | Priority 0 response per `docs/MAINTENANCE_PRIORITY_MATRIX.md`. |
| NEW source becomes unavailable | Priority 1 response. |
| Aggregation count drops significantly | Priority 1 response. |
| Known limitation persists (freshness, THE, ARWU) | No escalation. Document in demo caveats if presenting. |

---

## Boundary

This document analyzes workflow patterns. It does not change report content,
suppress signals, or alter escalation states. The escalation states in
operational reports remain accurate.

See also:
- [OPERATIONAL_CALMNESS_REVIEW.md](OPERATIONAL_CALMNESS_REVIEW.md) — calmness preservation guidelines
- [MAINTENANCE_READING_MODES.md](MAINTENANCE_READING_MODES.md) — structured reading by context
- [SIGNAL_TO_NOISE_REVIEW.md](../data/SIGNAL_TO_NOISE_REVIEW.md) — signal value classification
