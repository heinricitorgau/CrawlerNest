# Snapshot Lineage

CrawlerNest snapshots are point-in-time operational evidence. They are
readonly, append-oriented, historical, and non-authoritative for runtime
behavior.

---

## Snapshot Source

`scripts/export_system_snapshot.py` reads PostgreSQL and writes:

- `snapshots/system_snapshot_<timestamp>.json`
- `snapshots/latest_status.json`

The script captures health, freshness, unresolved counts, drift warnings,
regression summary, and latest ingestion metadata. It does not modify database
state.

---

## Lifecycle

1. A pipeline run or release checkpoint creates runtime state in PostgreSQL.
2. `export_system_snapshot.py` captures that state into a dated JSON file.
3. `latest_status.json` is refreshed as the compact latest pointer.
4. Timeline and intelligence reports read snapshots and derive historical
   summaries.
5. `build_demo_bundle.sh` copies selected snapshots and summaries into the
   release bundle.

---

## Timeline Derivation

`scripts/build_snapshot_timeline.py` reads all `snapshots/*.json`, tolerates
missing fields, skips malformed files with warnings, and emits:

- `reports/snapshot_timeline.md`
- `reports/snapshot_timeline.json`

The timeline deduplicates equivalent latest/named snapshots so readers see
historical states rather than duplicate pointers.

---

## Relationship To Snapshot Comparison

`scripts/compare_snapshots.py` compares two selected snapshot files. It is best
for focused before/after review.

`build_snapshot_timeline.py` is best for broad historical visibility across all
available snapshot files.

Both are readonly and file-based.

---

## Relationship To Freshness Escalation

`scripts/build_freshness_escalation.py` uses the latest normalized snapshot to
classify current freshness as:

- `healthy`
- `degraded`
- `stale`
- `critical`

It observes age, expected source gaps, aggregation count, and subject freshness
evidence. It does not rerun the pipeline.

---

## Relationship To Drift Timeline

`scripts/build_drift_timeline.py` compares neighboring snapshots and classifies:

- unresolved increase/decrease
- source disappearance/appearance
- stale-state transitions
- aggregation count collapse or drop
- drift warning history

It emits severity labels (`info`, `warning`, `critical`) for human review only.

---

## Runtime Boundary

Snapshots are not runtime authority. If a snapshot says data is fresh or stale,
that is evidence captured at export time. The running API and PostgreSQL state
remain the operational source of truth for live behavior.
