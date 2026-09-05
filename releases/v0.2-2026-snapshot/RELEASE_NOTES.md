# CrawlerNest v0.2 - 2026 Data Release Freeze

**Release label:** `v0.2-2026-snapshot`
**Freeze date:** 2026-09-05
**Source ingest:** 2026-09-04

This release freezes the reproducible 2026 database snapshot. It contains
9,530 QS, 1,637 THE, and 838 ARWU source ranks; 10,125 aggregated ranking rows
across all scopes; 2,098 global canonical rows; and 2,279 rows exposed through
`analytics.v_ml_predictions_latest`.

The release preserves deterministic Agent 2026 context locking, ML estimate
provenance through `isEstimated` and support caveats, source-linked entity
resolution, and partial-coverage disclosures. It makes no real-time or
cross-year trend claim.

Restore the database with the command in [README.md](README.md), then run
`scripts/start_localhost.sh`. The snapshot was restored into a disposable
PostgreSQL database and verified before this release note was prepared.
