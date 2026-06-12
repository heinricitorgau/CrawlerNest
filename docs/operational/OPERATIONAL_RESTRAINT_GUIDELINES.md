# Operational Restraint Guidelines

This document defines when NOT to add automation, diagnostics, reports,
wrappers, or maintenance scripts to the CrawlerNest operational surface.

It is a first-class maintenance artifact. Review it before adding any new
operational tooling.

---

## Core Principle

Every addition to the operational surface has a carrying cost: cognitive load
for the maintainer who must understand it, runtime risk from any new execution
path, and long-term maintenance debt if it drifts out of sync with the system.

The correct default is: **do not add it.**

Add only when the addition demonstrably reduces ambiguity or reduces operational
risk, and no existing artifact already provides that visibility.

---

## When NOT To Add Automation

Do not add new automation when:

- An existing readonly script already covers the observable state.
- The automation would run without explicit operator invocation (daemon,
  scheduler, background worker).
- The automation would write to PostgreSQL, mutate application runtime state,
  or alter ranking output.
- The automation would trigger secondary automation (cascading remediation).
- The failure mode of the automation is harder to diagnose than the problem it
  solves.
- The automation assumes a stable environment not yet verified for RC-1.

---

## When NOT To Add Diagnostics

Do not add new diagnostic scripts when:

- Existing diagnostics (`check_pipeline_health.py`,
  `inspect_source_freshness.py`, `maintenance_overview.sh`) already answer
  the question.
- The diagnostic mixes readonly observation with any write side-effect.
- The diagnostic would require a live PostgreSQL connection in a readonly
  review context.
- The diagnostic output would overlap with an existing report without
  replacing it.

---

## When NOT To Add Reports

Do not add new generated reports when:

- An existing report under `reports/` already covers the signal class.
- The new report would require a reader to compare it against another report
  to resolve disagreement.
- The report output cannot be explained to a demo presenter in two sentences.
- The report would only be read in the same workflow as an existing report
  that already dominates it.

See [REPORT_CRITICALITY.md](../data/REPORT_CRITICALITY.md) for the current criticality
hierarchy before proposing a new report.

---

## When NOT To Add Wrappers

Do not add new shell or Python wrappers when:

- The wrapped command is already surfaced in `maintenance_overview.sh` or the
  maintenance runbook.
- The wrapper would add a new CLI entrypoint that maintainers must discover
  and remember.
- The wrapper exists only to chain two existing commands that work fine when
  called directly.
- The wrapper introduces hidden semantics (silent retries, auto-fallback, state
  mutations) not visible in the call site.

---

## When NOT To Add Maintenance Scripts

Do not add new maintenance scripts when:

- The operation is already documented as a manual step in
  `MAINTENANCE_RUNBOOK.md` or `OPERATIONAL_RUNBOOK.md`.
- The script would only be run once and has no ongoing maintenance value.
- The script carries assumptions about environment, credentials, or service
  state that are not validated at RC-1.
- Adding the script would increase the total number of scripts in `scripts/`
  beyond what a single maintainer can survey in ten minutes.

---

## Saturation Signals

These signals indicate the operational surface is already saturated and no new
additions should be made without first retiring something:

| Signal | Description |
| --- | --- |
| **Operational saturation** | Maintainer cannot name all current maintenance entry points from memory. |
| **Report duplication** | Two reports answer the same question with potentially different answers. |
| **Signal fragmentation** | No single first-read provides enough context to determine system health. |
| **Maintainer cognitive overload** | First-time operator requires more than 15 minutes to orient to the maintenance surface. |
| **Overlapping confidence layers** | Multiple documents assign different confidence ratings to the same state. |
| **Observability inflation** | New visibility tooling is added faster than old tooling is retired. |

If any saturation signal is present, pause and classify before adding anything.

---

## Safe Addition Criteria

An addition is safe only when it satisfies **all four** of the following:

1. **Reduces ambiguity** — An operator faced with a real question cannot answer
   it using existing artifacts without ambiguity.
2. **Reduces operational risk** — The missing visibility creates a concrete risk
   of a bad demo or release decision.
3. **Does not duplicate existing visibility** — No existing report, script, or
   runbook section already answers the question adequately.
4. **Does not introduce hidden semantics** — The addition has no side effects
   beyond what its name and docstring declare.

If any criterion is not met, do not add the artifact.

---

## Boundary

These guidelines apply at RC-1 and beyond. They are not temporary freeze rules;
they reflect the intended steady-state operational philosophy of CrawlerNest.

See also:
- [OPERATIONAL_BOUNDARY_REINFORCEMENT.md](OPERATIONAL_BOUNDARY_REINFORCEMENT.md)
- [MAINTENANCE_SUSTAINABILITY_REVIEW.md](MAINTENANCE_SUSTAINABILITY_REVIEW.md)
- [REPORT_CRITICALITY.md](../data/REPORT_CRITICALITY.md)
