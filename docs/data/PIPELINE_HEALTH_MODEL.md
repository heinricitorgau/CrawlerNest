# Pipeline Health Model

CrawlerNest pipeline health is classified from readonly operational evidence.
The model is intentionally conservative: it reports state and likely risk, but
does not auto-fix data, change aggregation, or tune recommendation behavior.

## States

### healthy

The pipeline has current aggregated rankings, ranking records, source coverage,
and freshness within expected thresholds.

Expected signals:

- `analytics.v_aggregated_rankings_latest` has rows
- `warehouse.ranking_record` has rows
- latest finished aggregation is recent
- unresolved ratio is within tolerance
- expected sources have coverage, or missing sources are an accepted local scope

### degraded

The pipeline is usable but has quality or coverage risk.

Examples:

- one expected source is missing
- unresolved ratio exceeds tolerance
- duplicate resolution saves are present and need review
- aggregated row count is low but not empty

### stale

The pipeline has data, but the latest finished aggregation is older than the
freshness expectation.

Stale data can still be served, but diagnostics should make the age visible and
operators should avoid treating it as newly validated evidence.

### failed

The pipeline cannot provide reliable rankings evidence.

Examples:

- database is unreachable
- required tables or views are missing
- aggregated rankings are empty
- ranking records are empty
- no finished aggregation timestamp exists

## Thresholds

Default thresholds used by `scripts/check_pipeline_health.py`:

```text
stale_after_hours: 36
min_aggregated_rows: 100
max_unresolved_ratio: 5%
expected_sources: QS, THE, ARWU
```

These thresholds are operational diagnostics, not product logic. Changing them
must not change aggregation formula, recommendation scoring, canonical matching,
or subject ranking schema.

## Unresolved Tolerances

Unresolved entities represent source rows that could not be mapped to canonical
universities.

Default tolerance:

```text
unresolved_count / ranking_record_count <= 5%
```

Above that level, health is degraded. If rankings are empty or source records
are missing, health is failed.

## Drift Tolerances

Source drift should be treated as a review signal, especially when:

- unresolved counts spike relative to previous ingestion
- source record counts drop unexpectedly
- rank or score distributions shift sharply
- duplicate resolution saves increase

Drift does not automatically imply a code bug. Check upstream availability,
source markup changes, and ingestion logs before changing normalization or
matching logic.

## Freshness Expectations

For normal local and daily operational checks, the latest finished aggregation
should be no older than 36 hours.

Freshness state:

| Signal | State |
| --- | --- |
| `<= 36 hours` | fresh |
| `> 36 hours` | stale |
| missing timestamp | failed |

Subject rankings are tracked separately by latest subject year. Missing subject
data may be degraded or failed depending on the workflow being validated, but it
must not alter global aggregation health by itself.

## Source Coverage

Expected global ranking sources:

```text
QS
THE
ARWU
```

If a source has zero `warehouse.ranking_record` rows, health is degraded unless
the current run is intentionally scoped to a subset. A missing source should be
classified as operational coverage risk, not a reason to change scoring.

## Operational Use

Run:

```bash
python3 scripts/check_pipeline_health.py
python3 scripts/check_pipeline_health.py --json
```

Use `--strict` only when a non-healthy state should fail the calling process.
Default mode is reporting-only so local smoke checks can remain useful when a
developer lacks PostgreSQL or live data.
