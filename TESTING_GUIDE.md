# CrawlerNest 測試與維護指南

本文件定義 CrawlerNest 的測試流程、架構維護原則、模組邊界、變更流程與例行維護方式。
目標是確保系統在持續演進時，仍維持一致性、可擴展性、可回溯性與可驗證性。

---

## 1. 文件目的與適用範圍

本說明書適用於以下維護場景：

- 新增或調整 crawler / extractor / db writer / API 功能
- 資料模型（schema）異動
- 推薦邏輯或分析邏輯擴展
- Python / C / Java 跨模組整合調整
- 架構層級重整與技術債治理

不適用於純文案與非技術性內容更新。

---

## 2. 架構總覽與分層責任

CrawlerNest 架構遵循：

**資料採集 → 資料處理與正規化 → 知識庫 → 分析與推薦 → 產品服務**

### 2.1 分層定義

1. 採集層（Crawler）
- 職責：來源抓取、分頁、重試、容錯
- 主要目錄：`crawlernest/crawlernest-jobs`, `crawlernest/crawlernest-extractors`

2. 處理與正規化層（Normalization）
- 職責：欄位清洗、分數解析、名稱與國家標準化
- 主要目錄：`crawlernest/crawlernest-core`, `crawlernest/crawlernest-normalization/c_engine`

3. 儲存層（Knowledge Base）
- 職責：資料寫入、lineage、資料品質追蹤
- 主要目錄：`crawlernest/crawlernest-db-writer`, `crawlernest/crawlernest-schema`

4. 分析與推薦層（Analytics / Recommendation）
- 職責：聚合計算、推薦特徵、決策邏輯
- 主要目錄：`crawlernest/crawlernest-analytics`, `crawlernest/crawlernest-recommendation`

5. 服務與產品層（Service / Product）
- 職責：API 對外介面、服務編排
- 主要目錄：`crawlernest/servise_for_java`, `crawlernest/crawlernest-cli`, `crawlernest/crawlernest-web`

### 2.2 分層紅線（不得跨越）

- 採集層不得直接實作推薦決策邏輯
- API 層不得直接繞過 writer 寫 DB
- 推薦層不得依賴未正規化的原始欄位
- 任一層不得硬編碼另一層內部實作細節

---

## 3. 模組邊界與相依原則

### 3.1 相依方向（允許）

- `crawlernest-jobs` -> `crawlernest-extractors` -> `crawlernest-core` -> `crawlernest-db-writer`
- `servise_for_java` -> DB（查詢）
- `crawlernest-analytics` -> 已落庫的 canonical 資料

### 3.2 相依方向（禁止）

- 上層直接呼叫下層私有函式
- Java API 服務直接綁定 crawler 內部流程
- C engine 直接控制 Python 工作流（應由 Python 主流程編排）

### 3.3 共用邏輯準則

- 可重用邏輯優先放 `crawlernest-core`
- 常數與映射集中管理於 `constants/`
- 模組間資料交換使用明確模型或結構化 payload

---

## 4. 變更分級與流程

### 4.1 變更分級

1. L1（低風險）
- 註解、文件、非核心參數調整

2. L2（中風險）
- 單模組功能變更，不影響 schema 與跨語言介面

3. L3（高風險）
- schema 變更
- API contract 變更
- Python/C/Java 跨層介面變更
- 推薦模型核心計分邏輯變更

### 4.2 標準流程

1. 先寫變更目的與影響範圍
2. 明確列出受影響層與模組
3. 實作變更與必要遷移
4. 更新對應文件（本檔、白皮書、README）
5. 完成驗證後才可合併

---

## 5. 資料模型與 Schema 維護規範

### 5.1 Schema 單一真實來源

- 正式 runtime schema：`crawlernest/crawlernest-schema/postgresql_schema.sql`
- 相關擴充 schema：
  - `crawlernest/crawlernest-schema/entity_resolution_postgresql.sql`
  - `crawlernest/crawlernest-schema/multi_source_postgresql.sql`
  - `crawlernest/crawlernest-schema/ranking_aggregation_postgresql.sql`
  - `crawlernest/crawlernest-schema/recommendation_postgresql.sql`
- `crawlernest/crawlernest-schema/schema.sql` 為 archived legacy SQLite schema，不再作為 runtime source

