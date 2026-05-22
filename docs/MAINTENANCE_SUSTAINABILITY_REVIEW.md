# Maintenance Sustainability Review

This document classifies which parts of the current maintenance layer are
sustainable, which are beginning to show complexity, where maintenance debt may
grow, and where future cleanup would be most valuable.

It does not prescribe a rewrite. It classifies, explains, and recommends.

---

## Scope

The review covers:

- Scripts under `scripts/`
- Generated reports under `reports/`
- Documentation under `docs/`
- Release artifacts under `releases/v0.1-demo/`
- The operational validation suite (`validate_maintenance_*.py`)

---

## What Is Sustainable

### Core Readonly Scripts

The following scripts are stable, bounded, and clearly motivated:

| Script | Assessment |
| --- | --- |
| `maintenance_overview.sh` | Single readonly entry point. Well-bounded. Sustainable. |
| `inspect_source_freshness.py` | Focused, readonly. Does one thing. Sustainable. |
| `smoke_release.sh` | Necessary release gate. Stable. Sustainable. |
| `build_demo_bundle.sh` | Assembles static release artifacts. Sustainable. |
| `compare_snapshots.py` | Targeted, readonly diff tool. Sustainable. |
| `export_system_snapshot.py` | Explicit operator-run snapshot. Sustainable. |

### Core Reports

The following reports have stable, non-overlapping roles:

| Report | Assessment |
| --- | --- |
| `reports/demo_caveats.md` | Singular demo-facing caveat source. Sustainable. |
| `reports/freshness_escalation.md` | Authoritative freshness escalation signal. Sustainable. |
| `reports/operational_trust_summary.md` | Confidence rollup. Occupies a unique role. Sustainable. |
| `reports/drift_timeline.md` | Historical drift classification. Sustainable. |

### Operational Documentation

These documents have clear, non-redundant roles:

| Document | Assessment |
| --- | --- |
| `docs/OPERATIONAL_RUNBOOK.md` | The startup/smoke/ops reference. Stable. |
| `docs/SOURCE_FRESHNESS_RECOVERY.md` | Human-action recovery plan. One-of-a-kind. Stable. |
| `docs/MAINTENANCE_PRIORITY_MATRIX.md` | Triage guide. Well-scoped. Stable. |
| `docs/DEMO_HONESTY_GUIDELINES.md` | Demo presenter requirements. Clear scope. Stable. |
| `docs/RC1_FREEZE_SCOPE.md` | Freeze boundaries. Stable for RC-1 lifecycle. |

---

## What Is Starting To Complexify

### Report Proliferation

The `reports/` directory now has ten files. Several overlap in scope:

| Overlap | Risk |
| --- | --- |
| `operational_summary.md` and `operational_index_summary.md` | First-stop ambiguity. A maintainer may read the wrong one. |
| `operational_trust_summary.md` and `maintenance_readiness_summary.md` | Both carry confidence/caveat framing. Divergence is possible over time. |
| Release bundle copies in `releases/v0.1-demo/` | Reports are duplicated outside `reports/`. Bundle copies may become stale. |

### Docs Sprawl

The `docs/` directory contains over 50 Markdown files. Several address adjacent
topics without a clear dominant document:

- Freshness: `SOURCE_HEALTH_MODEL.md`, `FRESHNESS_CONSISTENCY_REVIEW.md`,
  `SOURCE_FRESHNESS_RECOVERY.md`, `SOURCE_COMPLETENESS_REVIEW.md`,
  `SOURCE_STATE_EXPLAINABILITY.md` — five documents share freshness focus.
- Confidence: `OPERATIONAL_CONFIDENCE_MODEL.md`,
  `CONFIDENCE_CONSISTENCY_REVIEW.md`, `OPERATIONAL_TRUST_SUMMARY.md` (report)
  — three surfaces carry confidence language.
