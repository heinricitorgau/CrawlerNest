# CLAUDE.md

CrawlerNest — a university ranking data platform. Python crawlers ingest ranking
sources (currently QS only) into a PostgreSQL warehouse, a Spring Boot API serves
read-only aggregated data, and a Next.js frontend displays it.

Development happens on Linux/WSL. All commands below assume a POSIX shell at the
repo root.

## Naming traps (read first)

These names are historical and misspelled. They are load-bearing — do not "fix"
them without a coordinated rename, and remember them when searching:

- `crawlernest/servise_for_java/` — the main Spring Boot API service ("servise" is a typo, kept).
- Java root package is `clawer` (not `crawler`). Grepping for "crawler" will miss all Java code.
- The PostgreSQL database is named `clawer` (user `test`, password `test`, localhost:5432).

## Repository layout (read before moving or searching for files)

The top level holds only `README.md`, `README.zh-TW.md`, `LICENSE` and four folders: `crawlernest/` (all code,
tests and `requirements*.txt`), `docs/` (including `docs/releases/`), `scripts/` (including `scripts/hooks/`) and
`deploy/` (Dockerfile, compose files, systemd units, `.env.example`). Hidden files that git and GitHub require there
(`.github/`, `.gitignore`, `.gitattributes`) stay; this file is `.claude/CLAUDE.md`.

- The crawler packages (`crawlernest_ranking_crawler`, `crawlernest_admission_crawler`, `crawlernest_crawler_core`,
  and the archived `legacy`) are in `crawlernest/packages/` but are imported by their own top-level names.
  `crawlernest/__init__.py`, `crawlernest/pipeline/__init__.py` and `recommendation_engine/engine.py` put that
  directory on `sys.path`; an entry point that imports one of them before importing any of those must add it itself.
  **A missing package can be silent**: `recommendation_engine/engine.py` falls back to `None` on `ImportError` and
  the recommender simply stops reading deadlines. `test_recommendation_engine_deadline_import.py` guards it.
- `legacy/root_models.py` is the old top-level `models.py`. Nothing imports it, and it must not go anywhere on
  `sys.path` ahead of `crawlernest-core`: several `models.py` files share that name and `sys.path` order picks the winner.
- Everything the scripts write that is not source -- `.local/reports/`, `.local/snapshots/`, `.local/backups/`, `.local/logs/`,
  `.local/tmp/`, `.local/crawlernest-samples/`, `.local/snapshot_htmls/` -- lives under the gitignored `.local/`, so the top
  level stays clean. Python builds those paths as `REPO_ROOT / ".local" / "reports"`, shell as `${ROOT_DIR}/.local/reports`;
  the Next.js `snapshot-info` route reads `.local/snapshots/latest_status.json`. A new script that writes to a bare
  `reports/` at the top level is a regression. (`.venv/` and `.pytest_cache/` are hidden by their own names and stay.)

## Live code vs. stale duplicates

- **`crawlernest/packages/crawlernest_ranking_crawler/` (underscores) is the live
  ranking pipeline package.** It is what `crawlernest/run_pipeline.py` imports.
- `crawlernest/crawlernest-ranking-crawler/` (hyphens) was a diverged copy that no
  Python code imports. It is untracked and gitignored now; if it still exists on
  disk, do not edit it.
- Same pattern applies to `crawlernest/packages/crawlernest_admission_crawler/` and
  `crawlernest/packages/crawlernest_crawler_core/` — verify imports before choosing where to edit.
- Build artifacts (`__pycache__/`, `*.pyc`, `crawlernest/clawer.db`, `*.db.bak`)
  were untracked from git and are gitignored, but stale copies may remain on
  disk. Never edit or read these as source.
- Some docs exist in two copies (e.g. `docs/demo/DEMO_SCRIPT_v0.1.md` and
  `docs/releases/v0.1-demo/DEMO_SCRIPT_v0.1.md`). Update both or note the divergence.

## Architecture

```
Python pipeline (crawlernest/run_pipeline.py + crawlernest/packages/crawlernest_ranking_crawler/)
  → PostgreSQL: staging → warehouse.canonical_university → analytics.aggregated_rankings
    (one row per university per year per aggregation_run; source_ranks_json holds
     {"QS": rank, "THE": null, "ARWU": null} — missing sources are null-valued keys)
  → Spring Boot read API  crawlernest/servise_for_java/   (port 8080, package clawer.*)
  → Next.js web           crawlernest/crawlernest-web/    (port 3000, proxies /api/* to 8080)
  → Agent API                                             (port 8090)
```