任何表結構變更，應以 PostgreSQL schema 與對應 bootstrap / migration 路徑為準。

### 5.2 Schema 變更要求

- 新欄位需定義用途、型別、可空性、索引策略
- 變更需保留向後相容方案（migration/預設值/回填）
- 影響 API 回傳時，需同步更新 DTO 與文件

### 5.3 Canonical 規則

- `universities` 為核心實體表
- `university_aliases` 管理來源別名映射
- `raw_source_records` 必須保留追溯資訊
- `field_status_logs` 用於資料品質與稽核

---

## 6. API 與服務層維護規範

### 6.1 API 合約規則

- 新增端點優先，不破壞既有端點語意
- 若需破壞式變更，必須提供版本策略（如 `version=v2` / `version=v3`）
- 回應結構需穩定，錯誤格式需一致

### 6.2 Java 服務層規範

- Controller 僅處理輸入輸出與錯誤映射
- 業務邏輯放 Service 層
- 資料存取集中 Repository
- 禁止在 Controller 直接拼 SQL

### 6.3 設定管理

- 連線與環境配置由 `application.properties` 管理
- 不將密碼硬寫入程式碼
- 變更 DB 設定時需同步更新部署說明

---

## 7. 正規化引擎（Python + C）維護規範

### 7.1 Python 正規化基線

- 新規則需可讀、可測、可回退
- 欄位驗證優先採安全失敗（invalid -> None）

### 7.2 C 引擎維護

- 介面變更需同步更新：
  - `include/*.h`
  - `src/*.c`
  - `src/tests/test_normalizer.c`
- `Makefile` 目標不可破壞（`make`, `make test`, `make clean`）

### 7.3 跨語言邊界

- C engine 為可插拔加速器，不取代 Python 編排層
- 跨語言資料交換格式需穩定且可追蹤

---

## 8. 推薦與分析邏輯維護規範

### 8.1 推薦層演進順序

- 先規則過濾（硬限制）
- 再權重評分（可解釋）
- 最後 ML 精煉（可選）

### 8.2 推薦變更要求

- 每次改分數權重需說明原因
- 保留可解釋欄位（不做黑盒替換）
- 禁止直接依賴未標準化 raw 欄位做最終決策

### 8.3 分析層原則

- 聚合邏輯與爬蟲流程解耦
- 指標定義必須可重現
- 分析結果需可追溯到來源批次

---

## 9. 例行維護作業（Runbook）

### 9.1 每週

- 檢查來源頁面結構是否有變動
- 抽樣確認前 10 所大學資料完整性
- 檢查 API 關鍵端點可用性
- 檢查是否出現「QS ranking 可抓但 detail 頁 403」模式，若發生則記錄批次時間、指令與錯誤比例

### 9.2 每月

- 盤點 schema 與索引是否仍符合查詢模式
- 檢查 alias 與實體對齊品質
- 檢查 C engine 與 Python 流程一致性

### 9.3 每季

- 回顧技術債與模組邊界偏移
- 校正路線圖與實際進度
- 更新 `MASTER_PROJECT_PLAN.md` 反映真實狀態

---

## 10. 架構異常處理與回滾策略

### 10.1 常見異常

- 來源網站改版導致提取失效
- schema 變更造成寫入失敗
- API 合約變動造成前後端不一致
- 實體識別錯配導致資料碎片化
- QS detail 頁回應 `403 Forbidden`（常見於 async 指紋或高頻 detail 請求）

### 10.4 QS Detail 403 標準處置（Runbook）

1. 先確認採集合規參數：`workers=1`、`request_delay=10`。
2. 若指令含 `--use-async` 且大量 detail 403，先改為同步模式重跑同批資料。
3. 若仍不穩定，先使用 `--rankings-only` 完成主資料，再分批補抓 detail。
4. 將本次 403 事件記錄到維運日誌（時間、limit、模式、成功/失敗比）。

### 10.2 回滾原則

- 高風險變更需保留前一版可回退路徑
- schema 變更需有 migration 與 rollback 腳本
- 推薦邏輯變更需保留上一版權重配置

### 10.3 事故後處置

1. 先止血（降級/關閉新邏輯）
2. 鎖定影響範圍（資料批次、端點、模組）
3. 產出根因與改善項
4. 補文件與補監控

---

## 11. 文件同步規範

