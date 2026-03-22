# CrawlerNest 架構維護說明書

本文件定義 CrawlerNest 的架構維護原則、模組邊界、變更流程與例行維護方式。
目標是確保系統在持續演進時，仍維持一致性、可擴展性與可回溯性。

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

- SQLite：`crawlernest/crawlernest-schema/schema.sql`
- PostgreSQL：`crawlernest/crawlernest-schema/postgresql_schema.sql`

任何表結構變更必須同步兩份 schema（若該功能需跨環境）。

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
- 若需破壞式變更，必須提供版本策略（如 `/v2`）
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
