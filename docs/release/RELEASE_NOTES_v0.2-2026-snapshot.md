# CrawlerNest v0.2 - 2026 Data Release Freeze

**Release label:** `v0.2-2026-snapshot`
**Freeze date:** 2026-09-05
**Source ingest:** 2026-09-04
**Release type:** Reproducible data snapshot and competition demonstration baseline

## Summary

This release freezes the 2026 CrawlerNest warehouse and analytics database for
local reproduction. It includes the QS, THE, and ARWU source records, canonical
entity resolution, aggregation outputs across all supported scopes, ML
prediction view data, and the read-only API contract used by the competition
demo.

The full `analytics.aggregated_rankings` table contains 10,125 rows for 2026.
The global API view currently exposes a canonical universe of 2,098 rows; the
10,125 total also includes region, regional, special, and subject scopes.

## Data Coverage

| Source or artifact | Frozen value |
| --- | ---: |
| QS source ranks | 9,530 |
| THE source ranks | 1,637 |
| ARWU source ranks | 838 |
| 2026 aggregated rankings across all scopes | 10,125 |
| 2026 global canonical ranking universe | 2,098 |
| `analytics.v_ml_predictions_latest` rows | 2,279 |

Source coverage is partial. A missing source rank may result from snapshot scope
or entity resolution and must not be presented as the source declining to rank
a university.

## Engineering Highlights

- Agent context is hard-locked to the 2026 dataset year and rejects unsupported
  temporal claims rather than filling gaps with invented rankings.
- `analytics.v_ml_predictions_latest` is included in the frozen database. Model
  estimates retain `isEstimated`, support status, and estimate-related caveats.
- QS, THE, and ARWU coverage is stored with source provenance and deterministic
  aggregation evidence.
- Entity resolution and canonical university identity are preserved in the
  warehouse, including source mappings and unresolved-data boundaries.
- Competition documentation now distinguishes current 2026 live guidance from
  the RC-1 historical baseline.

## Operational Boundaries

- This is a point-in-time 2026 snapshot, not a real-time feed.
- Current trend data has one available year, so no year-over-year rank delta is
  claimed.
- THE and ARWU coverage is partial, not complete for every university.
- The Agent API may use its deterministic fallback when no generation provider
  is configured; ranking and recommendation data remain outside its write path.
- The database snapshot is restored before `scripts/start_localhost.sh`; the
  launcher checks PostgreSQL and starts services but does not crawl or mutate the
  warehouse.

## Snapshot Artifact

See [the snapshot manifest](../../releases/v0.2-2026-snapshot/README.md) and
`clawer-2026-09-04-release-freeze.dump` for the PostgreSQL custom-format archive.
The manifest records the SHA-256 checksum and the verified restore procedure.

## Verification

The freeze archive was restored into a disposable PostgreSQL database and
rechecked for the 2026 aggregation and source counts before release preparation.
The local API smoke check returned `rankingYear: 2026` and `sourceCount: 3`.
