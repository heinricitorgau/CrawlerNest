# Ranking Schema Convergence

Retiring `warehouse.ranking_records_preview` and pointing every reader at
`warehouse.ranking_record`.

Companion to [ADMISSION_SCHEMA_CONVERGENCE.md](ADMISSION_SCHEMA_CONVERGENCE.md),
which did the equivalent thing for the admission side. This one is smaller:
there is no rename and no column extraction, because the destination table
already existed and was already full.

---

## Why this was needed

`warehouse.ranking_record` had been the real ranking fact table since
`92a7bf8` ("Give warehouse.ranking_record one writer"). The preview table kept
its readers.

Measured against the live `clawer` database on 2026-08-22:

| table | rows |
|---|---|
| `warehouse.ranking_records_preview` | 0 |
| `warehouse.ranking_record` | 3310 |

Two user-visible consequences, both reproduced before the change:

1. `preview-ranking-admission-convergence` reported
   `both=0 ranking_only=0 admission_only=8`. The convergence count the command
   exists to produce was structurally always zero on the ranking side.
2. `GET /api/v1/preview/universities?universityName=University of Oxford`
   returned `rankingSummary: null` and `hasRankingData: false` for a university
   with three ranking rows and aggregated rank 1. Its `admissionSummary` was
   populated, so the contrast was purely the dead table.

---

## The actual design work: picking a scope

This is not a find-and-replace. The two tables have different grains.

`ranking_records_preview` carried the source as a `source TEXT` column, the rank
as `rank INTEGER NOT NULL`, and the university's name inline. It held one
universe, so selecting the whole table gave something coherent.

`ranking_record` is keyed
`(canonical_university_id, ranking_source_id, ranking_year, ranking_type,
universe_type, universe_key)` — enforced by `uq_ranking_record_universe`. A
university appears once per source *and* once per universe it was ranked in.
The source is a `SMALLINT` FK into `warehouse.ranking_source`, and the rank is
`rank_position INTEGER` — **nullable**, where the preview column was not.

So every read had to make three decisions:

| # | Decision | Rationale |
|---|---|---|
| 1 | Pin `ranking_type='world'`, `universe_type='global'`, `universe_key='global'` | Without it a regional table would be folded into the same `MIN(rank_position)` as the world table, and a university ranked 4th in Asia would out-rank its own world position. Only this universe is currently ingested, so the filter changes no result today — it stops the query being wrong the first time a second universe lands |
| 2 | Aggregate across years, do not pin one | `RankingPreviewSummaryDTO` already exposes `rankingYears` as an array and `bestRankingYear` as the year the best rank came from. Pinning a year would make one always-single-element and the other always redundant. This preserves the previous semantics exactly |
| 3 | Exclude `rank_position IS NULL` | `rank` was `NOT NULL` in the preview table, so every row there was a ranking datapoint. `rank_position` is nullable, and a row with no rank would inflate `row_count` while contributing nothing to `best_rank`. There are zero such rows today |

Sources are resolved by joining `warehouse.ranking_source` and reading
`source_code`, which is what produces the `"QS"` / `"THE"` / `"ARWU"` strings the
DTO and the CLI summary already promised.

The scope lives in one place per language:

- Python — `crawlernest/pipeline/ranking_scope.py`
- Java — inline in `UniversityPreviewRepository`, matching that file's existing
  idiom of one self-contained text block per query

---

## Call sites

**Python readers** — `crawlernest/pipeline/convergence_preview.py`,
`crawlernest/pipeline/canonical_university_detail_preview.py`. Both had the
ranking filter written twice in one query; both now derive their summaries from
a single scoped CTE, so the filter cannot drift within a query either.

**Python defaults** — `crawlernest/pipeline/cli.py` (the two reader parsers),
`crawlernest/run_pipeline.py`.

**Java main** — `clawer/repository/UniversityPreviewRepository.java`: four
identity-lookup `EXISTS` clauses plus the ranking summary CTE. The summary now
binds the canonical id once rather than twice, because the scoped CTE is
referenced by both halves.

