# CrawlerNest

English version: [README.md](README.md)

CrawlerNest 是一套端到端的大學資料基礎設施與網站平台。它把分散的排名與 admissions 資料，轉成結構化 warehouse records、canonical university identity、可解釋 ranking evidence，以及面向產品的 decision support。

目前主線採取 correctness-first：

```text
crawl -> extract -> normalize -> write -> warehouse -> API -> web
```

Agent 與 AutoEval 能力已存在，但它們屬於開發輔助系統，不擁有 production truth。

## 目前狀態

截至 2026 年 4 月，CrawlerNest 最適合被理解成三個區域：

- **Active data pipeline：** QS / THE / ARWU ranking ingestion、admission pilot ingestion、normalization、warehouse writes、deterministic entity resolution、API 與 web product。
- **Controlled expansion：** admission enrichment、multi-universe aggregation、comparison，以及基本 explainable recommendation。
- **Development support：** Python agent runtime、Web Agent / Dev Agent split、mini-agent runtime，以及 AutoEval-assisted extractor improvement。

CrawlerNest 之後也會與一個 sibling development-support repo 一起演進：

```text
../crawlernest-agents
```

該 repo 是 CrawlerNest 專用的小型 AI-assisted development system，包含 repo onboarding、code review、data pipeline engineering、PostgreSQL tuning、workflow architecture、debugging/reliability 與 technical writing agents。它是工程協作輔助 repo，不是 production runtime，也不是 production truth source。

工程順序刻意維持嚴格：

1. 先穩定 crawl 與 extraction
2. 再穩定 normalization 與 canonical mapping
3. 再正式化 warehouse 與 API contracts
4. 再建立 admission-aware recommendation
5. 最後才在資料路徑可靠後擴大 agent autonomy

## 產品介面

網站目前包含：

- rankings browser
- university detail pages
- recommendation flow
- compare page
- preview university page
- web-facing `/agent` page，並具備 deterministic fallback behavior

後端 API 目前提供：

- rankings 與 ranking evidence
- university detail
- admissions context
- recommendations
- comparison data
- canonical university preview data

## 決策產品層

CrawlerNest 的 recommendation surface 現在更接近一個決策產品，而不是單純的分數清單。Recommendation engine 仍然維持 deterministic scoring、filtering 與 ranking，但產品層會在結果外加上簡潔、可解釋的 decision surfaces：

- `decisionOutput` 說明單一大學的建議動作。
- `applicationPlans` 比較 balanced、conservative、aggressive 三種申請策略。
- `decisionSummary` 匯出結構化決策紀錄。
- `decisionSummaryCompact` 提供 UI、assistant reply 與 text export 共用的一行產品摘要。
- `admissionResolved` 只暴露 admission requirement 的 trust metadata，不改變推薦邏輯。

Admission data 會被視為 signal，而不是絕對事實。目前 trust path 是：

```text
raw extraction
  -> AdmissionSignal
  -> validation
  -> resolved admission field
  -> recommendation metadata
  -> decision messaging / UI / export
```

這一層刻意採取保守設計：

- conflicting requirement signals 會保留並顯示
- low-confidence requirement signals 會出現在 decision messaging
- consistent high-confidence signals 會提升解釋清楚度
- admission trust metadata 不會改變 scoring、ranking 或 filtering

在 web product 中，這會呈現為 compact admission signal badges、decision summary banner、assistant summary text，以及可匯出的 decision snapshot。

## Repository Layout

CrawlerNest 採用外層 repo 加內層產品 workspace 的結構。

```text
repo-root/
├── README.md / README.zh-TW.md
├── docs/
├── crawlernest/                       # canonical product workspace
├── crawlernest-samples/               # outer sample artifacts
├── deployment-support/
├── legacy/
└── docker-compose.postgres.yml
```

`crawlernest/` 內的重要路徑：

```text
crawlernest/run_pipeline.py            # Python pipeline 主入口
crawlernest/run_platform.py            # modular platform bootstrap
crawlernest/pipeline/                  # command routing 與 pipeline stages
crawlernest/crawlernest-ranking-crawler/
crawlernest/crawlernest-admission-crawler/
crawlernest/crawlernest-crawler-core/  # shared crawler runtime primitives
crawlernest/crawlernest-core/          # domain engines
crawlernest/crawlernest-schema/        # PostgreSQL / SQLite schema assets
crawlernest/servise_for_java/          # Spring Boot API；名稱是歷史拼字
crawlernest/crawlernest-web/           # Next.js frontend
crawlernest/agent/                     # development-support agent runtime
crawlernest/crawlernest-mini-agent/    # standalone mini-agent runtime
crawlernest/crawlernest-autoeval/      # extractor evaluation workflow
```

完整目錄地圖請看 [Repository Structure](docs/architecture/REPO_STRUCTURE.md)。

## 架構

Canonical architecture 文件是：

- [System And Engine Architecture](docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md)

目前 production-oriented path 是：

```text
External Sources
  -> ranking / admission crawlers
  -> extraction
  -> normalization
  -> staging validation
  -> warehouse landing
  -> deterministic entity resolution
  -> aggregation / read models
  -> Spring Boot API
  -> Next.js web product
```

Crawler 邊界是刻意切開的：

- `crawlernest-crawler-core/` 只放可重用 runtime primitives，例如 HTTP、retry、rate limiting、logging 與 snapshot helpers。
- `crawlernest-ranking-crawler/` 負責 QS / THE / ARWU ranking-source extraction 與 ranking-specific crawl policy。
- `crawlernest-admission-crawler/` 負責 university-site discovery、admission extraction、site profiles 與 admission-specific crawl policy。

## Data Visibility Model

API 可見的排名資料會經過 warehouse 與 canonical identity chain：

