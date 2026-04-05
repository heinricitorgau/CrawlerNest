# 大學資料基礎設施與網站平台

這是 **CrawlerNest** 的獨立繁體中文版 README。  
英文版請參考 [README.md](README.md)。

---

## CrawlerNest 是什麼？

**CrawlerNest** 是一套從資料抓取、標準化、資料庫寫入、聚合、API，到前端網站的完整大學資料與排名 intelligence 平台。  
它的目標不是重做單一官方榜單，而是把分散在全球網站上的大學排名、申請要求與學校資訊，轉成結構化、可查詢、可比較、可解釋、可推薦的產品級資料系統。

---

## 目前能做什麼？

- **多來源排名 ingestion**：QS、THE、ARWU 已能進入同一條 ranking storage / aggregation path。THE 世界排名優先使用**結構化 JSON**，不以脆弱 HTML-first 為主。
- **多 universe 排名真相**：已支援 `global / region / subject / special` universe-aware aggregation，不再把不同 universe 混在一起。
- **以 rank 為主的聚合排序**：aggregated rank 以來源 rank 聚合為主，`compositeScore` 保留為展示欄位，而不是排序真相。
- **Ranking Evidence**：產品頁面與大學 detail page 可顯示 QS / THE / ARWU 原始來源排名與差異。
- **Trust Layer**：每個聚合排名可附帶保守型 trust score 與 trust explain。
- **Explainable Recommendation**：推薦結果不只給分數，也會提供 reasons / warnings / fit dimensions。
- **Compare Page**：shortlist 中的學校可做 side-by-side 比較，查看 aggregated rank、evidence、trust 與 admissions context。
- **Canonical Country Filter**：Rankings Browser 的國家過濾已升級為 canonical country normalization 流程。像 `China`、`China (mainland)`、`USA`、`UK` 這類 alias 會先被收斂成統一 canonical country，再進入 validation、SQL filter 與 metadata country options。
- **寫入可追蹤性**：每次 ingest 都會帶 `run_id` 與 `updated_at`。
- **可見性修復路徑**：若學校已抓到 `warehouse.universities` 但尚未出現在 API / 前端，可透過 canonical seeding 與 ranking backfill 補齊。
- **API 與網站**：Spring Boot API + Next.js frontend 已支援 rankings、university detail、recommendation、compare 等主要產品流程。

---

## 高層架構

CrawlerNest 採用 5 層結構：

1. **Data Layer**：crawler 從外部來源抓資料  
2. **Canonical / Processing Layer**：entity resolution、alias matching 與 normalization  
3. **Aggregation / Storage Layer**：PostgreSQL warehouse 與 universe-aware aggregated truth  
4. **Decision Layer**：recommendation、trust、comparison、evidence summary  
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
5. Spring Boot API 在 aggregated truth 之上 join canonical university metadata，補出 `universityName`、`slug`、`country` 等產品欄位  
6. Next.js 前端透過 `/api/rankings` 顯示資料  

這很重要，因為 **只存在於 `warehouse.universities` 的資料不會自動出現在 API / 前端**。  
必須完成 canonical linking 與 ranking-record backfill，資料才會真正可見。

---

## 如何啟動網站

請使用兩個 terminal：

### 1. 啟動 Java Backend API

下次要重新驗證 Java backend 前，建議先做這些事：

1. 先停掉舊的 Spring Boot process，避免實際打到舊版程式
2. 如果剛改過 rankings / trust / country filter，先重新 compile backend
3. 如果改到 country normalization 或 rankings read path，先跑 focused test 再啟動

建議 preflight：

```bash
pkill -f "spring-boot:run"
cd crawlernest/servise_for_java
./mvnw -q -DskipTests compile
./mvnw -q -Dtest=CountryNormalizationTest test
```

接著再啟動 API：

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

目前前端產品層已包含：

- Rankings Browser
- University Detail Page
- Recommendation Flow
- Compare Page

目前 rankings page 透過 same-origin `/api/rankings` proxy 與 `no-store` fetch 取得資料；更新時機為：

- 首次載入
- 使用者變更 filter / page / scope / region / country / search
- 使用者手動重新整理瀏覽器

其中 `country` filter 是套用在最終 rankings read query：

- 不改 aggregation 排序真相
- 依 canonical university country metadata 過濾產品結果
- global 可選任一支援國家
- region 仍保持 region-consistent
- country alias 會先正規化成 canonical country name
- `metadata.countryOptions` 只回 canonical country，不再回重複變體

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
- **Step 3.5**：ARWU world rankings ingestion
- **Step 4**：QS major regions 各跑一輪
  - europe
  - asia
  - latin-america
  - arab-region
  - oceania
  - africa
  - north-america
- **Step 5**：seed canonical entities from missing THE entities

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

#### 2.4 在主流程 `run` 一併跑 THE（選用）

在完成「QS 抓取 → 正規化 → 寫入 DB → QS multi-source 同步」之後，可在同一個指令中接著跑 THE ingestion（**預設不會**執行，需加上旗標）：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run --limit 2500 --ranking-year 2026 \
  --with-the-rankings --the-ranking-year 2026 \
  --pg-user test --pg-database clawer
```

相關參數：

- `--the-ranking-year`：THE 版本年度（預設 `2026`）
- `--the-output-dir`：寫出 `the_rankings_<year>.json` 的目錄（預設為 `crawlernest/crawlernest-kb/databases`）
- `--the-skip-seed`：THE ingest 後略過 canonical seed／legacy backfill（較快，修復較少）

THE 抓取階段日誌會出現 `[THE_CRAWL]`；multi-source 寫入時批次識別為 `the-<year>` 風格。

#### 2.5 一次跑 QS 主要區域（連續迴圈）

下列指令會依序連續執行 World 與五大區域排名（歐、亞、拉丁美洲、大洋洲、非洲），直到手動停止：

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-major --ranking-year 2026
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

### 3. 統計 `warehouse.ranking_record` 中的 THE 筆數

`ranking_record` 以 `ranking_source_id` 關聯來源，沒有單獨的 `source` 文字欄位。請 join `warehouse.ranking_source`：

```sql
SELECT COUNT(*)
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
WHERE rs.source_code = 'THE';
```

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

---

## 版本對照

- 英文版完整說明（含 Milestones、Repository Map）：[README.md](README.md)
