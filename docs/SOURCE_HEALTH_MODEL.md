# Source Health Model

Defines the source-health vocabulary used by Operational Intelligence
Automation Phase 1. This model is observational only: it classifies signals for
operators and release reviewers, but it does not retry sources, fail over to
alternate providers, rerun pipelines, or mutate ranking data.

---

## Source States

| State | Meaning | Typical Signals |
| --- | --- | --- |
| `healthy` | The source is present, current enough for the release window, and not producing unusual unresolved or drift signals. | Recent snapshot, expected records present, no major unresolved spike, no aggregation gap. |
| `degraded` | The source is usable but has freshness, coverage, or quality warnings that should be called out before a demo. | Moderate age, small unresolved increase, partial source coverage, warning-level drift. |
| `stale` | The source exists but has aged past the freshness threshold. The product may still serve cached data, but operators should not claim freshness. | Stale snapshot age, old latest ingestion, old latest aggregation. |
| `unavailable` | The expected source is missing from the latest snapshot or has zero usable records. | Missing source coverage, HTTP/source fetch failures, no latest ingestion, zero records. |
| `partial` | The source is visible but incomplete relative to the expected release baseline. | Some records present, missing subjects or years, incomplete source coverage, partial aggregation contribution. |

---

## Signals

| Signal | Description | Typical Severity |
| --- | --- | --- |
| HTTP failures | Fetch or crawler access failures recorded by crawler logs or future source snapshots. | `warning` if intermittent, `critical` if persistent and source is unavailable. |
| Missing source | Expected source is absent from `source_counts` or has zero records. | `critical` for baseline sources during release validation. |
| Unresolved spikes | `unresolved_total` or unresolved delta increases compared with earlier snapshots. | `warning` for moderate growth, `critical` for large or sudden spikes. |
| Stale snapshots | Snapshot or aggregation age crosses freshness thresholds. | `stale` or `critical` depending on duration. |
| Aggregation gaps | Aggregated count drops, aggregation status is missing, or latest aggregation is absent. | `warning` for moderate drops, `critical` for collapse or missing aggregation. |

---

## Boundaries

The model intentionally does not perform:

- automatic source failover
- automatic pipeline reruns
- automatic selector repair
- automatic scoring changes
- automatic recommendation mutation
- autonomous commits, PRs, or code edits

Operational intelligence reports should make the state visible and easy to
explain. Human operators decide whether to refresh data, investigate source
changes, or defer a demo claim.
