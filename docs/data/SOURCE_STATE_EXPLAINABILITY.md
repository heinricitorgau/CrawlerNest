# Source State Explainability

This guide explains source and freshness states for maintainers, demo
presenters, and reviewers. It is intentionally honest: no hidden fallback
semantics, no fake-healthy interpretation, and no silent substitution of
missing source data.

---

## State Explanations

| State / Signal | Plain Explanation | Expected Maintainer Response | Demo / Release Caveat |
| --- | --- | --- | --- |
| `stale` | Data exists, but the latest evidence is older than the freshness threshold. | Inspect freshness, decide whether a human-approved refresh is needed, preserve caveat if not refreshed. | "This data is present but not fresh." |
| `unavailable` | Expected source has no current usable records in the latest coverage. | Check source pipeline status and source-specific inputs before running ingestion. | "This source is not represented in the current data." |
| `degraded` | System is usable, but freshness, coverage, or quality signals need attention. | Continue readonly inspection, document limitations, avoid broad claims. | "The demo is scoped; some operational caveats apply." |
| `partial` | Some evidence exists, but coverage is incomplete relative to expected release scope. | Identify missing years, subjects, or sources; avoid pretending completeness. | "This area is partially populated." |
| `unresolved spike` | More source records failed canonical matching than expected. | Compare snapshots, inspect resolver inputs, avoid auto-merging. | "Entity matching needs review before claiming full coverage." |
| `missing coverage` | Expected source or subject coverage is absent. | Treat as source gap, not as healthy absence. | "The current view does not include all expected sources." |
| `aggregation freshness` | Age of the latest aggregation output. | If old, refresh only after human approval and re-export snapshots. | "Aggregation output is from a prior run." |
| `subject freshness` | Age and availability of subject ranking records. | Check subject loaders separately from global ranking aggregation. | "Subject ranking completeness is limited." |

---

## Example Scenarios

### QS Present But Stale

Interpretation: QS data is usable for a scoped demo, but freshness claims should
be avoided.

Maintainer response:

1. Run `./scripts/inspect_source_freshness.py`.
2. Review `reports/freshness_escalation.md`.
3. Decide whether to run a human-approved refresh.

Caveat: "QS is present, but the latest aggregation is stale."

### THE And ARWU Unavailable

Interpretation: The current source coverage does not include THE or ARWU. This
must not be hidden by treating QS as a substitute.

Maintainer response:

1. Inspect source pipeline inputs and adapter status.
2. Avoid demo claims about multi-source freshness.
3. Preserve missing-source caveat until a real source refresh lands.

Caveat: "THE and ARWU are unavailable in the current snapshot."

### Aggregation Freshness Critical

Interpretation: The aggregation output is very old or otherwise beyond the
critical threshold. Runtime may still serve data, but release claims must be
scoped.

Maintainer response:

1. Preserve current snapshot evidence.
2. Decide whether to refresh data.
3. Re-run smoke, snapshot export, timeline, freshness, and caveat reports after
   any refresh.

Caveat: "The system is operational, but data freshness is a known limitation."

---

## No Hidden Fallbacks

Do not interpret missing or stale sources as healthy. Do not substitute one
source for another, rewrite ranking output to hide missing coverage, or soften a
critical report without new evidence.
