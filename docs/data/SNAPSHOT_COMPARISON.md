# Snapshot Comparison

Operational snapshots show what the pipeline believed at a point in time.
Comparing two snapshots helps detect drift without rerunning ingestion or
changing pipeline state.

## Command

```bash
python3 scripts/compare_snapshots.py snapshots/old.json snapshots/new.json
python3 scripts/compare_snapshots.py snapshots/old.json snapshots/new.json --json
```

The command is readonly. It reads two JSON files and writes the comparison to
stdout.

## Compared Signals

`compare_snapshots.py` compares:

- aggregated ranking count
- unresolved entity count
- source coverage by source code
- stale status
- drift warning count
- freshness payload

Missing fields are treated as unknown or empty rather than crashing.

## Output

Default output includes:

- markdown summary
- source coverage table
- freshness JSON block
- machine-readable JSON payload

Use `--json` when the comparison is consumed by scripts.

## Failure-State Fixtures

CI fixtures under `crawlernest/crawlernest-autoeval/datasets/ci_fixtures/`
include:

- `stale_state.json`
- `missing_source_state.json`
- `unresolved_spike_state.json`
- `empty_aggregation_state.json`

These fixtures make failure-state validation reproducible without PostgreSQL.

## Operational Use

Use snapshot comparison when:

- an aggregation run looks suspicious
- unresolved counts jump
- source coverage changes
- freshness status changes
- a demo or handoff needs before/after evidence

Snapshot comparison is diagnostic only. It must not change aggregation,
recommendation scoring, canonical matching, schema, frontend behavior, or agent
workflow behavior.
