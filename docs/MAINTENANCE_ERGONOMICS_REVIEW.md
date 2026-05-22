# Maintenance Ergonomics Review

This review looks at operator experience, not product features. It documents
current strengths, pain points, and safe cleanup opportunities.

---

## Current Strengths

- Clear readonly-first reports now exist for freshness, drift, operational
  summary, maintenance readiness, and bundle evidence.
- `maintenance_overview.sh` provides a single command for a human-friendly
  maintenance readout.
- Release bundle artifacts now include operational, maintenance, and caveat
  context.
- Vocabulary, source health, report relationships, and snapshot lineage are
  documented.

---

## Current Pain Points

- There are many generated reports; first-time operators need a clear first
  entrypoint.
- Freshness semantics differ between compact snapshot status and newer reports.
- Some commands are repeated across runbooks, release checklist, and recovery
  docs.
- Snapshot export still requires an explicit PostgreSQL connection and is not
  part of the readonly-only overview.

---

## Common Operator Path

Use this path for maintenance without changing runtime state:

```bash
./scripts/maintenance_overview.sh
./scripts/build_demo_caveats.py
./scripts/build_demo_bundle.sh
```

For deeper freshness review:

```bash
./scripts/inspect_source_freshness.py --summary-output reports/maintenance_readiness_summary.md
./scripts/build_freshness_escalation.py
./scripts/build_drift_timeline.py
```

---

## Safe Future Cleanup Opportunities

- Make `operational_index_summary.md` the documented first report everywhere.
- Consider adding a shared tiny report-reading helper if report parsers keep
  multiplying.
- Clarify compact snapshot freshness fields in a future snapshot exporter pass.
- Keep generated report names stable; avoid adding more top-level summaries
  unless they replace an existing role.

No massive tool rewrite is recommended for Phase 2.
