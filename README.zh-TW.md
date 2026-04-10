# CrawlerNest

英文版請參考 [README.md](README.md)。

**CrawlerNest** 是一套 **University Data Intelligence Infrastructure**，並以一個**受控、評估驅動的 AI 輔助開發層**作為增強。它的目標是把分散的全球教育資料，轉成結構化分析、可解釋推薦，以及具備 production-minded system design 的資料基礎設施。

## 這個系統是什麼？

CrawlerNest 是一套端到端的大學資料平台，能把分散的網頁資料轉成結構化、可查詢的大學 intelligence。它聚合 QS、THE、ARWU 等排名來源，提供 ranking evidence 與 trust signals，並支援學生、顧問與產品團隊所需的 explainable recommendation 與 comparison workflows。

目前系統也正逐步納入 **Mini-Agent Development Layer**：這是一個輕量、受控的 workflow，用來加速開發與系統 refinement。這一層與 evaluation 深度耦合，並且必須有人類監督。它不是獨立的自治 agent system。

## 為什麼要做這個系統？

學生與顧問需要的不只是更多 ranking rows，而是透明的 evidence、可比較的 signals，以及值得信任的 decision support。CrawlerNest 的存在，是為了讓 ranking aggregation 不再只是 opaque 的列表，而是真正可理解、可使用的資料系統。

## 目前能力

*   **多來源排名 Ingestion：** QS、THE、ARWU 已可進入同一條 ranking storage / aggregation path。THE world rankings 優先使用**結構化 JSON**（已發布時使用 CDN blobs，否則退回 Next.js `__NEXT_DATA__`），而非脆弱的 HTML-first 抓法。
*   **Universe-Aware Aggregation：** 排名已區分為 `global`、`region`、`subject`、`special` 等 universe，aggregation 會依 universe 隔離處理。
*   **以 Rank 為主的 Aggregation Truth：** aggregated rank 由來源 rank 決定，而不是用 composite score 排序；`compositeScore` 僅保留為展示訊號。
*   **Ranking Evidence：** 產品列與大學 detail page 可直接顯示 QS / THE / ARWU 的來源排名，以及來源間的差異。
*   **Trust Layer：** 每個 aggregated ranking 都可附帶保守型 trust score 與 trust explanation，依據來源覆蓋率與來源一致性計算。
*   **Explainable Recommendation：** 推薦結果不只給 match score，也會提供 fit dimensions、reasons 與 warnings。
*   **Compare Workflow：** shortlist 中的學校可 side by side 比較 aggregated rank、source evidence、trust 與 admissions context。
*   **Canonical Country Filtering：** rankings country filter 已統一走 canonical country normalization。像 `China`、`China (mainland)`、`USA`、`UK` 這些變體都會先正規化，再進入 validation、SQL filtering 與 metadata generation。
*   **Canonical Recovery Path：** 尚未 linked 的 crawled universities 可提升為 `canonical_university`，並回填到 `warehouse.ranking_record`，不需改動 crawler 行為。
*   **Ingestion Traceability：** 每次 ingest 都會將 `run_id` / `updated_at` trace fields 寫入 PostgreSQL ranking records。
*   **API Platform：** Java Spring Boot API 已提供 rankings、university detail、recommendations 與 comparison data 給產品 UI。
*   **Database Reliability：** PostgreSQL transaction handling、canonical repair paths 與 operational snapshot fallback，可在上游不穩定時維持產品可用性。

## 高層架構

CrawlerNest 採用嚴格解耦的 6 層架構：

1.  **Data Layer：** 從公開 ranking 與 university data providers 取得原始資料。
2.  **Canonical Layer：** 負責 entity resolution、alias handling、normalization，以及 source-to-canonical mapping。
3.  **Aggregation Layer：** 負責 PostgreSQL warehouse 與 universe-aware ranking truth。
4.  **Decision Layer：** 負責 recommendation、trust scoring、evidence summaries 與 comparison logic。
5.  **Mini-Agent Layer：** 一個輕量、受控的 AI-assisted development loop，用於有範圍的 task generation、evaluation 與 refinement。
6.  **Product Layer：** Spring Boot API 與 Next.js website。

