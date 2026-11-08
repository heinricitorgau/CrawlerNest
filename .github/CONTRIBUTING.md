# Contributing to CrawlerNest

Thanks for helping. This guide covers the local setup, how to add a university to the admission crawler, and what a
pull request needs. [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md) has the full setup and troubleshooting.

## Local setup

You need Python 3.11+, PostgreSQL 14+, JDK 17 and Node.js 20.9+ (`.nvmrc`). Development happens on Linux or WSL;
run every command from the repository root.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r crawlernest/requirements.txt

# PostgreSQL with the expected role and database (or create role `test` / database `clawer` yourself)
docker compose -f deploy/docker-compose.postgres.yml up -d
python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-user test --pg-password test --pg-database clawer

# Load some ranking data, then start PostgreSQL, the API (8080) and the web app (3000)
./.venv/bin/python -m crawlernest.run_pipeline run --limit 20 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer
./scripts/start_localhost.sh
./scripts/smoke_local_stack.sh
```

Some names are misspelled on purpose and must stay that way: the API lives in `crawlernest/servise_for_java/`, its
Java package is `clawer`, and so is the database.

## Adding a university to the admission crawler

Rankings come from whole-source crawlers (QS, THE, ARWU), so a university missing from the rankings is a data issue,
not a new crawler -- open a **Data issue** instead. The per-university crawler is the admission crawler, which reads
English-language and entry requirements from each university's own site.

1. Add a `UniversityProfile` to `UNIVERSITY_PROFILES` in
   `crawlernest/crawlernest-admission-crawler/site_profiles/universities.py`:
   - a short lowercase key, e.g. `"edinburgh"`;
   - one to three `candidate_urls` in priority order -- prefer a dedicated English-language or entry-requirements page
     over the admissions home page;
   - `country`, which entity resolution needs to match the university confidently;
   - `expects_language_score=False` if the university does not ask for IELTS/TOEFL.
2. Crawl it live, once, politely:

   ```bash
   ./.venv/bin/python crawlernest/crawlernest-admission-crawler/scripts/run_admission_crawl.py --only edinburgh
   ```

3. Save the page that worked into `crawlernest/crawlernest-admission-crawler/crawl_snapshots/`, named as
   `_url_to_slug(url) + ".html"` (see `crawlers/university_site.py`). CI crawls these snapshots, never the network.
4. Run the admission tests and check that the new university produces a record:

   ```bash
   python3 crawlernest/crawlernest-tests/run_tests.py
   ```

Respect each site's `robots.txt` and terms, and keep the default rate limit.

## Pull requests

- Branch from `main`, keep one change per PR, and fill in the checklist in the PR template.
- Run `python3 crawlernest/crawlernest-tests/run_tests.py`; for a Java change, `cd crawlernest/servise_for_java && ./mvnw -q compile`;
  for a web change, `cd crawlernest/crawlernest-web && npm run build`.
- A new test file must be added to the `test_modules` list in `run_tests.py`, or CI never runs it.
- Analytics endpoints are read-only, and every analytics response keeps its `caveats` array. Do not remove or soften a
  caveat to make output look better; caveat strings are defined once per language and
  `test_caveat_contract.py` checks that they agree.
- Confidence is derived from the number of sources. Do not set it by hand.
- Nothing the scripts write goes at the top level: generated files belong under `.local/`.
- Describe schema or aggregation-formula changes in the PR, and update `docs/` when you add a script or pipeline step.

By contributing you agree that your contribution is licensed under the [Apache License 2.0](../LICENSE), and that you
follow the [Code of Conduct](CODE_OF_CONDUCT.md).