Core aggregation logic lives in `crawlernest/crawlernest-core/ranking_aggregation/`
(weights, composite score, coverage ratio). Schema DDL is in
`crawlernest/crawlernest-schema/`.

## Commands

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate && pip install -r crawlernest/requirements.txt
python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-user test --pg-password test --pg-database clawer

# Load ranking data
./.venv/bin/python -m crawlernest.run_pipeline run --limit 20 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer

# Start everything (PostgreSQL + API + web)
./scripts/start_localhost.sh

# The Docker stack (copy deploy/.env.example to deploy/.env first)
docker compose -f deploy/docker-compose.yml up --build

# Individual services
cd crawlernest/servise_for_java && ./mvnw -Dmaven.test.skip=true spring-boot:run
cd crawlernest/crawlernest-web && npm run dev

# Verify a Java change compiles
cd crawlernest/servise_for_java && ./mvnw -q compile

# Python tests (adds crawlernest/crawlernest-* module dirs to sys.path)
python3 crawlernest/crawlernest-tests/run_tests.py

# Smoke check the running stack
./scripts/smoke_local_stack.sh
```

CI: seven workflows, eleven jobs — see the table in [README.md](../README.md#continuous-integration).
`crawlernest/crawlernest-tests/` now runs in `python-tests.yml`, in two jobs: fixture
mode, and a PostgreSQL job that opts the database tests in with
`CRAWLERNEST_RUN_PG_TESTS=1`. Locally those tests skip unless you set the same
variable, so a clean local run does not mean the database paths were exercised:

```bash
CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \
  python3 crawlernest/crawlernest-tests/run_tests.py