Mini-Agent Layer 遵循一個受限的循環：

`Task -> Generate -> Evaluate -> Refine`

它與 AutoEval 深度整合，目標是在不削弱 system reliability 的前提下提升開發速度。

更完整的工程設計請參考 [Whitepaper](docs/foundation/Whitepaper.md)。

## AI 輔助開發（Mini-Agent）

- **從設計上即受控：** Mini-Agent layer 是一個有邊界的 workflow，不是 fully autonomous system
- **評估驅動：** 生成出的結果應先經過 evaluation，再考慮更廣泛採用
- **Human-in-the-loop：** 重要修改、refinements 與 integration decisions 都需要人工監督
- **與 AutoEval 整合：** evaluation 的角色是強化 reliability，而不是盲目自動化
- **聚焦系統 refinement：** 適合用在 extractor iteration、workflow improvement 與 development acceleration

## 設計哲學

- reliability 優先於 autonomy
- evaluation-first development
- controlled automation 優先於 unrestricted generation
- system clarity 優先於 opaque intelligence

## 雙系統架構

CrawlerNest 被設計為一個雙層系統，結合資料 intelligence core 與 evaluation-driven agent capability layer。

### Core Intelligence Layer

Core Intelligence Layer 負責平台的主要資料與決策流程。它涵蓋多來源 crawling、university 與 ranking records 的結構化 extraction、normalization 與 canonical identity resolution、以 PostgreSQL 為核心的資料儲存、aggregation 與 analytics pipelines，以及將 explainable outcomes 提供到產品層的 recommendation logic。這一層是整個系統的 operational backbone，並保持 deterministic、queryable 與 production-oriented 的特性。

### Agent Capability Layer

Agent Capability Layer 位於 operational core 之上，作為一個受控的 improvement 與 assistance system。它包含 agent engine、evaluator 與 refiner 等元件，共同支援 iterative task execution、refinement loops，以及 development assistance。這一層不是要取代 core system，而是提供有邊界的 reasoning、evaluation-driven improvement，以及對 extractor hardening、parser refinement 與 system validation 等工程 workflow 的範圍化支援。

CrawlerNest Platform
│
├── Core Intelligence Layer
├── Agent Capability Layer
└── Interface Layer

這種分層存在的目的，是讓架構內部的責任邊界更清晰。核心平台可以作為穩定的 intelligence 與 analytics system 持續擴張，而 agent layer 則可作為受控、可自我改善的 capability 獨立演進。其結果是更乾淨的 separation of concerns、更可擴展的 system boundary，以及一個能持續迭代改進、同時不削弱 production data path trustworthiness 的基礎。

## Python 環境設定

CrawlerNest 的 Python pipeline 應在專案虛擬環境中執行。

### 1. 建立虛擬環境
```bash
python3 -m venv .venv
```

### 2. 啟用虛擬環境
```bash
source .venv/bin/activate
```

### 3. 安裝 Python 依賴
```bash
pip install -r requirements.txt
```

production-safe runner 已優先使用：

```bash
/Users/test/Desktop/crawlernest/.venv/bin/python
```

因此，保持 `.venv` 正常可用，是執行 crawler、validation scripts 與 PostgreSQL ingestion pipeline 最安全的方式。

## 資料可見性模型

目前 CrawlerNest 的 database visibility chain 如下：

1. crawler 將原始 university / ranking facts 寫入 PostgreSQL
2. canonical identity layer 將 raw universities 對應到 `canonical_university`
3. `warehouse.ranking_record` 儲存 universe-aware ranking truth
4. aggregation 刷新 `analytics.v_aggregated_rankings_latest`
5. Spring Boot API 在 aggregated truth 上 join canonical university metadata，補出 `universityName`、`slug`、`country` 等產品欄位
6. Next.js frontend 透過 `/api/rankings` 讀取資料

這很重要，因為只存在於 `warehouse.universities` 的 universities 並不會自動出現在 API 中。  
只有 canonical linking 與 ranking-record backfill 完成後，它們才會真正可見。

## 如何啟動網站平台（Website Product Layer）

若要啟動完整堆疊（Backend API + Frontend UI），請使用兩個 terminal：

### 1. 啟動 Java Backend API