**Java test fixtures** — `university_preview_integration_{setup,seed,cleanup}.sql`
move to `ranking_record` and seed `warehouse.ranking_source` idempotently by
`source_code` (`ranking_source_id` is a `SMALLSERIAL` and differs between a
developer's database and a fresh one). The `rankings_integration_*` fixtures had
their preview blocks **deleted** rather than migrated — nothing reads that table
in those tests, and see the trap below.

---

## Traps

**A fixture that creates the table undoes the drop.** The Java integration
fixtures ran `CREATE TABLE IF NOT EXISTS warehouse.ranking_records_preview`
against the developer's real database. Dropping the table while leaving that in
place means the next `./mvnw test` silently recreates it — empty, unconstrained,
and once again shadowing the real one. This is the same shape as the 42P07
rename-skip the admission migration hit, arriving from the other direction.
Verified after the fact: the table is still absent after a full integration run.

**The writer recreated its own target.** `warehouse_writer.py::_ensure_table`
carried a second copy of the DDL and ran `CREATE TABLE IF NOT EXISTS` on every
write. That is why the table existed at all — **no schema file ever defined it**.
It is now `_require_table`, which raises and names `bootstrap-postgres`, matching
what the admission migration did to its counterpart.

**A schema file cannot contain a dollar-quoted block, and `psql` will not tell
you.** The guard against dropping a non-empty table was first written as a
`DO $$ … $$` block in `multi_source_postgresql.sql`. Both appliers
(`bootstrap_postgres.py` and `pipeline/utils/schema.py`) run
`_split_sql_statements`, which truncates every line at `--` and splits on every
`;`. A procedural block has semicolons inside it, so it reaches psycopg2 as
several fragments and dies with `unterminated dollar-quoted string`.

`psql` handles it perfectly, which is exactly what makes it dangerous: applying
the file by hand succeeds and the live database gets migrated, so the change
looks verified. Only `bootstrap-postgres` breaks — that is, only a fresh clone,
which is the one case nobody runs while iterating. Reproduced against an empty
database, fixed, and re-reproduced clean.

ADMISSION_SCHEMA_CONVERGENCE.md states this constraint ("no `DO $$ … $$` blocks
in any schema file") under its own Traps section. It is worth reading the applier
constraints *before* writing a schema file, not after.

**The drop refuses rather than destroying — from Python.** The schema file now
carries a plain `DROP TABLE IF EXISTS`, and the non-empty check lives in
`assert_ranking_preview_is_empty()`, called by both appliers before any file
runs — mirroring `assert_no_admission_table_collision()`. Applying the `.sql` by
hand bypasses it, the same caveat the admission rename carries.

`ensure_subject_ranking_postgres_schema()` needed the guard too: it applies
`multi_source_postgresql.sql` from its own shorter file list and called no
precondition at all.

Verified both ways — a stray table holding one row is refused with the row still
in place; the same table empty is dropped and the bootstrap completes.

---

## The preview write chain (removed)

**Step 1 of this migration was "confirm nothing writes the table". It did not
hold.** Six CLI commands still targeted `ranking_records_preview` by default,
forming a parallel landing pipeline —
`staging → ranking_records_preview → aggregated_rankings_preview → ranking_decision_preview`
— that was inert end to end: its middle table held zero rows and
`warehouse.aggregated_rankings_preview` did not exist in the database at all. No
script, CI workflow, or doc invoked any of them.

Repointing them at `ranking_record` would have been actively wrong: they write
and mutate columns (`university_name`, `source`, `entity_resolution_status`)
that table does not have, and the writer's `ON CONFLICT` target does not exist
there. So the chain was deleted instead.

### What was purely preview-chain, and went

| command | now |
|---|---|
| `write-ranking-warehouse-preview` | deleted |
| `aggregate-ranking-preview` | deleted |
| `resolve-ranking-entities` | deleted |
| `unresolved-ranking-entities` | deleted |
| `refresh-ranking-resolution` | deleted |

With their last callers gone, four modules were unreachable and were deleted
too: `crawlernest_ranking_crawler/warehouse_writer.py`, `entity_resolver.py`,
`unresolved_report.py` and `aggregation_writer.py`. (The `_require_table` fix
described under Traps therefore no longer exists — the writer it guarded is
gone, which is the stronger version of the same guarantee.)
`crawlernest_ranking_crawler/aggregator.py` keeps only the
`AggregatedRankingRow` dataclass; its `aggregate_rankings()` had no caller left.

### What was shared, and stayed

**`rebuild-preview-and-resolve` ran four steps across both pipelines.** Steps 1
and 3 were the ranking half and are gone with their flags
(`--ranking-preview-input-file`, `--ranking-landing-schema`,
`--ranking-landing-table`); steps 2 and 4 write `warehouse.admission_record` and
refresh admission entity resolution, which is the live pipeline and is
unchanged. The command survives, admission-only, with its steps renumbered.

**`preview-ranking-warehouse-map` was left in place.** It writes a JSON artifact
and never touches the database, so it is not part of the write chain — but its
only consumers were the two deleted commands, so it now produces an artifact
nothing reads. Removing it is a separate call.

### What needed a new source rather than deletion

**`decision-ranking-preview` survives, repointed.** Its target,
`warehouse.ranking_decision_preview`, still exists and is read by
`JdbcScopedRankingReadAdapter`, so deleting the command would have orphaned a
live API path. Its source was the dropped middle table — and its
`--source-schema` / `--source-table` flags were decorative, because
`decision_writer.load_aggregated_rows_from_postgres()` hardcoded
`FROM warehouse.aggregated_rankings_preview` and ignored them. It now reads
`analytics.aggregated_rankings` joined to `canonical_university`, and the flags
are honoured.

That table stores less than the preview table did: no normalized name, no source
count, no standard deviation. The name comes from
`canonical_university.display_name_normalized`; the other two are recomputed
from `source_ranks_json` with the arithmetic the deleted chain used — the mean
of the per-source ranks and their population standard deviation — so a row built
from analytics matches what the chain would have produced. Sources with a null
rank are dropped rather than counted.

Verified against the live database by writing to a scratch target: 1499 rows,
one per canonical university, 2026. Oxford comes out `{"QS": 3, "THE": 1,
"ARWU": 7}`, `aggregated_rank` 3.67, `source_count` 3 — consistent with the
warehouse figures above. Source-count spread: 607 rows with three sources, 597
with two, 295 with one.

**Found while verifying, not fixed here:** 216 of 1499
`canonical_university.display_name_normalized` values carry a trailing space
(e.g. `'indian institute of technology bombay iitb '`). `build_decision_row()`
strips the name, so those rows cannot rejoin `canonical_university` on the
equality the Java adapter uses, and are invisible to the API. This predates the
migration — the deleted chain stripped identically — and is a warehouse data
defect, not a schema one.

---

## Verification

```bash
python3 -m crawlernest.run_pipeline preview-ranking-admission-convergence \
  --pg-user test --pg-password test --pg-database clawer
```

```
before:  rows=8  both=0  ranking_only=0   admission_only=8
after:   rows=50 both=8  ranking_only=42  admission_only=0
```

`ranking_only=42` is new and correct: the limit-50 window now surfaces ranked
universities that have no admission data, which the empty table had hidden.

```bash
curl -s 'localhost:8080/api/v1/preview/universities?universityName=University%20of%20Oxford'
```

```
before:  "rankingSummary": null,               "hasRankingData": false
after:   "rankingSummary": {"rowCount":3, "sources":["ARWU","QS","THE"],
                            "bestRank":1, "bestSource":"THE",
                            "bestRankingYear":2026},
         "hasRankingData": true, "missingSections": []
```

`bestRank: 1` from THE is consistent with the warehouse: Oxford is QS 3, THE 1,
ARWU 7 for 2026.

Suites: 36 Java tests (`UniversityPreviewApiIntegrationTest`,
`RankingApiIntegrationTest`, `SubjectRankingApiIntegrationTest`) and 204 Python
tests with `CRAWLERNEST_RUN_PG_TESTS=1`, all passing.
