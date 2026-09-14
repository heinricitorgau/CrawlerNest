# Admission Schema Convergence

Migration guide for folding the admission pipeline into the entity-resolution
and review infrastructure the ranking side already uses.

Two things change:

1. `warehouse.mapping_review` stops being ranking-only. Its key moves from
   `ranking_source_id` to `source_code`, so a non-ranking source — starting
   with university admission pages — can be reviewed by the same people
   through the same screen.
2. `warehouse.admission_records_preview` is promoted to
   `warehouse.admission_record`, and the fields that are actually queried
   (GPA, Duolingo, deadline, degree level) come out of `raw_payload` and
   become columns.

This document is the checklist. Each phase names every file that has to move
with it, because several of them fail silently rather than loudly.

---

## Why this is needed

Measured on the eight checked-in admission snapshots
(`crawlernest/scripts/explore_admission_raw_data.py`):

| resolver | resolved |
|---|---|
| exact-only, what `crawlernest_admission_crawler.entity_resolver` used to do | 3/8 |
| `EntityResolver`, shared with the ranking side, in use since phase 4 | 8/8 |

The five misses are the same shapes the ranking resolver already handles:
`University of Melbourne` vs `The University of Melbourne`,
`National University of Singapore` vs `National University of Singapore (NUS)`.
Writing a second resolver means reproducing the same bugs; the admission
pipeline reuses the ranking one instead.

One of the eight (`UCL (University College London)`, fuzzy, 0.8819) lands in
the review band, so admissions needs a review path from the first run — not
later.

---

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Add `warehouse.entity_source` as a small registry; `mapping_review.source_code` carries a FK to it | Referential integrity beats a `CHECK` list. Future sources (tuition, housing) register instead of forcing a DDL edit |
| 2 | `mapping_review.ranking_source_id` becomes nullable this round, dropped next | Zero-cost rollback during the transition. Tracked as tech debt — leaving both keys forever is the failure mode |
| 3 | `degree_level` is one of `undergraduate` / `postgraduate` / `doctoral`, `NOT NULL DEFAULT 'unknown'` | Those are the only values `_DEGREE_MAP` can emit. `NOT NULL` is load-bearing: PostgreSQL treats `NULL`s as distinct in a `UNIQUE`, so a nullable `degree_level` in the natural key would let the same page insert forever |
| 4 | Reuse the review infrastructure; do not build an admission-specific one | The question a reviewer answers — "is this name this university?" — does not depend on whether the payload is a rank or an IELTS band. Two review paths means UCL gets judged twice, possibly differently |

Source credibility (an official admission page is first-hand, a ranking table
is not) is a *confidence* concern, not a *review* concern. It belongs in
`SOURCE_TYPE_PRIORITY` in `crawlernest_admission_crawler/resolver.py`, which
already ranks `official_admission_page` first.

---

## Prerequisite: admission rows need a `source_entity_id`

`mapping_review` reviews a `(source_code, source_entity_id)` pair. Ranking rows
have always had one (a QS nid, a THE id). Admission rows had not: the natural
key of the admission table was `(normalized_university_name, source_url)`, and
`normalized_university_name` is the very thing entity resolution decides.

Keying a durable human decision on a value the resolver may change is a bug in
waiting — the decision silently stops applying the moment the name normalizes
differently. So `source_entity_id` is added first, and it must not contain the
university's name.

**Definition** — the source URL reduced to a stable identity:

```
lowercase, strip scheme, drop query and fragment, strip trailing slashes
https://www.ucl.ac.uk/prospective-students/graduate/taught-degrees/english-language-requirements
  -> www.ucl.ac.uk/prospective-students/graduate/taught-degrees/english-language-requirements
```

The Python definition lives in
`crawlernest_admission_crawler/source_identity.py` and is mirrored by the
backfill in `crawlernest/crawlernest-schema/admission_postgresql.sql`. The two
must agree; `crawlernest/crawlernest-tests/test_admission_source_identity.py`
pins the Python side.