```

Three committed files are derived from the warehouse: `crawlernest-kb/databases/cross_edition_ranks.csv`,
`qs_the_pairing_2026.json` and the `*_university_aliases_*.json` files. CI cannot hold them against the
warehouse (its database is bootstrapped empty, and the real one is on your machine), and those checks skip
where the warehouse is too small, so a green CI run says nothing about them. This is the gate, and it fails
where the suite would skip:

```bash
./scripts/check_warehouse_drift.sh      # exit 1 on drift, 2 if the database is unreachable
./scripts/install_git_hooks.sh          # once per clone: runs it before every push when the database is reachable
```

`CRAWLERNEST_REQUIRE_WAREHOUSE=1` is what turns the skip into a failure. What CI does check without a database is
that the export code and the committed CSV agree (`TestTheExportCodeAndTheCommittedFileAgree`).

`run_tests.py` names its modules explicitly. Adding a test file does not put it in
CI — several sat unrun for months that way. Add it to the `test_modules` list.

## Behavioral policies that constrain changes

- **Analytics endpoints are strictly read-only.** No mutations, no pipeline
  triggers from the API layer.
- **Every analytics response must include a `caveats` array** disclosing data
  limitations. This is an explicit honesty contract — see
  `docs/analytics/ANALYTICS_EXPLAINABILITY.md`. Never remove or soften caveats
  to make output look better.
- **No black-box scores.** Confidence is derived mechanically from source count
  (3 sources = high, 2 = medium, 1 = low). Do not set confidence manually.
- **Caveat strings have one definition per language, and a test that they
  agree.** `crawlernest/core/caveats.py` (Python), `AnalyticsService` constants
  (Java, referenced by `AnalyticsController` and `RecommendationEvidenceService`
  rather than repeated), `crawlernest-web/src/lib/caveatMessages.ts` (frontend),
  and `docs/analytics/ANALYTICS_EXPLAINABILITY.md` (prose). Change one and
  `crawlernest-tests/test_caveat_contract.py` tells you which of the others
  drifted — it matches exact substrings, so a reworded copy fails.
- **The ranking crawler implements QS only**
  (`crawlernest/packages/crawlernest_ranking_crawler/sources/qs.py`), but the warehouse is no longer
  QS-only: as of 2026-10-02 `analytics.aggregated_rankings` carries 9,864 QS, 1,712 THE
  and 955 ARWU ranks for 2026 (2025: 1,512 / 1,663 / 961). THE and ARWU also hold
  every edition 2015–2024. QS holds 2016, 2018–2020 and 2022–2024, read from
  Internet Archive captures (`crawlernest-jobs/qs_archive_loader.py`, pinned in
  `crawlernest-kb/qs_archive/manifest.json`) with `rank` stored as the lower bound
  of the printed rank; it has no 2015, 2017 or 2021. Those editions carry their own
  caveat (`DATASET_ARCHIVE_EDITIONS`). The QS figure sums every universe type (global, region,
  regional, special, subject); THE and ARWU exist only in `global`, where QS
  is 1,502 of 2,240 universities (README quotes the `global` figures).
  Coverage is partial, so code must still handle a missing
  source rank — but as *our* gap, never as the source declining to rank. Read
  the ingested set from `crawlernest/core/dataset.py:DATASET_SOURCES`; do not
  write "QS only" into new code or copy.
- Model estimates (`analytics.ml_predictions`, populated from the edition-verified
  QS 2026 snapshot: 787 overall-score and 1,483 disagreement rows) are read through `crawlernest/core/services/ml_service.py`
  and `crawlernest/agent/tools/ml_tools.py`. Every row keeps `isEstimated` —
  that field, not the caveat text, is what arms the `estimate_credited_to_source`
  provenance rule. Never surface a predicted value without it.

## Wikipedia introductions

The "About" section of a university page is the English Wikipedia article matched to that university
(`warehouse.university_wikipedia_article`, served by `GET /api/v1/universities/{id}/wikipedia`). The table is a copy
of committed files in `crawlernest-kb/wikipedia/en/`; `crawlernest-jobs/wikipedia_profile_loader.py` writes them:

```bash
./.venv/bin/python crawlernest/crawlernest-jobs/wikipedia_profile_loader.py match    # warehouse + Wikidata -> matches.json
./.venv/bin/python crawlernest/crawlernest-jobs/wikipedia_profile_loader.py fetch    # Wikipedia -> articles/*.jsonl.gz
./.venv/bin/python crawlernest/crawlernest-jobs/wikipedia_profile_loader.py ingest   # files -> PostgreSQL, no network
```

- **A university is matched by publisher id, exact title or exact label -- never by a similar name.** An unmatched
  university shows no introduction, and `matches.json` says why. Do not add a fuzzy tier to raise coverage; correct a
  single university in `overrides.json`.
- **The text is Wikipedia's (CC BY-SA 4.0), not warehouse data.** Whatever renders it shows the article link, the
  licence and the API's `notice`. Nothing may compute from it or feed it to the recommender or agent as fact: an
  article quotes ranks from editions the warehouse does not hold.
- A fresh database has an empty table until `ingest` is run; `bootstrap-postgres` creates the table only.

## Entity resolution traps

- Two universities on one canonical keep one rank per edition and silently drop the other. Name normalisation
  treats "Miami University" and "University of Miami" as the same string, and a fuzzy match (0.85-0.90) can attach
  a new source id to a different university. After any backfill that adds editions, run
  `crawlernest/scripts/split_false_entity_merges.py verify` (read-only) and read
  `docs/data/ENTITY_SPLIT_2026-10-03.md`. Creating a canonical can itself attract fuzzy matches: rehearse on a copy.
- The opposite defect is one university carried as two records: a source prints its English name, the record holds
  its native one, and the resolver opens a second record. Nothing collides, so nothing flags it; each row just has fewer
  sources than the university has. 112 were merged on 2026-10-12 (`crawlernest/scripts/merge_duplicate_canonicals.py`,
  `docs/data/DUPLICATE_MERGE_2026-10-12.md`). After a backfill, re-run `wikipedia_profile_loader.py match` and read the
  `shared_with` entries of `matches.json`: two active records on one Wikipedia article is this defect.
- An alias outranks a display name and an exact alias match ignores the country. Before writing aliases in bulk, ask
  `entity_resolution/alias_safety.py`; a name with a trailing parenthesis is indexed without it as well.
- `ranking_decision_preview` is a derived table written with `ON CONFLICT DO NOTHING`; re-running its command does not
  repair a stale row. It joins on the canonical's `display_name_normalized`, so renaming a canonical needs its rows rewritten.

## Key docs

- `docs/GETTING_STARTED.md` — canonical setup steps and troubleshooting
- `docs/ARCHITECTURE_OVERVIEW.md`, `docs/DATA_FLOW.md`, `docs/API_SURFACE.md`
- `docs/REPOSITORY_MAP.md` — directory guide (but see the stale-duplicate warning above)
- `crawlernest/crawlernest-web/CLAUDE.md` — subproject-specific guidance

## Debugging order

Data problems are almost always upstream of the UI. When something looks wrong
on a page, check in this order: warehouse/analytics tables → Java API response
(`curl localhost:8080/api/v1/...`) → Next.js proxy route → React component.