backend 負責提供已正規化的大學與 ranking data。

在 fresh verification run 前，建議先做：

1. 停掉舊的 Spring Boot process，避免查到舊版程式
2. 若改過 ranking / trust / country-filter logic，先重新 compile backend
3. 若改到 normalization 或 rankings read-path logic，先跑 focused test 再啟動

建議 preflight：

```bash
pkill -f "spring-boot:run"
cd crawlernest/servise_for_java
./mvnw -q -DskipTests compile
./mvnw -q -Dtest=CountryNormalizationTest test
```

接著啟動 API：

```bash
./mvnw clean
./mvnw spring-boot:run
```

### 2. 啟動 Next.js Frontend

frontend 提供 Rankings Browser 與 Recommendation UI。

```bash
cd crawlernest/crawlernest-web
npm run dev
```

應用程式入口：

`http://localhost:3000`

目前 frontend 包含：

- rankings browser
- university detail pages
- recommendation flow
- compare page

rankings browser 透過同源 `/api/rankings` proxy 與 `no-store` fetch 讀取資料，但目前只會在以下情況刷新：

- 首次載入
- filter 變更
- 使用者手動重新整理瀏覽器

country filtering 是套用在最終 rankings read query，而不是 aggregation layer：

- 保留 aggregated rank order
- 依 canonical university country metadata 過濾產品列
- global scope 可選任一支援國家
- region scope 仍保持 region-consistent
- country aliases 會先正規化為 canonical names，再進入 validation 與 SQL filtering
- `metadata.countryOptions` 會去重後僅保留 canonical country names

---

## 如何執行資料管線（Crawler）

請依你要做的工作選擇對應指令：

- **日常安全執行：** 使用 production-safe runner
- **手動 crawl / 定向重跑：** 直接使用 QS / THE commands
- **驗證：** 使用 validation 與 diagnostic commands
- **可見性修復：** 使用 canonical / backfill recovery commands

### 1. Production-Safe Run（建議日常入口）

若你要用最安全的預設指令進行日常操作，請使用：

```bash
bash crawlernest/scripts/run_production_safe.sh
```

若中斷後要續跑：

```bash
bash crawlernest/scripts/run_production_safe.sh 2500 --resume
```

這支 production-safe script 目前會執行：

- **Step 1：** QS global rankings crawl
- **Step 2：** 若有 pending items，執行 deferred detail enrichment
- **Step 3：** THE world rankings ingestion
- **Step 3.5：** ARWU world rankings ingestion
- **Step 4：** QS major region universes，各跑一輪
  - europe
  - asia
  - latin-america
  - arab-region
  - oceania
  - africa
  - north-america
- **Step 5：** 從 missing THE entities seed canonical entities

執行特性：

- 自動優先使用專案 `.venv`
- crawler progress 會維持為單一 live progress line
- 支援 resume mode
- 每輪完成後都會立即寫入 PostgreSQL
- 若非關鍵階段失敗，會 warning 並繼續往下跑

### 2. 手動 Crawl / Ingest Commands

當你需要更細的 scope、resume 行為或測試控制時，可直接使用以下命令。

#### 2.1 跑全部 QS universes

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

若中斷後續跑：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.2 跑單一 QS region universe

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

若要續跑同一 region：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.3 跑 THE world rankings

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --pg-user test --pg-database clawer
```

若你只想 ingest THE，而不做額外 seed/backfill recovery：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --skip-seed --pg-user test --pg-database clawer
```

#### 2.4 在主流程 `run` 中串接 THE（選用）

完成 QS crawl -> normalize -> DB write -> QS multi-source sync 後，你也可以在同一個 invocation 中接著 ingest THE（除非你加旗標，否則不會改變預設行為）：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run --limit 2500 --ranking-year 2026 \
  --with-the-rankings --the-ranking-year 2026 \
  --pg-user test --pg-database clawer