---

## Phase order

Each phase is independently deployable and independently revertible.

| Phase | Scope | Status |
|---|---|---|
| 1 | Schema: `source_entity_id`, `entity_source`, `mapping_review` migration, `v_entity_mapping` | done |
| 2 | Python: `load_mapping_reviews`, `apply_mapping_reviews.py`, the two review SQL scripts | done |
| 3 | Java + web: review repository, DTOs, service validation, admin screen | done |
| 4 | Admission ER: swap the exact-only resolver for `EntityResolver`, write `warehouse.source_mapping` | done |
| 5 | Rename to `warehouse.admission_record`, extract columns, update all call sites | done |
| 6 | Close the crawler → staging gap | done |
| 7 | Programme / intake granularity; admission mappings move to `source_university_mapping`; ranking guardrails in the admission resolver | done (schema + resolver) |
| 8 | Readers stop collapsing rows with `MIN()`; `CAVEAT_IELTS_MISSING` / `CAVEAT_ADMISSION_DATA_STALE` with the fetch date | next |

Phase 1 could not stand alone as first planned. Making `source_code` NOT NULL
and moving the unique constraint breaks both existing writers — their
`ON CONFLICT (ranking_source_id, source_entity_id)` target stops existing — so
the minimum compatible edit to `saveDecision` and `apply_mapping_reviews.write`
landed with phase 1 rather than with phase 3. Likewise
`upsert_ranking_sources` had to start mirroring into `entity_source` in phase
1, or the new foreign key would reject the first review filed against a
ranking source registered after bootstrap.

---

## Phase 1 — schema (landed)

### 1.1 `warehouse.entity_source`

New registry in `crawlernest/crawlernest-schema/mapping_review_postgresql.sql`,
seeded from `warehouse.ranking_source` plus one row for `university_site`.
Adding a source is an `INSERT`, not a DDL change.

### 1.2 `mapping_review` re-keyed

`source_code TEXT NOT NULL` added and backfilled from `ranking_source`;
`ranking_source_id` relaxed to nullable; the unique constraint moves from
`(ranking_source_id, source_entity_id)` to `(source_code, source_entity_id)`.

The 119 existing decisions carry over untouched — the backfill joins on the
FK that is already there.

### 1.3 `warehouse.v_entity_mapping`

The review queue is *not* derived from `mapping_review`. It is derived from
`warehouse.source_university_mapping WHERE match_method IN ('fuzzy',
'fuzzy_review')`. Admission mappings will land in `warehouse.source_mapping`
instead — a second, parallel mapping table that already exists with a
`source_name TEXT` column and zero rows.

`v_entity_mapping` unions the two under one `source_code` vocabulary so the
queue has a single place to read from. It is additive: nothing consumes it
until phase 2.

> **The admission writer must populate `metadata.raw_row`.**
> The review screen renders the source's own name and country from
> `metadata #>> '{raw_row,name}'` and `{raw_row,location}`. Those are written
> by each source's crawler, *not* by `EntityResolver._build_metadata`. Without
> them the reviewer sees a blank row and cannot judge the pair.

### 1.4 `source_entity_id` on the admission table

Added, backfilled from `source_url`, indexed. The table keeps its old name
this round; the rename is phase 5.

The `CREATE TABLE` also moved out of `recommendation_postgresql.sql` into a new
`admission_postgresql.sql`, loaded *before* it. The recommendation view depends
on the admission table, so the table has to exist first — and in phase 5 that
ordering is what lets the rename land before the view is rebuilt.

---

## Phase 2 — Python (landed)

