# 大學資料基礎設施與網站平台

這是 **CrawlerNest** 的獨立繁體中文版 README。  
英文版請參考 [README.md](README.md)。

---

## CrawlerNest 是什麼？

**CrawlerNest** 是一套從資料抓取、標準化、資料庫寫入、聚合、API，到前端網站的完整大學資料平台。  
它的目標是把分散在全球網站上的大學排名、申請要求與學校資訊，轉成結構化、可查詢、可比較、可推薦的產品級資料系統。

---

## 目前能做什麼？

- **資料管線**：可穩定抓取 QS 與 THE 等排名資料，並寫入 PostgreSQL。
- **多宇宙排名 ingestion**：已支援 QS 的 `global / region / subject / special` universes。
- **寫入可追蹤性**：每次 ingest 都會帶 `run_id` 與 `updated_at`。
- **可見性修復路徑**：若學校已抓到 `warehouse.universities` 但尚未出現在 API / 前端，可透過 canonical seeding 與 ranking backfill 補齊。
- **聚合真相層**：aggregation 已支援 multi-universe truth，不再只有 global。
- **推薦系統**：已有 deterministic recommendation engine，可做 `reach / target / safety` 類型建議。
- **API 與網站**：Spring Boot API + Next.js frontend 已能顯示與搜尋聚合排名資料。

---

## 高層架構

CrawlerNest 採用 5 層結構：

1. **Data Layer**：crawler 從外部網站抓資料  
2. **Canonical / Processing Layer**：entity resolution 與 normalization  
3. **Aggregation / Storage Layer**：PostgreSQL warehouse 與 aggregated truth  
4. **Decision Layer**：recommendation / comparison logic  
5. **API / Product Layer**：Spring Boot API 與前端網站  

更完整的工程設計請參考 [Whitepaper](docs/foundation/Whitepaper.md)。

---

## Python 環境

CrawlerNest 的 Python pipeline 應優先使用專案虛擬環境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

正式執行時建議使用：

```bash
/Users/test/Desktop/crawlernest/.venv/bin/python
```

---

## 資料可見性模型

目前資料從 crawler 到前端的可見路徑是：

1. crawler 將原始大學 / 排名資料寫入 PostgreSQL  
2. canonical identity layer 將 raw university 對應到 `canonical_university`  
3. `warehouse.ranking_record` 儲存 universe-aware ranking truth  
4. aggregation 刷新 `analytics.v_aggregated_rankings_latest`  
5. Spring Boot API 從 aggregated truth 讀資料  
6. Next.js 前端透過 `/api/rankings` 顯示資料  

這很重要，因為 **只存在於 `warehouse.universities` 的資料不會自動出現在 API / 前端**。  
必須完成 canonical linking 與 ranking-record backfill，資料才會真正可見。

---

## 如何啟動網站

請使用兩個 terminal：

### 1. 啟動 Java Backend API

```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

### 2. 啟動 Next.js Frontend

```bash
cd crawlernest/crawlernest-web
npm run dev
```

網站入口：

```text
http://localhost:3000
```

目前前端已補強資料新鮮度機制：

- same-origin `/api/rankings` proxy
- `no-store` fetch
- 定時 polling
- focus / visibility / reconnect 後立即 refresh

---

## 如何執行資料管線

目前建議依用途分成四類：

- **日常安全執行**：用 production-safe script
- **手動抓取 / 測試 / 指定 scope 重跑**：直接用 QS / THE commands
- **驗證與診斷**：確認 aggregation 是否正確、哪些 universe 缺資料
- **可見性修復**：資料已在 PostgreSQL，但 API / 前端還看不到時使用

### 1. Production-safe 方式（建議日常使用）

如果你想用一條最安全的命令定期刷新資料庫，請用這條：

```bash
bash crawlernest/scripts/run_production_safe.sh
```

中斷後續跑：

```bash
bash crawlernest/scripts/run_production_safe.sh 2500 --resume
```

這支 script 目前會依序執行：

- **Step 1**：QS global rankings crawl
- **Step 2**：如果有 deferred items，就跑 detail enrichment
- **Step 3**：THE world rankings ingestion
- **Step 4**：QS major regions 各跑一輪
  - europe
  - asia
  - latin-america
  - arab-region
  - oceania
  - africa
  - north-america

執行特性：

- 自動優先使用專案 `.venv`
- 單一進度列輸出
- 支援 `--resume`
- 每輪完成就先寫入 PostgreSQL
- 非關鍵步驟失敗時會警告但繼續往下跑

### 2. 手動執行資料抓取 / ingestion

當你需要更細的控制，例如只跑 QS、只跑某個 region、或只跑 THE，可以直接用下面這些命令。

#### 2.1 跑全部 QS universes

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

中斷後續跑：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.2 單跑一個 QS region

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

中斷後續跑：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.3 跑 THE 世界排名

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --pg-user test --pg-database clawer
```