```

常用旗標：

- `--the-ranking-year` — THE edition（預設：`2026`）
- `--the-output-dir` — `the_rankings_<year>.json` 的輸出路徑（預設為 `crawlernest/crawlernest-kb/databases`）
- `--the-skip-seed` — THE ingest 後略過 canonical seed / legacy backfill（較快，但 recovery 較少）

pipeline logs 在 THE crawl 階段會出現 `[THE_CRAWL]`；THE rows 在 multi-source ingest path 中會使用 `the-<year>` 風格的 `run_id`。

#### 2.5 一次跑 QS major regions（continuous loop）

這個單一指令會依序連續執行 World ranking 與五大 regional rankings（Europe、Asia、Latin America、Oceania、Africa）：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-major --ranking-year 2026
```

QS universe commands 的重要執行語意：

- `run-qs-*` 與 `run-qs-universes` 都是 continuous commands，會一直跑到你按 `Ctrl+C`
- 每個 completed pass 都會先寫入 PostgreSQL，再開始下一輪
- 若中斷，下次可帶 `--resume`，從上次儲存的 universe snapshot 繼續，而不是全部重跑

### 3. 驗證與診斷

當你在 crawl/ingest 後想確認資料正確性，或找出缺失的 universes，可使用以下命令。

#### 3.1 驗證 aggregation output

```bash
./.venv/bin/python crawlernest/scripts/validate_aggregation.py --year 2026 --universe-type region --universe-key europe
```

validator 會回報：

- row count
- distinct university count
- duplicate count
- null rank count
- missing ranks
- top countries
- top 20 preview

#### 3.2 診斷缺失的 QS universes

```bash
./.venv/bin/python crawlernest/run_pipeline.py rebuild-universe-records --ranking-year 2026 --pg-user test --pg-database clawer
```

此命令會：

- 檢查所有已設定的 QS universes
- 回報哪些 universe/year pairs 在 `warehouse.ranking_record` 中目前為 `0` rows
- **不會** 自動重新 crawl

#### 3.3 統計 `warehouse.ranking_record` 中的 THE rows

`ranking_record` 儲存的是 `ranking_source_id`，不是單純的 `source` 文字欄位。請 join registry：

```sql
SELECT COUNT(*)
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
WHERE rs.source_code = 'THE';
```

### 4. 可見性修復命令

只有在資料已存在 PostgreSQL，但 API 或 frontend 仍看不到時，才使用這些命令。

#### 4.1 補回已存在 `warehouse.universities` 的 universities

若 universities 已被 crawler 寫入 `warehouse.universities`，但沒有出現在 API 或 frontend，通常原因是 canonical/link/backfill 步驟缺失。

請依序執行這兩條：

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical --pg-user test --pg-database clawer
./.venv/bin/python crawlernest/run_pipeline.py backfill-ranking-records --pg-user test --pg-database clawer
```

這兩條命令會：

- 建立缺失的 `canonical_university` rows
- 建立缺失的 `canonical_university_link` rows
- 將 legacy `warehouse.rankings` 回填到 `warehouse.ranking_record`
- 刷新 aggregation，讓 API/frontend 能立刻看到新 rows

目前環境中的觀察結果：

- visible global aggregated rows 從 `221` 增加到 `1323`
- `/api/v1/rankings` 回報 `metadata.totalCount = 1323`

#### 4.2 從 `analytics.missing_entity_log` 補回僅存在於 THE 的 universities

THE universities 不會來自 `warehouse.universities`，因此光靠 `seed-canonical` 無法修復。

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical-from-missing --pg-user test --pg-database clawer
```

此命令會：

- 從 `analytics.missing_entity_log` 讀取 unresolved rows（預設 source：`THE`）
- 使用 `(raw_name, country_hint)` seed 新的 `canonical_university` entities
- 重新執行 THE ingestion，讓新 seed 的 entities 可立即被 matched

目前環境中的觀察結果：

- `seeded=1283`
- THE re-ingest 達到 `matched=2191`
- THE `unresolved=0`
- aggregated visible rows 擴張到 `2736`

---

工程維運、API invariants 與 testing logic 請參考 [Engineering Validation & Maintenance Guide](docs/foundation/TESTING_GUIDE.md)。  
目前 repository map 與工作路徑請參考 [Repository Structure](docs/REPO_STRUCTURE.md)。

## 目前系統狀態

這反映了目前實際的工程成熟度：