| File | Change |
|---|---|
| `crawlernest/crawlernest-core/multi_source/repository.py` | `load_mapping_reviews` takes `source_codes: Sequence[str]`; the `code_by_id` inversion is gone and `source_code` is selected directly |
| `crawlernest/crawlernest-core/multi_source/pipeline.py` | The only caller — passes `sorted(source_id_map)` |
| `crawlernest/crawlernest-core/multi_source/reviews.py` | **No change.** `MappingReview.key` was already `(source_code, source_entity_id)` |
| `crawlernest/crawlernest-tests/test_mapping_reviews.py` | **No change.** All 22 tests exercise the pure function |
| `crawlernest/crawlernest-tests/test_multi_source_pipeline.py` | `FakeMultiSourceRepository.load_mapping_reviews` now rejects the old `{code: id}` shape, so a regression fails here instead of only against PostgreSQL |
| `crawlernest/scripts/apply_mapping_reviews.py` | `Pending.ranking_source_id` → `source_code`; `load_pending`, `write`, `remaining` read `v_entity_mapping`; conflict target is `(source_code, source_entity_id)`. `mapping_review.ranking_source_id` is filled by a `LEFT JOIN` on `ranking_source`, so a non-ranking source correctly leaves it NULL |
| `crawlernest/scripts/mapping_review_queue.sql` | Reads `warehouse.v_entity_mapping`; the `ranking_source` join is gone |
| `crawlernest/scripts/mapping_review_skeleton.sql` | Same substitution |

`v_entity_mapping` has no `is_active` writer for the admission side yet; that
arrives with phase 4, when the admission resolver starts writing
`warehouse.source_mapping`.

---

## Phase 3 — Java and web (landed)

| File | Change |
|---|---|
| `clawer/review/repository/MappingReviewRepository.java` | `CANDIDATE_SELECT`, `countPending`, `mappingExists` and `saveDecision` all read `warehouse.v_entity_mapping`; the `ranking_source` join is gone from the queue and survives only as the `LEFT JOIN` that fills the legacy `ranking_source_id`. `mappingExists(int, String)` → `(String, String)` |
| `clawer/review/dto/MappingReviewCandidate.java` | Dropped `int rankingSourceId`; `sourceCode` was already carried |
| `clawer/review/dto/MappingReviewDecisionRequest.java` | `Integer rankingSourceId` → `String sourceCode` |
| `clawer/review/service/MappingReviewService.java` | Validates a non-blank `sourceCode`; the save response echoes it back |
| `clawer/review/controller/MappingReviewController.java` | **No change** — it only forwards |
| `src/test/java/clawer/review/service/MappingReviewServiceTest.java` | `new MappingReviewDecisionRequest(402, …)` → `("THE", …)`; `mappingExists`/`saveDecision` stubs take `anyString()` |
| `crawlernest-web/src/app/admin/entity-review/page.tsx` | `rankingSourceId` removed from `ReviewCandidate`; `candidateKey()` and the POST body use `sourceCode` |

**The API contract changed.** `POST /api/v1/admin/mapping-reviews` now takes
`sourceCode` where it took `rankingSourceId`, and `MappingReviewCandidate` no
longer carries `rankingSourceId`. This is an internal admin endpoint behind a
reviewer allowlist, so no external consumer is affected — but any saved request
or bookmarked script using the old field will be refused with
"sourceCode is required."

---

## Phase 4 — admission entity resolution (landed)

`crawlernest_admission_crawler/entity_resolver.py` no longer carries a resolver
of its own. It loads canonical profiles through `EntityResolutionRepository`,
resolves with `EntityResolver`, applies standing decisions, then writes
`warehouse.source_mapping`, `analytics.entity_resolution_event` and the
canonical columns of the admission table.

Measured on the eight seeded snapshot universities: **3/8 → 8/8**, with one
fuzzy match (`UCL (University College London)` → `UCL`, 0.8819) correctly
landing in the review queue.

| File | Change |
|---|---|
| `crawlernest_admission_crawler/entity_resolver.py` | Rewritten around `EntityResolver`; `EntityResolutionSummary` reports exact / normalized / fuzzy / awaiting-review / retired / human-decisions-applied instead of the old canonical-exact and alias-exact pair |
| `crawlernest/crawlernest-core/multi_source/reviews.py` | `apply_mapping_reviews` takes `source_of`, so it applies to `ResolutionResult` (which spells the field `source_name`) as well as `UnifiedRankingRecord` |
| `crawlernest/pipeline/commands/admission.py` | Summary keys and printed lines follow |
| `crawlernest/crawlernest-tests/test_admission_entity_resolution.py` | 23 new tests, registered in `run_tests.py` |