1. crawlers 收集 raw university、ranking 與 admission facts
2. normalization 準備 source records
3. staging validators 擋下 invalid 或 suspicious rows
4. `warehouse.ranking_record` 儲存 universe-aware ranking truth
5. canonical identity 將 raw entities 連到 `canonical_university`
6. aggregation refresh 產品 read models，例如 `analytics.v_aggregated_rankings_latest`
7. Spring Boot 把 ranking truth 與 canonical metadata join 起來
8. Next.js 透過 same-origin API routes 讀取資料

只存在 raw 或 staging tables 的資料不會自動出現在產品。API 缺資料時，通常需要 canonical linking、backfill，或 aggregation refresh。

## Setup

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

多數 pipeline commands 建議用：

```bash
./.venv/bin/python crawlernest/run_pipeline.py <command>
```

### PostgreSQL

pipeline 與 Java API 預設的本機資料庫是：

```text
database: clawer
user: test
host: localhost
port: 5432
```

需要時可啟動本機 helper service：

```bash
docker compose -f docker-compose.postgres.yml up -d
```

## 啟動 Web Platform

請使用兩個 terminal。

### 1. 啟動 Spring Boot API

```bash
cd crawlernest/servise_for_java
./mvnw -q -DskipTests compile
./mvnw spring-boot:run
```

API 會跑在：

```text
http://localhost:8080
```

常用 focused backend tests：

```bash
cd crawlernest/servise_for_java
./mvnw -q -Dtest=CountryNormalizationTest test
./mvnw -q -Dtest=RankingApiIntegrationTest test
./mvnw -q -Dtest=RecommendationControllerTest test
```

### 2. 啟動 Next.js Frontend

```bash
cd crawlernest/crawlernest-web
npm install
npm run dev
```

網站會跑在：

```text
http://localhost:3000
```

Frontend 透過 same-origin Next.js routes proxy 產品 API，例如 `/api/rankings`、`/api/recommendations`、`/api/compare`、`/api/university-preview`。

## 執行 Data Pipeline

### Production-Safe Daily Run

```bash
bash crawlernest/scripts/run_production_safe.sh
```

中斷後 resume：

```bash
bash crawlernest/scripts/run_production_safe.sh 2500 --resume
```

production-safe runner 會優先使用 `.venv`、採用保守 request pacing、把已完成 pass 寫進 PostgreSQL，並在安全時跳過非關鍵 stage failure 繼續執行。

### 常用 Manual Commands

執行 QS global crawl 並寫入：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run --limit 2500 --ranking-year 2026 --pg-user test --pg-database clawer
```

執行所有 configured QS universes：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

執行單一 QS region：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

執行 THE rankings：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --pg-user test --pg-database clawer
```

執行 ARWU rankings：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-arwu-rankings --pg-user test --pg-database clawer
```

產生 v3 recommendation output：

```bash
./.venv/bin/python crawlernest/run_pipeline.py recommend-v3 --country "United Kingdom" --ielts 6.5 --target-rank 100
```

比較大學：

```bash
./.venv/bin/python crawlernest/run_pipeline.py compare --a "University of Oxford" --b "University of Cambridge"
```

查看完整 command list：

```bash
./.venv/bin/python crawlernest/run_pipeline.py --help
```

## Validation And Repair

驗證 aggregation output：

```bash
./.venv/bin/python crawlernest/scripts/validate_aggregation.py --year 2026 --universe-type global --universe-key global
```

從既有 warehouse universities 修復 canonical visibility：

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical --pg-user test --pg-database clawer
./.venv/bin/python crawlernest/run_pipeline.py backfill-ranking-records --pg-user test --pg-database clawer
```

修復 source-only unresolved entities，例如 THE rows：

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical-from-missing --pg-user test --pg-database clawer
```

Refresh ranking resolution：

```bash
./.venv/bin/python crawlernest/run_pipeline.py refresh-ranking-resolution --pg-user test --pg-database clawer
```

Refresh admission resolution：

```bash
./.venv/bin/python crawlernest/run_pipeline.py refresh-admission-resolution --pg-user test --pg-database clawer
```

## Testing

Python focused tests：

```bash
python -m pytest crawlernest/crawlernest-tests
```

Admission trust 與 decision-product focused tests：

```bash
python -m pytest test_admission_signals.py test_admission_resolver.py crawlernest/crawlernest-tests/test_recommendation_engine.py
```

Frontend tests：

```bash
cd crawlernest/crawlernest-web
npm test
```

Recommendation UI / export focused tests：

```bash
cd crawlernest/crawlernest-web
npm test -- AdmissionSignalBadge.test.tsx RecommendationPageExport.test.tsx
```

Frontend build：

```bash
cd crawlernest/crawlernest-web
npm run build
```

AutoEval extractor evaluation：

```bash
./.venv/bin/python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

## Engineering Guardrails

修改主線行為前，請先看：

- [Architecture Scope](docs/foundation/ARCHITECTURE_SCOPE.md)
- [Data Contracts](docs/foundation/DATA_CONTRACTS.md)
- [Module Ownership](docs/foundation/MODULE_OWNERSHIP.md)
- [Development Workflow](docs/foundation/DEV_WORKFLOW.md)
- [Do Not Auto Modify](docs/foundation/DO_NOT_AUTO_MODIFY.md)
- [Testing Guide](docs/foundation/TESTING_GUIDE.md)
- [Whitepaper](docs/foundation/Whitepaper.md)

短版原則：

- production truth 必須維持 deterministic
- frontend wiring 前，先把 contract 說清楚
- 不要把 business logic 放進 `crawlernest-crawler-core/`
- agent output 是 assistance，不是 authority
- ingestion 通過 validation 後才進 product visibility
- 不要跳過 canonical identity 與 warehouse contracts
