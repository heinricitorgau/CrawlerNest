# CrawlerNest 2026 Data Release Freeze

Freeze date: 2026-09-05
Source ingest: 2026-09-04
Database: `clawer`

> **Note (2026-11-11): cleaned, and history rewritten.** As first committed, this dump also held 2 rows of
> `warehouse.app_user` (an email and its bcrypt password hash). It was replaced by a dump restored from it with
> user-table data excluded, as every release now is, and git history was rewritten so that no commit carries the
> original. No other table changed; `manifest.json` verifies the counts below.

## Snapshot

- File: `clawer-2026-09-04-release-freeze.dump`
- Format: PostgreSQL custom archive (`pg_restore`)
- SHA-256: `59e5245109508a27e9b0e7c6d8ca7d5deade017afb47e0863a9b70fdf464e39e`

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
  docs/releases/v0.2-2026-snapshot/clawer-2026-09-04-release-freeze.dump
```

After restore, run `scripts/start_localhost.sh`. The launcher is intentionally
read-only with respect to the warehouse: it checks PostgreSQL and starts the API
and web services; it does not crawl or mutate ranking data.

To restore and verify the frozen counts in one step, use:

```bash
RELEASE_DIR=docs/releases/v0.2-2026-snapshot PGDATABASE=clawer ./scripts/restore_release_snapshot.sh
```

Set `RELEASE_DIR=docs/releases/v0.2-2026-snapshot`, because the script now defaults to the latest release.
Set `API_BASE_URL=http://localhost:8080` as well when the API is already running;
the script will then smoke-test the rankings and ranking-trends endpoints.