Three things worth knowing:

**`raw_row` is written here, not by the resolver.** The review screen reads the
source's own name and country from `metadata #>> '{raw_row,name}'` and
`{raw_row,location}`. `EntityResolver._build_metadata` does not produce them.
Without `_resolve_row` adding them, every admission row in the queue would
render blank and be unjudgeable.

**Rejections retire the mapping.** `upsert_source_mapping` returns early for an
unresolved result, which is not enough on its own — a mapping written by an
earlier run keeps asserting the match the reviewer threw out, and the queue
keeps offering it. `_deactivate_rejected_mappings` sets `is_active = FALSE`,
mirroring `MultiSourceRepository.deactivate_rejected_mappings`.

**Two different "unresolved" counts.** `unresolved_row_count` counts rows with
no canonical id, including ones a reviewer rejected. The unresolved *report*
excludes those — a rejected entity needs no further resolution work. The CLI
prints the first as `no_canonical` so the two do not read as contradictory.

`apply_mapping_reviews` and `MappingReview` still live under `multi_source`
even though both pipelines now use them. They belong in `entity_resolution`;
moving them is deliberately not bundled into this migration.

## Phase 5 — rename and column extraction (landed)

`warehouse.admission_records_preview` is now `warehouse.admission_record`, and
the fields the recommendation view had been digging out of `raw_payload` with
`->>` and a cast are columns. 28 identifier references moved across Python,
Java, SQL and the Java test fixtures.

Shape as built:

```
source_code            TEXT NOT NULL DEFAULT 'university_site' -> entity_source
source_entity_id       TEXT NOT NULL
degree_level           TEXT NOT NULL DEFAULT 'unknown'   undergraduate|postgraduate|doctoral|unknown
ielts_requirement      DOUBLE PRECISION   0  .. 9
toefl_requirement      INTEGER            0  .. 120
duolingo_requirement   INTEGER            10 .. 160
gpa_requirement        DOUBLE PRECISION   0  .. 4.0
application_deadline   DATE
UNIQUE (source_code, source_entity_id, degree_level)
```

Ranges are taken from `_validate_extracted_fields` in
`crawlernest/crawlernest-admission-crawler/crawlers/university_site.py` so the
`CHECK` cannot reject a value the crawler already accepted. The same bounds are
checked again in `validator.py`, so a bad staging row is reported against its
line number instead of aborting an ingest on a constraint violation.

**`ielts_requirement` stayed `DOUBLE PRECISION`** rather than becoming
`NUMERIC(3,1)` as first planned. `UniversityPreviewRepository` reads it with
`(Double) rs.getObject(...)`; under `NUMERIC` the driver hands back a
`BigDecimal` and that cast throws at runtime, in a path no unit test covers.
`gpa_requirement` matches it for consistency within the table. The `CHECK`
constraints, not the column type, are what actually guard these values.

**The backfills are pattern-guarded, not `NULLIF`-wrapped.** One unparseable
`raw_payload` value would otherwise abort the whole bootstrap. Verified against
a row holding `"deadline": "not-a-date"`, `"gpa_requirement": "n/a"` and
`"degree_level": "masters"`: all three were left alone and the migration
completed.

**`_ensure_table` is gone from `warehouse_writer.py`.** It carried a second
copy of the DDL and created it on demand, which on a fresh database silently
produced a table without the constraints the schema file would have given it.
It now raises and names the bootstrap command instead.

**The upsert reports which branch it took** via `RETURNING (xmax = 0)`. The
old before/after row-count check treated every write as an insert and would
have failed on any run that corrected an existing row.

