# CrawlerNest v0.3.1 — QS 2017 Relabel

Freeze date: 2026-11-11
Database: `clawer`
Built from commit: see `manifest.json` (`built_from_commit`)

## Snapshot

- File: `clawer-2026-11-11-release.dump` (PostgreSQL 16 custom archive, `pg_restore`)
- SHA-256: `a368095d26b37b39efdc03b13a5a3684e3fae31b2bbc11f30d4bbc6f397b0690`
- `manifest.json` holds every count, read back from a copy of the dump restored into a scratch database.
- No user data: user tables are dumped as schema only, and both the build and the verifier check it.

## What changed since v0.3

One data change, by decision of the repository owner on 2026-11-11:

- **QS's September 2016 table is QS 2017.** An edition's year is now the one QS's own title gives it today. QS
  published that table as "2016/17" and has titled its page "2017" since 2020; the page address still reads /2016.
  The table was ingested as 2017 from the same archived data file (same sha256), proven by a 2020 capture of the page
  whose title names 2017. The 890 identical QS 2016 rows were then retired and 2016 re-aggregated. Receipts:
  `crawlernest/crawlernest-kb/qs_archive/receipts/2017_*.json` and `2016_retired_as_2017_*.json`.
- **QS 2015 and 2021 are not ingested** (also decided; parked under `_not_ingested` in the archive manifest).

QS editions held: 2017–2020 and 2022–2026; no 2015, 2016 or 2021. THE and ARWU: 2015–2026, unchanged.

| Edition | Aggregated rows | QS ranks |
| --- | ---: | ---: |
| 2016 | 842 (was 1,065) | 0 (was 890) |
| 2017 | 1,246 (was 1,097) | 890 (was 0) |

Every other count equals v0.3's. `analytics.aggregated_rankings` holds 27,335 rows (v0.3: 27,409). 2016 lost the
223 universities QS alone ranked there; in 2017, 149 of those become new rows and 74 join a THE or ARWU 2017 row
they already had, hence 74 fewer in all.

`cross_edition_ranks.csv` and the MATLAB cross-edition forecast were regenerated from this warehouse (MATLAB and
Python agree to 1e-9); QS now has 2017→2018 pairs it did not have when the table was labelled 2016.

## Restore

```bash
RELEASE_DIR=docs/releases/v0.3.1-qs-2017-relabel PGDATABASE=clawer ./scripts/restore_release_snapshot.sh
```
