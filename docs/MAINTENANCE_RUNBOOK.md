# Maintenance Runbook

Copy-paste friendly commands for conservative CrawlerNest maintenance. Start
with readonly checks unless a human has explicitly approved a data refresh.

---

## Inspect Operational State

```bash
./scripts/maintenance_overview.sh
./scripts/inspect_source_freshness.py
./scripts/build_operational_index_summary.py
sed -n '1,160p' reports/operational_index_summary.md
```

---

## Verify Freshness

```bash
./scripts/inspect_source_freshness.py --summary-output reports/maintenance_readiness_summary.md
./scripts/build_freshness_escalation.py
sed -n '1,160p' reports/freshness_escalation.md
```

---

## Inspect Drift

```bash
./scripts/build_snapshot_timeline.py
./scripts/build_drift_timeline.py
sed -n '1,160p' reports/drift_timeline.md
```

---

## Inspect Unresolved Spikes

```bash
./scripts/build_snapshot_timeline.py
rg -n "Unresolved|unresolved|trend" reports/snapshot_timeline.md
```

---

## Export Snapshots

```bash
./.venv/bin/python scripts/export_system_snapshot.py \
  --pg-host 127.0.0.1 \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

---

## Compare Snapshots

```bash
python3 scripts/compare_snapshots.py \
  snapshots/system_snapshot_YYYYMMDD_HHMMSS.json \
  snapshots/latest_status.json
```

---

## Refresh Rankings

Only run after human approval. This mutates database state.

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

After refresh:

```bash
./.venv/bin/python scripts/export_system_snapshot.py --pg-host 127.0.0.1 --pg-user test --pg-password test --pg-database clawer
./scripts/inspect_source_freshness.py --summary-output reports/maintenance_readiness_summary.md
./scripts/smoke_release.sh
```

---

## Validate Release State

```bash
./scripts/smoke_release.sh
./scripts/inspect_source_freshness.py
./scripts/build_operational_index_summary.py
```

---

## Rebuild Demo Bundle

```bash
./scripts/build_demo_caveats.py
./scripts/build_demo_bundle.sh
```

---

## Human-First Rule

Reports can classify stale, degraded, or critical states. They do not authorize
automatic repair. A human decides whether to refresh data, defer a demo claim,
or preserve the current state as an accepted limitation.