如果只想先 ingest，不做額外 seed / backfill：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --skip-seed --pg-user test --pg-database clawer
```

QS universe commands 的執行語意：

- `run-qs-*` 與 `run-qs-universes` 都是 continuous commands
- 會一直跑到你按 `Ctrl+C`
- 每一輪完成都會先寫 DB
- 下次帶 `--resume` 會從上次 snapshot 接著跑

---

## 驗證與診斷

### 1. 驗證 aggregation 結果

```bash
./.venv/bin/python crawlernest/scripts/validate_aggregation.py --year 2026 --universe-type region --universe-key europe
```

會輸出：

- row count
- distinct university count
- duplicate count
- null rank count
- missing ranks
- top countries
- top 20 preview

### 2. 診斷哪些 QS universe 缺資料

```bash
./.venv/bin/python crawlernest/run_pipeline.py rebuild-universe-records --ranking-year 2026 --pg-user test --pg-database clawer
```

它會：

- 檢查所有 QS universes
- 找出哪些 universe 在指定年份的 `warehouse.ranking_record` 是 0 rows
- 印出應重新 re-crawl 的 universe

它 **不會** 自動重抓，只做診斷。

---

## 可見性修復

### 1. 補回「已抓到但前端看不到」的 QS 學校

如果資料已經進了 `warehouse.universities`，但 API / frontend 看不到，通常是 canonical / link / ranking_record 還沒補齊。

請依序執行：

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical --pg-user test --pg-database clawer
./.venv/bin/python crawlernest/run_pipeline.py backfill-ranking-records --pg-user test --pg-database clawer
```

這兩步會：

- 建立 `canonical_university`
- 建立 `canonical_university_link`
- 將 legacy `warehouse.rankings` 回填到 `warehouse.ranking_record`
- 重新 refresh aggregation

目前實際觀察結果：

- visible global aggregated rows 已從 `221` 擴大到 `1323`（seed-canonical + backfill 階段）

### 2. 補回卡在 missing log 裡的 THE 學校

THE universities 不會先進 `warehouse.universities`，所以不能只靠 `seed-canonical` 修復。

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical-from-missing --pg-user test --pg-database clawer
```

這條 command 會：

- 從 `analytics.missing_entity_log` 讀 THE unresolved rows
- 用 `(raw_name, country_hint)` 補種 `canonical_university`
- 自動重跑一次 THE ingestion

目前實際觀察結果：

- `seeded=1283`
- THE re-ingest 後 `matched=2191`
- `unresolved=0`
- aggregated visible rows 擴大到 `2736`

---

## 目前系統狀態

- ✅ production-safe pipeline：已完成（2,736 所大學，QS + THE 雙來源）
- ✅ PostgreSQL integration：已完成
- ✅ recommendation engine：已完成
- ✅ API v1：已完成
- ✅ visible global recovery path：已完成
- ✅ multi-source（QS + THE）：已上線，THE 2,191 所大學完整匹配
- 🔄 website layer：持續擴充中（~92%）

更多工程維運與驗證細節：

- [Engineering Validation & Maintenance Guide](docs/foundation/TESTING_GUIDE.md)
- [Repository Structure](docs/REPO_STRUCTURE.md)
