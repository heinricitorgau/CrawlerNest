# CI Pipelines

GitHub Actions workflows for CrawlerNest. Both pipelines run on every push and pull request to `main`; the data-quality workflow also runs on a weekly schedule.

---

## Workflows

### `release-smoke.yml` — Release Smoke

**Trigger**: push/PR to `main`

Validates that the codebase compiles and builds without errors. Does **not** require a live database or running services.

| Step | What it checks |
|------|----------------|
| Spring Boot compile | `mvnw compile` — no Java errors |
| Next.js build | `npm run build` — no TS/build errors |
| Python syntax | `py_compile` on all runner scripts |
| smoke_release.sh | End-to-end smoke script (skips live API check in CI) |

### `data-quality.yml` — Data Quality

**Trigger**: push/PR to `main` + weekly on Sundays at 04:00 UTC

Validates data quality assertions using committed fixtures — no live PostgreSQL required.

| Step | What it checks |
|------|----------------|
| Python syntax | All autoeval runners compile |
| Golden dataset validation | `golden.json` structure is valid |
| CI fixture validation | `db_state.json` and `snapshot_fixture.json` are valid |
| Ranking regression (fixture mode) | All golden assertions pass against `ci_fixtures/db_state.json` |
| Failure summary | `build_failure_summary.py` runs against `snapshot_fixture.json` |

**Uploaded artifacts** (retained 14 days):
- `regression_result.json` — full regression output with assertion details
- `ci_failure_summary.md` — human-readable summary report

---

## Fixture Mode

Both CI workflows run **without a live database**. The key design:

- `run_ranking_regression.py --fixture-file PATH` reads a JSON list of university records instead of querying PostgreSQL. The assertion logic (`run_assertions()`) is identical — only the data source changes.
- `build_failure_summary.py --snapshot-file PATH` reads a committed snapshot fixture instead of `snapshots/latest_status.json`.

Fixture files live at:
```
crawlernest/crawlernest-autoeval/datasets/ci_fixtures/
  db_state.json          # 5 universities with ranks and source_ranks_json
  snapshot_fixture.json  # compact status snapshot for summary generation
```

When real data changes (e.g. a new top-10 university, a rank shift), update both the fixture and `golden.json` in the same PR.

---

## Local Reproduction

Use `scripts/run_ci_locally.sh` to reproduce both CI workflows on your machine without a running database:

```bash
bash scripts/run_ci_locally.sh
```

The script runs:
1. `smoke_release.sh` — Spring Boot compile + Next.js build + Python syntax
2. Ranking regression in fixture mode
3. Failure summary in snapshot fixture mode

For individual steps:

```bash
# Regression fixture mode only
python3 crawlernest/crawlernest-autoeval/runners/run_ranking_regression.py \
  --fixture-file crawlernest/crawlernest-autoeval/datasets/ci_fixtures/db_state.json

# Failure summary with fixture snapshot
python3 scripts/build_failure_summary.py \
  --snapshot-file crawlernest/crawlernest-autoeval/datasets/ci_fixtures/snapshot_fixture.json

# Spring Boot compile only
cd crawlernest/servise_for_java && ./mvnw compile -q

# Next.js build only
cd crawlernest/crawlernest-web && npm run build
```

---

## Artifact Locations

| Artifact | CI path | Local path |
|----------|---------|------------|
| Regression result (JSON) | `data-quality-report/regression_result.json` | `/tmp/regression_result.json` |
| CI failure summary | `data-quality-report/ci_failure_summary.md` | `/tmp/ci_failure_summary.md` |
| Live failure summary | — | `reports/latest_failure_summary.md` |
| Live snapshot | — | `snapshots/latest_status.json` |

Download CI artifacts from **Actions → data-quality run → Artifacts → data-quality-report**.

---

## Failure Debugging

### `release-smoke` fails

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Spring Boot compile error | Java syntax error or missing dependency | Fix the compile error; check `pom.xml` |
| Next.js build error | TypeScript type error or missing import | Run `npm run build` locally and fix |
| Python syntax error | `SyntaxError` in a runner script | Run `python3 -m py_compile <file>` locally |

### `data-quality` fails

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `golden.json` validation fails | Missing required key in an entry | Ensure all entries have `id`, `university_name_pattern`, `assertions` |
| Regression assertion fails | Rank in `db_state.json` exceeds `display_rank_max` in golden | Update `db_state.json` rank or relax the golden assertion |
| `snapshot_fixture.json` invalid | Missing required field | Ensure `aggregated_count` and other expected keys are present |
| Failure summary crashes | Import error in `build_failure_summary.py` | Run Python syntax check locally |

---

## PR Verification Flow

Before merging a PR:

1. Check the **release-smoke** check is green on the PR.
2. Check the **data-quality** check is green on the PR.
3. If data changed (new rankings, schema update): update `ci_fixtures/db_state.json` and `golden.json`, confirm regression still passes.
4. If a new runner script was added: add it to the Python syntax step in `data-quality.yml`.

---

## Adding a New Regression Assertion

1. Add the entry to `crawlernest/crawlernest-autoeval/datasets/ranking_regression/golden.json`.
2. Add a matching university record to `crawlernest/crawlernest-autoeval/datasets/ci_fixtures/db_state.json` (with rank within the assertion's `display_rank_max`).
3. Run `bash scripts/run_ci_locally.sh` to confirm the assertion passes in fixture mode.
4. Open a PR — CI will enforce it going forward.