- Maintenance: `MAINTENANCE_RUNBOOK.md`, `MAINTENANCE_PRIORITY_MATRIX.md`,
  `MAINTENANCE_ERGONOMICS_REVIEW.md`, `MAINTENANCE_SIGNAL_CLARITY.md`,
  `MAINTENANCE_SUSTAINABILITY_REVIEW.md` (this file) — maintenance framing is
  spread across five documents.

No individual document is wrong. The aggregate surface is beginning to require
orientation before it is useful.

### Validation Script Accumulation

The `scripts/` directory contains four phase-specific validation scripts:

- `validate_maintenance_mode.py`
- `validate_maintenance_phase2.py`
- `validate_maintenance_phase3.py`
- `validate_maintenance_phase4.py`

Each validates a distinct phase milestone. The cumulative suite is not
integrated; a new maintainer must know to run all four (or none). This is a
low-severity issue now, but will compound with additional phases.

### Artifact Discoverability

The `MARKDOWN_INDEX.md` root file is a pointer to `docs/reference/MARKDOWN_INDEX.md`.
The `docs/README.md` is the primary hub, but it now carries a table of over 40
documents with minimal grouping. A maintainer doing a first pass cannot easily
identify which five documents they actually need to read.

---

## Where Maintenance Debt May Grow

| Area | Debt Risk | Why |
| --- | --- | --- |
| Release bundle report copies | Medium | Bundle artifacts in `releases/v0.1-demo/` are point-in-time; they diverge from live `reports/` without notice. |
| Phase validation scripts | Low-Medium | If each maintenance phase adds a new `validate_maintenance_phaseN.py`, the suite becomes hard to survey. |
| Docs freshness docs cluster | Medium | Five freshness-related docs may diverge semantically as source state changes. |
| `operational_index_summary.md` vs `operational_summary.md` | Low | Well-differentiated today, but the distinction may erode if one author reads only one file. |
| Agent context artifacts in `tmp/` | Low | Temporary, but may be confused with authoritative artifacts by future operators. |

---

## Where Future Cleanup Would Be Most Valuable

These are the highest-value cleanup targets when a maintenance window permits.
None are urgent for RC-1.

1. **Consolidate maintenance docs cluster** — Consider a single `MAINTENANCE_HUB.md`
   that links to the five maintenance-themed docs with a one-sentence role
   description for each, so operators know which document answers which question
   without reading all five.

2. **Unified validation runner** — Replace the four phase-specific validation
   scripts with a single `validate_maintenance.py --phase N` or a single
   always-current `validate_current_state.py` that does not carry phase history.

3. **Bundle artifact staleness policy** — Explicitly document that
   `releases/v0.1-demo/*.md` report copies are point-in-time and the live
   source of truth is `reports/`. Add a one-line staleness warning to bundle
   report headers.

4. **Docs README grouping** — Reorganize the `docs/README.md` table into
   semantic groups (Core Ops, Freshness, Confidence, Release, Maintenance) to
   reduce orientation time from ten minutes to two.

5. **Agent context cleanup policy** — Document that `tmp/agent-context/` is
   ephemeral and not authoritative. Include it in the `cleanup_old_artifacts.sh`
   scope.

---

## Operator Workflow Complexity

Current minimal maintenance path (no DB access required):

```bash
./scripts/maintenance_overview.sh
```

Extended path for pre-demo preparation:

```bash
./scripts/build_operational_trust_summary.py
./scripts/build_demo_caveats.py
./scripts/build_demo_bundle.sh
```

Both paths are manageable. The risk is that a future maintainer adds an
intermediate step ("also run X") without documenting where it fits in the
hierarchy, gradually increasing the expected path length.

The restraint guidance in [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md)
is the primary guard against this.

---

## Conclusion

The current maintenance layer is sustainable at RC-1 scale. The most significant
risk is docs sprawl and report proliferation accumulating to a point where
orientation requires dedicated effort. No urgent consolidation is needed. The
five cleanup targets above are worthwhile backlog items.
