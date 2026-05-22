# Operational Confidence Model

This model explains confidence labels used in maintenance and release reports.
It is conservative, human-readable, and advisory. It is not hidden scoring logic
and does not trigger automatic release gates or repair actions.

---

## Confidence Dimensions

| Dimension | Meaning |
| --- | --- |
| Freshness confidence | Trust that current data is recent enough for the claim being made. |
| Source completeness confidence | Trust that expected sources are represented. |
| Release confidence | Trust that the system can be released or handed off with honest limitations. |
| Demo confidence | Trust that a demo can be given without misleading the audience. |
| Maintenance confidence | Trust that maintainers have enough evidence and runbooks to act safely. |
| Operational trust level | Conservative overall trust label across the above dimensions. |

---

## Levels

| Level | Meaning | Maintainer Behavior |
| --- | --- | --- |
| `high` | Evidence is current, complete, and validation is clean. | Proceed, keep evidence. |
| `medium` | Evidence is usable with minor caveats. | Proceed with stated limitations. |
| `limited` | Usable only for scoped claims; caveats are required. | State caveats, avoid broad claims. |
| `low` | Major limitations exist. | Treat as maintenance/recovery mode, not full release confidence. |
| `critical` | Severe freshness/source/validation limitation. | Do not claim healthy coverage; preserve evidence and plan recovery. |

---

## Example Scenarios

| Scenario | Likely Confidence |
| --- | --- |
| Fresh QS, THE, ARWU present, smoke passes | high or medium |
| QS present but stale, THE/ARWU unavailable | critical operational trust; limited demo confidence with caveats |
| Smoke passes but freshness is stale | limited release confidence |
| Aggregation collapse or missing snapshot | critical |

---

## Escalation Implications

- `limited`, `low`, and `critical` require explicit demo/release caveats.
- `critical` does not mean runtime is unusable; it means trust claims must be
  narrowed.
- Confidence labels are evidence summaries, not automatic decisions.

---

## Recommended Maintainer Behavior

1. Read `reports/operational_trust_summary.md`.
2. Read `reports/demo_caveats.md` before demos.
3. Use `docs/SOURCE_FRESHNESS_RECOVERY.md` for human-led recovery.
4. Do not inflate confidence without new evidence.