任何影響架構的變更，至少同步更新以下文件之一：

- `MASTER_PROJECT_PLAN.md`（架構與路線）
- `README.md`（對外摘要）
- 本文件（維護流程與規範）

若變更包含 schema 或 API contract，三份文件都應更新。

---

## 12. 維護決策檢核清單

在合併任何中高風險變更前，請確認：

- 是否符合分層邊界
- 是否引入不必要的跨模組耦合
- 是否保留資料追溯能力
- 是否更新對應文件
- 是否具備回滾方案

---

> [!IMPORTANT]
> 本文件是 CrawlerNest 的架構維護作業基準。所有跨層變更、資料模型調整與服務介面演進，都應先對照本規範執行，避免架構漂移與技術債快速擴張。

---

## 13. 決策系統驗證（2026-03 更新）

本節驗證目前正式對外的決策能力：

- comparison
- recommendation v1
- recommendation v2
- recommendation v3
- Spring Boot decision APIs

### 13.1 Python 核心單元驗證

```bash
python3 -m py_compile \
  crawlernest/crawlernest-core/comparison/engine.py \
  crawlernest/crawlernest-core/comparison/repository.py \
  crawlernest/crawlernest-core/recommendation_engine/types.py \
  crawlernest/crawlernest-core/recommendation_engine/config.py \
  crawlernest/crawlernest-core/recommendation_engine/engine.py \
  crawlernest/crawlernest-core/recommendation_engine/repository.py \
  crawlernest/run_pipeline.py \
  crawlernest/crawlernest-tests/test_recommendation_engine.py \
  crawlernest/crawlernest-tests/test_recommendation_v2.py \
  crawlernest/crawlernest-tests/test_recommendation_v3.py \
  crawlernest/crawlernest-tests/test_comparison_engine.py
```

```bash
python3 crawlernest/crawlernest-tests/test_recommendation_engine.py
python3 crawlernest/crawlernest-tests/test_recommendation_v2.py
python3 crawlernest/crawlernest-tests/test_recommendation_v3.py
python3 crawlernest/crawlernest-tests/test_comparison_engine.py
```

### 13.2 PostgreSQL 前置檢查

先確認 PostgreSQL schema 與資料庫可用：

```bash
python3 crawlernest/scripts/bootstrap_postgres.py --user test --database clawer
psql -h localhost -U test -d clawer -c "select current_database();"
```

### 13.3 Pipeline 寫入驗證

如果前一次 run 有 `Skipped(resume)`，先清 checkpoint：

```bash
rm -f crawlernest/crawlernest-kb/databases/pipeline_checkpoint.json
rm -f crawlernest/crawlernest-kb/databases/pipeline_checkpoint.json.journal
```

執行 pipeline：

```bash
python3 crawlernest/run_pipeline.py run \
  --limit 30 \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-database clawer \
  --pg-user test
```

驗證重點：

- console 應看到 `[3/4] Writing ... rows to postgres...`
- `Inserted` 不應長期維持 0
- 若出現 `No canonical university profiles found`，需補 canonical seed

必要時補做 canonical seed：

```bash
python3 crawlernest/scripts/seed_canonical_from_universities.py --user test --database clawer
```

### 13.4 CLI comparison / recommendation 驗證

v1 recommendation：

```bash
python3 crawlernest/run_pipeline.py recommend \
  --country "United Kingdom" \
  --ielts-score 6.5 \
  --target-rank 100 \
  --preferred-ranking-source QS \
  --limit 5
```

v2 grouped recommendation：

```bash
python3 crawlernest/run_pipeline.py recommend-v2 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile balanced \
  --country "United Kingdom" \
  --limit 5 \
  --pg-user test \
  --pg-database clawer
```

v3 hybrid recommendation：

```bash
python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile aggressive \
  --country "United Kingdom" \
  --preference-weights '{"ranking":0.5,"ielts":0.2,"confidence":0.2,"country_match":0.1}' \
  --limit 5 \
  --pg-user test \
  --pg-database clawer
```

comparison：

```bash
python3 crawlernest/run_pipeline.py compare \
  --a "Oxford" \
  --b "LSE" \
  --pg-user test \
  --pg-database clawer
```

驗證重點：

