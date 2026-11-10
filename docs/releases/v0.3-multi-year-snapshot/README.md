# CrawlerNest v0.3 — Multi-Year Release Snapshot

Freeze date: 2026-11-11 (dumped 2026-11-10 UTC)
Database: `clawer`
Built from commit: see `manifest.json` (`built_from_commit`)

## Snapshot

- File: `clawer-2026-11-10-release.dump` (PostgreSQL 16 custom archive, `pg_restore`)
- SHA-256: `2bca1ecf30a7ff482efbcfbab8883af497261468f864bb2db3081ac01380df51`
- `manifest.json` holds every count below. It was written by `scripts/release_snapshot.py build`
  from a copy of the dump restored into a scratch database, not from the live warehouse.

**No user data.** The schema of `warehouse.app_user`, `warehouse.password_reset_token`, `warehouse.saved_*`,
`desk.*` and `agent_state.*` is included; their rows are not. The build refuses to write a manifest if a
restored copy holds any, and the verifier checks again.

## Verified contents

Source ranks in `warehouse.ranking_record`:

| Edition | QS | THE | ARWU |
| --- | ---: | ---: | ---: |
| 2026 | 9,866 | 1,713 | 961 |
| 2025 | 1,506 | 1,663 | 967 |
| 2024 | 1,471 | 1,544 | 982 |
| 2023 | 1,397 | 1,488 | 983 |
| 2022 | 1,270 | 1,409 | 984 |
| 2021 | — | 1,317 | 986 |
| 2020 | 1,038 | 1,223 | 988 |
| 2019 | 973 | 1,125 | 990 |
| 2018 | 946 | 1,008 | 990 |
| 2017 | — | 907 | 795 |
| 2016 | 890 | 753 | 498 |
| 2015 | — | 381 | 498 |

QS 2026 counts every universe type (global, region, regional, special, subject); every other cell is `global`.
QS 2016, 2018–2020 and 2022–2024 come from Internet Archive captures, with `rank` as the lower bound of the
printed rank. QS has no 2015, 2017 or 2021 in this release (2015 and 2021 are pinned in
`crawlernest-kb/qs_archive/manifest.json` and not ingested). A dash is our gap, not QS declining to rank.

`analytics.aggregated_rankings`: 27,409 rows — 10,555 for 2026 (global 2,192, region 1,633, regional 3,198,
special 2,074, subject 1,458) and global-only for 2015–2025 (558 / 1,065 / 1,097 / 1,412 / 1,510 / 1,599 /
1,539 / 1,845 / 1,978 / 2,076 / 2,175).

Other tables: 4,059 canonical universities; 21,071 `analytics.ml_predictions` rows (2,270 in
`v_ml_predictions_latest`); 3,441 Wikipedia introductions; 272 US institutions with 7,870 federal metrics.

## What is new since v0.2

- Historical editions: THE and ARWU 2015–2025, QS archive editions.
- US federal institutional data (College Scorecard, IPEDS) — not a ranking source.
- Wikipedia introductions. The article text is Wikipedia's under CC BY-SA 4.0; anything that renders it
  shows the article link and licence.
- 112 duplicate canonical records merged (2026-10-12) and false entity merges split (2026-10-03).

## Restore

Into an empty database:

```bash
PGDATABASE=clawer ./scripts/restore_release_snapshot.sh
```

Set `API_BASE_URL=http://localhost:8080` as well when the API is running against that database; the script
then checks the rankings and ranking-trends endpoints against the manifest. To check a database without
restoring:

```bash
./.venv/bin/python scripts/release_snapshot.py --pg-database clawer verify --release-dir docs/releases/v0.3-multi-year-snapshot
```