`deadline_candidates` stays in `raw_payload`. It is one-to-many
(`early` / `final` / `rolling`, see `resolver.py`), and eight sample rows are
not enough evidence to justify a child table. When deadlines become a query
dimension, add `warehouse.admission_deadline` — do not widen this table into
`application_deadline_early`, `_final`, `_rolling`.

### Call sites (30)

**Python defaults** — `crawlernest_admission_crawler/warehouse_writer.py:65`,
`entity_resolver.py:72`, `unresolved_report.py:27`;
`crawlernest/pipeline/convergence_preview.py:54`,
`canonical_university_detail_preview.py:80`; `crawlernest/pipeline/cli.py`
(six defaults); `crawlernest/run_pipeline.py:2486`.

**Python with real SQL** — `crawlernest/core/services/ranking_service.py:86`
(`admission_country` CTE); `warehouse_writer.py::_insert_rows`;
`warehouse_mapper.py::map_staging_rows_to_warehouse_rows` and the
`WarehouseReadyAdmissionRow` dataclass.

**Java main** — `clawer/repository/UniversityPreviewRepository.java` lines 106,
144, 184, 225, 325; `clawer/api/RankingController.java:314`.

**Java test fixtures (these fail loudly, which is the good case)** —
`rankings_integration_setup.sql:96` and
`university_preview_integration_setup.sql:50` each keep their own copy of the
table definition and need the new columns; plus four seed/cleanup files.

**SQL view** — `recommendation_postgresql.sql:106`. Rewrite the
`admission_preview_summary` CTE to read the new columns; the
`NULLIF(COALESCE(raw_payload->>'duolingo_requirement', …))::numeric`
expression disappears entirely.

---

## Phase 6 — crawler to staging (landed)

Two packages had carried the word "admission" for months without touching.
`run_admission_crawl.py` wrote a `CrawlReport` — crawl_status, is_usable, which
fields were missing — and dropped `record.requirements`, so not one extracted
number ever reached a database. The pipeline's only input was one hardcoded MIT
record.

`crawlernest_admission_crawler/crawl_bridge.py` converts the crawler's
`AdmissionRecord` into the pipeline's. It adds no extraction logic: everything
it reports was already being computed and thrown away.

```bash
python3 -m crawlernest.run_pipeline crawl-admission --write-staging
```

| File | Change |
|---|---|
| `crawlernest_admission_crawler/crawl_bridge.py` | New. Drives the crawler, converts records, reports what it skipped |
| `crawlernest_admission_crawler/engine.py` | Drives the bridge instead of the stand-in; anomaly counts come from real `flagged_fields` |
| `crawlernest_admission_crawler/crawlers/example_university.py` | **Deleted.** The hardcoded MIT record it returned is what made the pipeline look like it worked |
| `crawlernest/crawlernest-admission-crawler/site_profiles/universities.py` | `UniversityProfile.country`, populated for all eight. No admission page states its own country, and without it the resolver loses country blocking |
| `crawlernest/pipeline/cli.py`, `run_pipeline.py`, `sample_crawl_exports.py` | `--snapshot-dir`, `--only`, `--rate-limit`, `--live` |
| `crawlernest/crawlernest-tests/test_admission_crawl_bridge.py` | New, registered in CI |
| `tests/test_crawlers.py` | Rewritten — see below |

**The engine is offline by default.** `AdmissionCrawlerEngine()` reads the
checked-in snapshots; reaching real university sites takes `live=True`. The
first version defaulted to live, and `pytest tests/` promptly spent five
minutes crawling eight real universities. A test suite must not do that, and
neither should a bare constructor.

**`--snapshot-dir` filters the candidate URLs.** The crawler falls back to live
HTTP for any URL it has no snapshot for, so simply passing a snapshot directory
still put requests on the wire — measured at 22.8s with real fetches, against
0.3s once only the eight URLs actually on disk were offered.

**Unusable pages do not become rows.** A blocked or empty page yields a record
with no requirements; staging it would assert that a university publishes no
entry requirements at all, which is a different claim from "we could not read
the page". They are counted in the summary instead.

