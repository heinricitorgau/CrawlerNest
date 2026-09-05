# CrawlerNest 2026 Data Release Freeze

Freeze date: 2026-09-05
Source ingest: 2026-09-04
Database: `clawer`

## Snapshot

- File: `clawer-2026-09-04-release-freeze.dump`
- Format: PostgreSQL custom archive (`pg_restore`)
- SHA-256: `28c67b7e8bc5ac7fc848221afdeee2ddf5a65e3c875d911027388e8a641be35e`

## Verified contents

The archive was restored into a disposable PostgreSQL database and checked before
this manifest was written:

| Check | Result |
| --- | ---: |
| `analytics.aggregated_rankings` rows for 2026 | 10,125 |
| `warehouse.ranking_record` rows for 2026 | 12,005 |
| QS source rows for 2026 | 9,530 |
| THE source rows for 2026 | 1,637 |
| ARWU source rows for 2026 | 838 |

The 10,125 aggregated rows span these scopes:

| `universe_type` | Rows |
| --- | ---: |
| `global` | 2,098 |
| `region` | 1,629 |
| `regional` | 3,198 |
| `special` | 2,074 |
| `subject` | 1,126 |

## Restore

Create or select an empty PostgreSQL database, then run:

```bash
PGPASSWORD=test pg_restore -h localhost -U test -d clawer \
  --no-owner --exit-on-error \
  releases/v0.2-2026-snapshot/clawer-2026-09-04-release-freeze.dump
```

After restore, run `scripts/start_localhost.sh`. The launcher is intentionally
read-only with respect to the warehouse: it checks PostgreSQL and starts the API
and web services; it does not crawl or mutate ranking data.