- `recommend` 會回平面 shortlist
- `recommend-v2` / `recommend-v3` 會回 `reach` / `target` / `safety`
- `recommend-v3` 回傳 `preference_alignment`、`base_score`、`risk_adjustment`
- `compare` 回傳 `better`、`summary`、`comparison`
- `preferred-ranking-source=QS` 時，說明文字應優先顯示 `QS rank #...`

### 13.5 Conservative vs Aggressive 差異驗證

```bash
python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile conservative \
  --country "United Kingdom" \
  --pg-user test \
  --pg-database clawer > /tmp/rec_conservative.json

python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile aggressive \
  --country "United Kingdom" \
  --pg-user test \
  --pg-database clawer > /tmp/rec_aggressive.json

diff -u /tmp/rec_conservative.json /tmp/rec_aggressive.json
```

驗證重點：

- aggressive 應提高 reach 類別分數
- conservative 應提高 safety 類別分數
- `score_breakdown.risk_adjustment` 應隨 profile 改變

### 13.6 Spring Boot Decision API Smoke Test

先啟動 API：

```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

再執行 smoke test：

```bash
python3 crawlernest/scripts/smoke_test_recommendations_api.py --base-url http://localhost:8080
```

或直接呼叫：

```bash
curl "http://localhost:8080/recommendations?country=United%20Kingdom&ielts=6.5&targetRank=100&preferredRankingSource=QS&limit=3"
curl "http://localhost:8080/recommendations?version=v3&targetRank=100&ielts=6.5&country=United%20Kingdom&riskProfile=aggressive"
curl "http://localhost:8080/recommendations?version=v3&targetRank=100&ielts=6.5&country=United%20Kingdom&riskProfile=balanced&preferenceWeights=%7B%22ranking%22%3A0.5%2C%22ielts%22%3A0.2%2C%22confidence%22%3A0.2%2C%22country_match%22%3A0.1%7D"
curl "http://localhost:8080/compare?u1=Oxford&u2=LSE"
```

驗證重點：

- HTTP 200
- `/recommendations?version=v3` 至少一個分組存在
- `/compare` 回傳 deterministic comparison JSON
- 回傳欄位包含：
  - `canonicalUniversityId`
  - `universityName`
  - `country`
  - `aggregatedRank`
  - `ieltsMin`
  - `matchingScore`
  - `category`
  - `preferenceAlignment`
  - `explanation`

### 13.7 決策資料鏈前置檢查

若推薦結果為空，先檢查：

```bash
psql -h localhost -U test -d clawer -c "select count(*) from warehouse.universities;"
psql -h localhost -U test -d clawer -c "select count(*) from warehouse.canonical_university;"
psql -h localhost -U test -d clawer -c "select count(*) from warehouse.canonical_university_link;"
psql -h localhost -U test -d clawer -c "select count(*) from warehouse.ranking_record;"
psql -h localhost -U test -d clawer -c "select count(*) from analytics.v_aggregated_rankings_latest;"
psql -h localhost -U test -d clawer -c "select count(*) from analytics.v_recommendation_candidates_latest;"
```

正常基線（目前資料集）：

- `universities > 0`
- `canonical_university = 166`
- `canonical_university_link = 166`
- `ranking_record > 0`
- `v_aggregated_rankings_latest = 166`
- `v_recommendation_candidates_latest = 166`

## 14. 多來源排名整合測試（QS / THE / ARWU）

本節用於驗證目前已落地的多來源資料流：

**QS crawler / THE payload / ARWU payload -> entity resolution -> `warehouse.ranking_record` -> aggregation -> recommendation**

### 14.1 先跑單元測試

```bash
python3 -m unittest \
  crawlernest/crawlernest-tests/test_multi_source_pipeline.py \
  crawlernest/crawlernest-tests/test_recommendation_engine.py
```

驗證重點：

- THE / ARWU adapter 會輸出標準化欄位
- QS / THE / ARWU 會各自保留，不互相覆寫
- aggregation 會吃多來源資料
- recommender 預設走 aggregated rank，而不是 raw QS

### 14.2 驗證 QS 真實資料流

先執行現有 QS pipeline：

```bash
python3 crawlernest/run_pipeline.py run \
  --limit 5 \
  --ranking-year 2026 \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-database clawer \
  --pg-user test