**`tests/test_crawlers.py` was asserting nothing.** Every case read
`any(s in output for s in ["1", "invalid_ielts: 1"])` — which matches the digit
`1` anywhere in the output. They passed because the stand-in printed
`total_records: 1`. Against real crawl output, which contains no `1`, all six
failed. They now check the structure the summary actually promises. Note they
live in `tests/`, which no CI workflow runs; the new bridge tests are in
`crawlernest/crawlernest-tests/` and registered.

---

## Phase 7 — granularity and one mapping table (landed 2026-09-14)

Backup: `~/crawlernest-backups/2026-09-14-admission-granularity/` (full
`pg_dump` plus CSVs of `admission_record`, `source_mapping`, the
`university_site` reviews and every mapping key).

### `warehouse.source_university_mapping` serves every source

`source_code` is now its key (`NOT NULL`, FK → `entity_source`, unique with
`source_entity_id`); `ranking_source_id` is nullable. A composite FK
`(ranking_source_id, source_code) → ranking_source` makes a ranking row's two
keys agree without a trigger (the schema loader cannot run `$$` bodies), and
MATCH SIMPLE skips it for a non-ranking row. Every ranking reader joins on
`ranking_source_id`, so it sees exactly the rows it saw before.

The 8 `university_site` rows in `warehouse.source_mapping` were copied across
once (inactive ones stay inactive; `threshold_used`, `matched_alias_id` and
`review_status` kept in metadata) and the legacy copies set inactive.
`v_entity_mapping` unions the legacy table only for entities the unified table
does not hold, so nothing is queued for review twice.

Writers that had to supply `source_code`: `MultiSourceRepository`
(`upsert_entity_mappings`, which the ranking `upsert_source_university_mappings`
now delegates to), `crawlernest_ranking_crawler/subjects/qs_subject.py`, and the
`test_mapping_provenance` fixture, which also has to register its test source in
`entity_source`.

### `warehouse.admission_record` granularity

| Column | Meaning |
|---|---|
| `faculty`, `programme_name` | as printed; both NULL when the number is not programme-specific |
| `programme_key` | normalised `faculty\|programme`, `''` when both NULL (`admission_programme_key`) |
| `requirement_scope` | `programme` / `faculty` / `institution_minimum` / `unspecified` |
| `intake_year`, `intake_year_basis` | `page_stated` / `deadline_inferred` / `unknown` (year NULL) |
| `fetched_at`, `fetch_mode` | `live` / `snapshot` / `unknown`; what a staleness caveat must name |
| `source_mapping_id` | the mapping that resolved the row, as on `ranking_record` |

Natural key: `UNIQUE NULLS NOT DISTINCT (source_code, source_entity_id,
degree_level, programme_key, intake_year)` (PostgreSQL 15+; CI runs 16). CHECKs
tie scope to the names, year to its basis, `live` to a fetch time, and a mapping
id to a canonical id.

**Every existing row is `unspecified`, intake `unknown`, fetch `unknown`.** That
is the truth about them: the crawler extracts one number per page and records no
programme, intake or fetch time — Imperial's profile even notes its IELTS is
tiered 6.5 / 7.0 by programme. Nothing was inferred in SQL.

### The resolver now meets the ranking standard

`crawlernest_admission_crawler/entity_resolver.py`, in order and before any
write: resolve per page (rows of one page are one entity), apply
`mapping_review`, **refuse** a run where a decision's page came back under a new
id (`refuse_reappeared_reviews`, matched on printed name or URL host — the last
path segment `english-language-requirements` is shared by most universities and
would refuse every run), log decisions whose page is absent, hold mapped pages
on their existing university (`apply_mapping_continuity`). Then one guarded
upsert into the unified table, rejected mappings retired, rows given
`canonical_university_id` and a `source_mapping_id` that credits the same
university or NULL.