*   ✅ **production-safe pipeline：** 已完成（2,736 所大學，QS + THE 雙來源）
*   ✅ **PostgreSQL integration：** 已完成（具 transaction-safe rollback）
*   ✅ **recommendation engine（v3 decision system）：** 已完成
*   ✅ **API v1 readiness：** 已完成（已修復、pagination-aligned、scope-aware、country-aware）
*   ✅ **node deployment（Lobster-01）：** 已完成（單一 canonical `lobster-01/` runtime 目錄）
*   ✅ **multi-source（QS + THE）：** 已運行（2,191 所 THE universities 完成 matched）
*   ✅ **website product layer：** 已運行（rankings、detail、recommendation、compare、evidence、trust、country-aware filters）

## 里程碑與開發歷史

CrawlerNest 的工程深度，建立在一系列明確的 milestones 之上：

### 已完成（Foundation & Infrastructure）

*   **Crawler Development：** 非同步 pipeline、local parse parallelism、compliance-safe request pacing。
*   **Normalization：** Python baseline 與 C prototype，處理高效字串解析。
*   **PostgreSQL Switch：** 已切換至穩健的 PostgreSQL warehouse，並成為唯一 datastore。
*   **Production-Safe Pipeline：** 建立 Lobster-01（node-ready deployment），搭配 systemd scheduling 與 decoupled cooldowns 避免 403 blocks。
*   **Recommendation Engine：** 從 rule-based filters（v1）演進到 grouped categories（v2），再到經校準的 hybrid deterministic scoring（v3）。

### 進行中（Platform Expansion）

*   持續深化 canonical university entity resolution。
*   擴張 subject / special universe coverage。

### 未來方向

*   Public API platform commercialization。
*   在 deterministic engine 之上加入 AI-driven insights。

### 近期產品與資料里程碑

*   **2026-04-02：** 強化 QS production crawl，穩定 global entry resolution 與 snapshot fallback，以應對上游 blocking。
*   **2026-04-03：** 將 aggregation ordering 從 score-led ranking 改為 weighted rank-based aggregation truth。
*   **2026-04-04：** 加入 aggregation explainability、strict trust layer、explainable recommendation 與更完整的 university detail evidence。
*   **2026-04-05：** 完成 hydration-safe rankings refactor、compare page MVP，以及透過最終 Java rankings read query 打通端到端 country filtering。
*   **2026-04-05：** 加入集中式 canonical country normalization layer，讓 alias inputs 與 metadata variants 收斂為穩定的 product-facing country filters。

## AutoEval Extractor Milestone

CrawlerNest 的 extractor loop 現在已由可重複執行的 AutoEval workflow 支撐，能對 candidate extractor 進行評分、指出具體失敗案例，並在 refinement 之後再次驗證結果是否真的提升，再決定是否保留。

### Improvement (Before -> After)

| Metric            | Before | After |
|------------------|--------|-------|
| score            | 0.13   | 0.95  |
| error_count      | 50+    | 0     |
| exact_match_rate | 0.05   | 1.00  |
| field_coverage   | 0.22   | 0.98  |
| retry_needed     | frequent | rare |

這些數值代表這次 milestone 的典型結果：baseline extractor 在大多數 golden samples 上失敗，而經過 refinement 的版本已能穩定對齊目標結構化輸出，並達到接近完整的欄位覆蓋率。

### What This Means (Engineering Perspective)

這不只是一次 parser 調整，而是一個受控的 optimization loop：系統可以先 evaluate candidate，接著 modify implementation，再 re-evaluate 結果，最後依據可量測的輸出品質決定 keep 或 revert。

這代表資料品質不再只是主觀判斷，而是可觀測、可比較、可驗證的工程指標。Regression 變得可被偵測，improvement 變得可被測試，而 extractor 路徑也開始更像一套可持續自我改進的工程系統，而不是一次性的 scraping script。

### How to Reproduce

可直接執行 extractor evaluation：

```bash
python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

若使用專案虛擬環境，等價指令如下：

```bash
./.venv/bin/python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

## Repository Map

目前 repo 有兩層：

- outer workspace：docs、deployment assets、editor config、top-level project material
- inner platform workspace：[crawlernest/](crawlernest)，包含 runnable pipeline、backend、schema 與 frontend