```

若 console 出現以下訊息，代表 QS 已同步進 multi-source 流程並觸發 aggregation：

```text
[multi-source] rows=5 matched=5 unresolved=0 duplicates=0 aggregated_years=[2026]
```

### 14.3 準備 THE / ARWU 測試 payload

建立 `the_sample.json`：

```json
[
  {
    "id": "the:oxford",
    "institution": "University of Oxford",
    "country": "United Kingdom",
    "year": 2026,
    "rank_position": 1,
    "scores": { "overall": 98.5 },
    "profile_url": "https://example.test/the/oxford"
  }
]
```

建立 `arwu_sample.json`：

```json
[
  {
    "id": "arwu:oxford",
    "university_name": "University of Oxford",
    "country": "United Kingdom",
    "year": 2026,
    "overall_rank": 7,
    "total_score": null,
    "url": "https://example.test/arwu/oxford"
  }
]
```

注意：`--input-file` 必須使用實際存在的路徑，例如 `./the_sample.json`，不要寫成 `/crawlernest/the_sample.json`。

### 14.4 匯入 THE / ARWU

```bash
python3 crawlernest/run_pipeline.py ingest-rankings \
  --source THE \
  --input-file ./the_sample.json \
  --ranking-year 2026 \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-database clawer \
  --pg-user test
```

```bash
python3 crawlernest/run_pipeline.py ingest-rankings \
  --source ARWU \
  --input-file ./arwu_sample.json \
  --ranking-year 2026 \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-database clawer \
  --pg-user test
```

### 14.5 驗證 `ranking_record` 沒有互相覆寫

```sql
SELECT
  cu.display_name,
  rs.source_code,
  rr.ranking_year,
  rr.rank_position,
  rr.score
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs
  ON rs.ranking_source_id = rr.ranking_source_id
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = rr.canonical_university_id
WHERE cu.display_name ILIKE '%Oxford%'
ORDER BY rs.source_code;
```

期望結果：

- 同一所 Oxford 會有 `QS`、`THE`、`ARWU` 三筆
- 三筆 source 獨立存在
- 不會用 THE 或 ARWU 覆寫 QS

### 14.6 驗證 aggregation 輸出

```sql
SELECT
  cu.display_name,
  ar.ranking_year,
  ar.display_rank,
  ar.composite_score,
  ar.source_ranks_json,
  ar.source_normalized_scores_json,
  ar.source_weights_used_json
FROM analytics.v_aggregated_rankings_latest ar
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = ar.canonical_university_id
WHERE cu.display_name ILIKE '%Oxford%';
```

Oxford 測試案例期望值：

- QS = 3 -> `99.866667`
- THE = 1 -> `100.0`
- ARWU = 7 -> `99.4`
- composite score = `99.796667`
- final rank = `1`

對應範例程式：

```bash
python3 crawlernest/scripts/ranking_aggregation_example.py
```

### 14.7 驗證 recommender 已吃 aggregated rank

```bash
python3 crawlernest/run_pipeline.py recommend \
  --country "United Kingdom" \
  --target-rank 10 \
  --limit 5 \
  --ranking-year 2026 \
  --pg-host localhost \
  --pg-port 5432 \
  --pg-database clawer \
  --pg-user test
```

驗證重點：

- candidate 來自 `analytics.v_recommendation_candidates_latest`
- 未指定 `--preferred-ranking-source` 時，預設走 aggregated rank
- 指定 `--preferred-ranking-source QS` 時，才改走 QS rank

### 14.8 觀測與除錯

可檢查以下表確認 ingestion / unresolved / merge diagnostics：

```sql
SELECT * FROM analytics.source_ingestion_log ORDER BY ingestion_log_id DESC LIMIT 20;
SELECT * FROM analytics.missing_entity_log ORDER BY missing_entity_log_id DESC LIMIT 20;
SELECT * FROM analytics.merge_diagnostics ORDER BY diagnostics_id DESC LIMIT 20;
```

常見問題：

- `FileNotFoundError`
  - `--input-file` 路徑錯誤，請改用 `./the_sample.json` 或完整絕對路徑
- `No canonical university profiles found`
  - 尚未建立 canonical university / alias 資料，需先完成 entity resolution 基礎資料
- `ranking_record` 只有 QS
  - 表示 THE / ARWU payload 尚未匯入，或 entity resolution 沒命中