Still reading `warehouse.source_mapping`, to move in phase 8:
`clawer/service/DataQualityService.java` (low-confidence counts — admission rows
there are now inactive), `crawlernest-autoeval/runners/run_canonical_diagnostics.py`;
and `crawlernest/scripts/seed_canonical_from_universities.py` still writes it for
the legacy universities seed.

### Before any programme-scoped row is written

Seven files collapse admission rows per university with `MIN()` —
`AdmissionRecordRepository`, `UniversityPreviewRepository`,
`JdbcScopedRankingReadAdapter`, `RecommendationEvidenceService`, the
`admission_preview_summary` CTE in `recommendation_postgresql.sql`,
`convergence_preview.py`, `canonical_university_detail_preview.py`. With one row
per page today they are correct. With several programme rows they would report
the least demanding programme's IELTS as the university's. Phase 8 must switch
them to scope-aware reads before any source writes `programme` rows.

---

## Traps

**The `DO NOTHING` freeze.** `warehouse_writer.py:152` inserts with
`ON CONFLICT … DO NOTHING`. Crawl the same URL a hundred times and the row
stays at whatever the first crawl said. Ranking data upserts; admission data
does not. Entry requirements change yearly, so frozen data is worse than
missing data. Phase 5 must switch this to `DO UPDATE`.

**Both table names can exist at once, and the migration used to skip
silently.** The Java integration tests run against the developer's real
database, and their fixtures do
`CREATE TABLE IF NOT EXISTS warehouse.admission_record`. On any machine that
has run `./mvnw test`, the rename then raises 42P07 — a *duplicate-table*
error, which both schema appliers deliberately swallow. Bootstrap reported
`skipped_existing=2` and exited zero while every row stayed in the old table
and every reader pointed at the empty new one.

`bootstrap_postgres.py` and `pipeline/utils/schema.py` now refuse up front and
name the fix:

```
psql -d <db> -c 'DROP TABLE warehouse.admission_record CASCADE'
```

`CASCADE` is required because `analytics.v_recommendation_candidates_latest`
reads the table; the next bootstrap rebuilds that view. Applying the `.sql` by
hand with `psql` bypasses the check.

That the Java integration tests create and seed tables in the developer's
`clawer` database at all is a separate, pre-existing problem worth its own
fix — they should point at a throwaway database.

**Do not add a backward-compatible view named `admission_records_preview`.**
It looks like a way to avoid touching 30 call sites. But the next bootstrap
runs `ALTER TABLE IF EXISTS warehouse.admission_records_preview RENAME TO
admission_record`, PostgreSQL happily renames the *view*, and the real table
is left uncovered. Silent, and hard to trace. Update the call sites.

**The schema loader is a naive splitter.** `_split_sql_statements` in
`crawlernest/scripts/bootstrap_postgres.py` truncates each line at `--` and
splits on every `;`. Therefore:

- no `DO $$ … $$` blocks in any schema file
- no `--` inside a string literal
- no `;` inside a string literal

**`NULL` in a unique key.** PostgreSQL considers two `NULL`s distinct, so
`UNIQUE (source_code, source_entity_id, degree_level)` with a nullable
`degree_level` does not prevent duplicates — the upsert never finds a conflict
and inserts a new row every run. Hence decision 3.

**Two mapping tables** — resolved for admissions in phase 7. Admission entity
resolution writes only `warehouse.source_university_mapping` now; the legacy
`warehouse.source_mapping` rows for `university_site` are inactive copies. The
table itself remains for the readers listed under phase 7 and the legacy
universities seed.

---

## Verification

```bash
CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \
  python3 crawlernest/crawlernest-tests/run_tests.py
```

```bash
cd crawlernest/servise_for_java && ./mvnw -q compile
```

Schema changes are idempotent: applying them twice must be a no-op. Check
against a scratch database rather than `clawer` before applying for real:

```bash
createdb -h localhost -U test clawer_mig_check
```

Adding a test file does not put it in CI. Register it in the `test_modules`
list in `crawlernest/crawlernest-tests/run_tests.py`.
