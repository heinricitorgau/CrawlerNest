# Maintenance Priority Matrix

This matrix keeps maintenance triage consistent during the RC and early release
period. It does not change runtime behavior or freeze scope.

---

## Priority Levels

| Priority | Examples | Recommended Response Time | Escalation Guidance |
| --- | --- | --- | --- |
| Priority 0 | Runtime corruption, auth/session breakage, aggregation corruption, source ingestion failure. | Same day; pause demo/release claims until understood. | Stop feature work, preserve evidence, run smoke and targeted tests, involve owner before mutation. |
| Priority 1 | Freshness degradation, source gaps, unresolved spikes, diagnostics inconsistency. | 1-2 working days; document caveats for demos. | Use readonly diagnostics first, export/compare snapshots, decide whether a human-run refresh is needed. |
| Priority 2 | UX polish, docs drift, operational cleanup. | Next maintenance window. | Batch changes, keep scope small, run smoke before handoff. |
| Priority 3 | Experimental automation, future architecture ideas. | Backlog only. | Do not mix with RC maintenance or freshness recovery. |

---

## Freeze Interaction Rules

- Frozen surfaces stay frozen: aggregation formula, recommendation scoring,
  auth/session model, diagnostics semantics, explainability payloads, and saved
  recommendation schema.
- Priority 0 may justify an explicit unfreeze decision, but only after evidence
  is captured and the risk is named.
- Priority 1 should prefer readonly inspection, data refresh planning, and
  documentation before code changes.
- Priority 2 and 3 must not disturb release validation or operational evidence.

---

## Triage Checklist

1. Classify the issue by impact, not by how interesting it is.
2. Capture current evidence: smoke output, snapshot, operational summary.
3. Check whether the change touches a frozen surface.
4. Prefer readonly investigation before mutation.
5. Record accepted limitations if the issue is not fixed before demo/release.
