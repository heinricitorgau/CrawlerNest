# Source Freshness Recovery

Current operational state:

- `QS`: stale
- `THE`: unavailable
- `ARWU`: unavailable

This plan prepares safe human-led recovery. It does not add automatic source
failover, hidden fallback ranking mutation, or silent data substitution.

---

## Probable Causes

| Source | Current Signal | Probable Causes |
| --- | --- | --- |
| QS | Present but stale. | Pipeline has not been refreshed, source fetch not rerun, or snapshot is old. |
| THE | Missing from source coverage. | Source adapter not run, source unavailable, no current fixture/data load, or ingestion failed before warehouse write. |
| ARWU | Missing from source coverage. | Adapter support exists but source data may not be loaded, source unavailable, or ingestion not scheduled. |

---

## Safe Investigation Sequence

1. Inspect current evidence:

```bash
./scripts/inspect_source_freshness.py
```

2. Review timeline and drift:

```bash
./scripts/build_snapshot_timeline.py
./scripts/build_drift_timeline.py
./scripts/build_freshness_escalation.py
```

3. Confirm live readonly health:

```bash
CRAWLERNEST_PG_PASSWORD=test ./.venv/bin/python scripts/check_pipeline_health.py
```

4. Inspect pipeline docs and source-specific scripts before running ingestion.
5. If a refresh is approved, run the documented pipeline command manually.
6. Export a new snapshot after the refresh.
7. Compare before/after snapshots.

---

## Non-Destructive Recovery Steps

Readonly or file-output-only:

```bash
./scripts/inspect_source_freshness.py --summary-output reports/maintenance_readiness_summary.md
./.venv/bin/python scripts/export_system_snapshot.py --pg-host 127.0.0.1 --pg-user test --pg-password test --pg-database clawer
./scripts/build_snapshot_timeline.py
./scripts/build_freshness_escalation.py
./scripts/build_operational_summary.py
./scripts/build_operational_index_summary.py
```

Human-approved data refresh only:

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

Only run ingestion after confirming the intended source behavior and expected
data impact.

---

## Fallback Assumptions

- If QS is stale but present, demos may use it only with a stale-data caveat.
- If THE/ARWU are unavailable, do not claim multi-source freshness.
- Do not substitute QS records as THE/ARWU evidence.
- Do not mutate ranking output to hide missing source coverage.

---

## Validation Expectations

After any approved refresh:

```bash
./scripts/smoke_release.sh
./scripts/inspect_source_freshness.py
./scripts/build_snapshot_timeline.py
./scripts/build_drift_timeline.py
./scripts/build_freshness_escalation.py
./scripts/build_operational_summary.py
./scripts/build_operational_index_summary.py
```

Expected evidence:

- latest aggregation age decreases
- source coverage changes are visible
- unresolved count does not spike unexpectedly
- drift timeline explains any source/count movement
- release/demo caveats are updated

---

## Rollback Expectations

This repository does not define automatic data rollback. If a refresh produces
bad data:

1. Preserve before/after snapshots.
2. Stop further ingestion.
3. Use `compare_snapshots.py` to identify the change.
4. Restore database state only through the documented backup/restore process.
5. Rebuild reports and bundle after recovery.
