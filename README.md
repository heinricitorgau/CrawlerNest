# CrawlerNest

CrawlerNest is an end-to-end university data infrastructure and web platform for global university rankings, subject rankings, admissions signals, and local exploration workflows.

The project is data-first: the UI reads from warehouse and analytics views, while crawlers and pipelines prepare canonical records in PostgreSQL.

## Quick Start

Use this path for a full local run.

### 1. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL

Recommended with Docker:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

If Docker is not installed:

```bash
brew install --cask docker
```

Local PostgreSQL also works with:

```text
database: clawer
user: test
host: localhost
port: 5432
```

### 3. Bootstrap schemas and seed data

Run this once in a new environment. It is safe to rerun.

```bash
python3 -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-user test \
  --pg-database clawer
```

### 4. Initialize ranking data

The web app will be empty until pipeline data exists.

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-database clawer
```

### 5. Start local services

```bash
./scripts/start_localhost.sh
```

The script starts the local API and web app using the project defaults.

## Service URLs

```text
Web: http://localhost:3000
API: http://localhost:8080
Agent API: http://localhost:8090
```

Main pages:

```text
Global rankings: http://localhost:3000/rankings
Subject rankings: http://localhost:3000/subject-rankings
Agent: http://localhost:3000/agent
```

## Subject Rankings MVP

Subject rankings are implemented as a parallel read path, not as an extension of global ranking aggregation.

Current MVP support:

```text
source: QS
year: 2026
subjects:
  - computer-science
  - electrical-engineering
```

Load QS subject ranking data:

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject computer-science \
  --year 2026 \
  --pg-user test \
  --pg-database clawer
```

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject electrical-engineering \
  --year 2026 \
  --pg-user test \
  --pg-database clawer
```

Subject ranking API examples:

```bash
curl "http://localhost:8080/api/v1/subject-rankings/subjects"
curl "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&year=2026&page=1&pageSize=20"
```

Web proxy examples:

```bash
curl "http://localhost:3000/api/subject-rankings/subjects"
curl "http://localhost:3000/api/subject-rankings?subject=computer-science&year=2026&page=1&pageSize=20"
```

## Data Visibility

Global ranking UI reads from:

```text
warehouse.ranking_record
analytics.v_aggregated_rankings_latest
```

Subject ranking UI reads from:

```text
warehouse.subject_ranking_record
analytics.v_subject_rankings_latest
```

Raw and staging tables are pipeline inputs. They are not shown directly in the product UI.

## Manual Development

Start the Spring Boot API:

```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

Start the Next.js web app:

```bash
cd crawlernest/crawlernest-web
npm install
npm run dev
```

Run selected checks:

```bash
python3 crawlernest/scripts/smoke_subject_rankings.py
cd crawlernest/crawlernest-web && npm run build
cd crawlernest/servise_for_java && ./mvnw -q -Dtest=SubjectRankingApiIntegrationTest test
```

## Common Issues

### Port 8080 is already in use

```bash
lsof -i :8080
kill -9 <PID>
```

### The UI has no data

Run the pipeline first, then reload the page:

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-database clawer
```

For subject rankings, also run the subject loader for the subject you want to browse.

### The subject ranking page loads but the table is empty

Check that the subject pipeline wrote rows and that the Java API is running:

```bash
python3 crawlernest/scripts/smoke_subject_rankings.py
curl "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&year=2026"
```

### Docker is not available

Install Docker Desktop:

```bash
brew install --cask docker
```

## Recommended Workflow

```text
1. Start PostgreSQL
2. Run the data pipeline
3. Start API and web services
4. Open /rankings or /subject-rankings
5. Debug from warehouse/analytics views before debugging UI
```

CrawlerNest is correctness-first. If something looks wrong, verify the data pipeline and warehouse views before changing the product layer.
