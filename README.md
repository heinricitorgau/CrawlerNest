# CrawlerNest

**English** · [繁體中文](README.zh-TW.md)

[![Agent Tests](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/agent-tests.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/agent-tests.yml)
[![ML Tests](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/ml-tests.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/ml-tests.yml)
[![Data Quality](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/data-quality.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/data-quality.yml)
[![Release Smoke](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/release-smoke.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/release-smoke.yml)
[![API Tests](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/api-tests.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/api-tests.yml)
[![Python Tests](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/python-tests.yml/badge.svg)](https://github.com/heinricitorgau/University-Data-Infrastructure-Web-Platform/actions/workflows/python-tests.yml)

An end-to-end university data infrastructure and web platform. It aggregates global and subject rankings from QS, THE, and ARWU into a single warehouse, exposes an explainability-first API, and delivers a Next.js frontend for browsing, comparing, and saving universities.

The system is data-first: crawlers and pipelines write canonical records into PostgreSQL, and the UI reads only from analytics views — never directly from raw tables.

---

## Contents

- [What It Does](#what-it-does)
- [What it looks like](#what-it-looks-like)
- [Architecture](#architecture)
- [Modelling layer](#modelling-layer)
- [Repository Layout](#repository-layout)
- [Getting Started](#getting-started)
- [Documentation](#documentation)
- [Continuous Integration](#continuous-integration)
- [Current State](#current-state)
- [License](#license)

---

## What It Does

- **Multi-source rankings** — 1,499 universities with all three sources ingested: QS 1,499, THE 1,080, ARWU 686
- **Subject rankings** — QS 2026 subject data for Computer Science, Electrical Engineering, Business & Management
- **Explainability** — every ranking and recommendation comes with a source comparison, confidence level, and evidence chain
- **Recommendations** — filter universities by region, rank tier, and subject; export a named plan
- **Analytics** — year-over-year rank movement, cross-source disagreement, data quality diagnostics
- **Modelling** — a feature layer over the nine QS indicators, with the withheld
  `Overall Score` of ranks 601–1503 as a supervised target
- **Identity layer** — session-based accounts, saved universities, saved recommendation plans

---

## What it looks like

The rankings browser, reading 1,499 aggregated universities out of the
warehouse:

![Rankings browser](docs/assets/screenshots/rankings.png)

The analytics page, where the honesty contract is visible rather than just
documented — the single-year limitation is stated at the top, and source
coverage shows exactly which of the three ranking bodies actually contributed:

![Analytics](docs/assets/screenshots/analytics.png)

Both captured from a local run against the real database, not mockups.

---

## Architecture

```mermaid
flowchart LR
    sources["QS / THE / ARWU"]
    ingestion["Python crawlers\n& normalization"]
    warehouse[("PostgreSQL\nwarehouse")]
    analytics[("Analytics\nviews")]
    api["Spring Boot API\n:8080"]
    frontend["Next.js\n:3000"]

    sources --> ingestion --> warehouse --> analytics --> api --> frontend
```

**Tech stack:** Python · PostgreSQL · Spring Boot (Java 17) · Next.js (React) · Tailwind CSS

---

## Modelling layer

QS publishes nine component indicators for all 1,503 universities in the 2026
snapshot, but the `Overall Score` only for ranks 1–600. That asymmetry is a
supervised learning problem sitting in the data:

```
rank    1– 600  →  score published   →    600 labelled rows  (training set)
rank  601–1503  →  score withheld    →    903 unlabelled rows (inference set)
```

Exploratory analysis of that split produced the finding that shapes the whole
modelling design:

![QS universities in indicator space](crawlernest/crawlernest-ml/artifacts/eda/pca_scatter.png)

PC1 alone explains 50.7% of the variance and orders the labelled universities
almost monotonically by rank. But the 903 universities we would predict pile up
at the low end of PC1, where training data is sparse — every indicator differs
between the two groups by 0.67 to 1.91 pooled standard deviations. **Predicting
the withheld scores is extrapolation, not interpolation.**

So the model does not get to report a flattering cross-validated error and call
it accuracy. Cross-validation measures how well it recovers QS's scoring
function; a per-prediction support flag decides which estimates are publishable;
and Spearman correlation against the published ranks of the 903 provides the
only external validation available in the shifted region — the scores are
unknown there, but the ordering is not.

Two results came out of it:

**The published weighting is recoverable from the data.** A linear fit on the
raw indicators reproduces QS's documented weighting to a mean absolute error of
0.0006 — Academic Reputation 0.2996 against a published 0.30, Citations per
Faculty 0.1992 against 0.20, and so on across all nine. That makes this system
identification rather than forecasting, and the resulting R² of 0.9999 is
reported as "the formula was recovered", not as predictive accuracy.

**Preprocessing mattered more than the model.** The first pipeline used median
imputation and scored Spearman 0.9551 against the published ranks of the 903.
Holding the weights fixed — they differ from QS's by at most 0.0008 — and only
renormalising over available indicators instead of imputing moved that to
0.9755. Median imputation borrows values from a training distribution whose
medians run three to five times higher than the withheld tail. Cross-validation
alone would have shipped the worse pipeline; only the out-of-distribution check
caught it.

Estimates are stored and labelled as estimates. Nothing in the modelling layer
writes to `analytics.aggregated_rankings` or changes a published rank, and 27%
of the inference set is flagged as outside the model's support.

→ **[crawlernest/crawlernest-ml/](crawlernest/crawlernest-ml/)** — feature
contract, EDA, metrics, and model cards.

---

## Repository Layout

```
crawlernest/
  crawlernest-web/          Next.js frontend
  servise_for_java/         Spring Boot API
  crawlernest-core/         canonical resolution, aggregation
  crawlernest-ml/           feature layer, EDA, and models over the QS indicators
  pipeline/                 CLI entry points
  crawlernest-normalization/ C-language CSV normalizer (research component)
  crawlernest-agents/       AI dev agent collection (readonly, optional)
crawlernest_ranking_crawler/ Python ranking ingestion package
crawlernest_admission_crawler/ Python admission ingestion package
docs/                       architecture, operations, release docs
scripts/                    startup, smoke checks, operational automation
tests/                      integration tests
```

---

## Getting Started

**Prerequisites**

| Dependency | Version |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 14+ |
| Java JDK | 17 |
| Node.js | ≥ 20.9 |
| Maven | bundled via `mvnw` |

First-time setup (fresh clone → runnable, one command):

```bash
./scripts/setup_from_scratch.sh
```

The script creates the Python venv, installs dependencies, starts PostgreSQL
(local install or Docker via `docker-compose.postgres.yml`), bootstraps the
schema, runs the first data crawl, and installs frontend dependencies. It is
idempotent — re-run it after fixing whatever it reports.

Then start everything:

```bash
./scripts/start_localhost.sh
```

→ **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** — the same steps done
manually, plus subject rankings and troubleshooting.

### Run your own data

**This repository ships with no ranking data.** Every deployment crawls its
own data directly from the ranking sources:

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer
```

- Crawling is polite by default: **10 seconds between requests** (tune with
  `--request-delay`, but stay respectful). Check the source site's
  `robots.txt` and terms of use before increasing crawl volume.
- If a live fetch fails, the pipeline falls back to your most recent local
  snapshot under `crawlernest/crawlernest-kb/` (snapshots are created on each
  successful run and are not committed to git).
- The crawl writes staging → warehouse → analytics; the UI reads only
  analytics views. Re-running is safe and idempotent per year/source.

---

## Documentation

| Topic | Doc |
|-------|-----|
| Architecture | [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md) |
| Repository map | [docs/REPOSITORY_MAP.md](docs/REPOSITORY_MAP.md) |
| Data flow | [docs/DATA_FLOW.md](docs/DATA_FLOW.md) |
| API surface | [docs/API_SURFACE.md](docs/API_SURFACE.md) |
| Operational runbook | [docs/operational/OPERATIONAL_RUNBOOK.md](docs/operational/OPERATIONAL_RUNBOOK.md) |
| Auth limitations | [docs/AUTH_LIMITATIONS.md](docs/AUTH_LIMITATIONS.md) |
| Local troubleshooting | [docs/LOCAL_TROUBLESHOOTING.md](docs/LOCAL_TROUBLESHOOTING.md) |
| Local LLM (ds4) | [docs/DS4_LOCAL_MODEL.md](docs/DS4_LOCAL_MODEL.md) — natural-language answers for recommendation, ranking, lookup, and data-query tasks via a local or remote ds4 model (env config, remote host + SSH-tunnel/auth setup) |
| All docs | [docs/README.md](docs/README.md) |

---

## Continuous Integration

Six workflows, ten jobs. What each one is worth depends on whether it can fail,
so that is what this table records rather than a list of names.

| Workflow | What it actually executes |
|---|---|
| **Agent Tests** | 126 tests over the web-agent generation layer, then the faithfulness eval across all 55 golden cases. Both mechanical verification signals — the faithfulness rules and the provenance/absence/completeness checker — are scored as detectors, with false positives on clean text reported separately from recall. |
| **ML Tests** | Three jobs. Feature-layer invariants and a metrics regression gate that retrains both models from the committed snapshot and fails on a real drop. A serving job that writes predictions to a throwaway PostgreSQL, verifies the rows, then *scores* them against the published data each target can be checked against — rank order for the estimated scores, observed disagreement for the probabilities. A MATLAB job that installs MATLAB, re-executes `run_qs_eda.m`, and compares the fresh output both against Python and against the committed artifacts. |
| **Python Tests** | Two jobs. Fixture mode with no services, and a PostgreSQL job that runs the opt-in database tests — the aggregation maths, source-weight consistency, the superseded-row prune, and ingest idempotency. Also runs weekly on a schedule, because one failure here was caused by time passing rather than by a commit. |
| **API Tests** | The Spring Boot suite against a real PostgreSQL service, 97 tests, with the surefire reports uploaded as artifacts. |
| **Release Smoke** | Two jobs. Build artefacts — Java compile, Next.js build, Python syntax, readonly fixtures — and an analytics-bridge job that bootstraps PostgreSQL, seeds six universities, runs the warehouse→analytics bridge twice, starts Spring Boot, and checks that `/api/v1/rankings` serves what was written, followed by the endpoint liveness checks. |
| **Data Quality** | Validates the golden regression dataset and the CI fixture files, then runs the ranking-regression and failure-summary runners in fixture mode — no database, no network. |

Two things this deliberately does *not* claim:

- **A skip is not a pass.** Several of these checks used to skip silently — the
  PostgreSQL tests had no database, the API endpoint checks had no server, the
  MATLAB sources were never re-executed. Each now runs somewhere that cannot skip
  it, and the jobs that legitimately skip say so in their names.
- **Green means the checks ran, not that the system is correct.** The gaps that
  remain are recorded as limits in
  [`crawlernest-ml/README.md`](crawlernest/crawlernest-ml/README.md), not hidden
  behind a passing badge.

The full local suite, including the opt-in PostgreSQL tests:

```bash
CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \
  python3 crawlernest/crawlernest-tests/run_tests.py
```

---

## Current State

CrawlerNest v0.1 is an operational MVP — reproducible and demonstrable, not a production deployment.

- All three ranking sources are ingested: QS 1,499, THE 1,080, ARWU 686
- 573 universities reach three sources (confidence high); 306 remain single-source (low)
- Entity resolution still has gaps — 419 universities carry no THE rank and 291 ARWU entities are unmatched. What rules can do safely has been done; the rest are renames, abbreviation-only forms and campus qualifiers that need a human, one at a time
- A missing rank is disclosed as **our** gap — not ingested, or not matched — rather than as the source declining to rank the university
- The agent page defaults to a mock provider and does not write to the database

Release notes: [docs/release/RELEASE_NOTES_v0.1.md](docs/release/RELEASE_NOTES_v0.1.md)

---

## License

[Apache License 2.0](LICENSE).

The ranking data this platform ingests belongs to QS, Times Higher Education and
ShanghaiRanking, and is not covered by that licence. The committed snapshots are
here so the pipeline and the models are reproducible; anything you publish from
them is subject to each source's own terms.
