# Clawer System Architecture Whitepaper

本文件為 Clawer 專案的技術架構白皮書（System Architecture Whitepaper），用於完整說明系統的分層設計、資料模型、資料流程、推薦架構與長期平台方向。其目標不是單純描述一個 crawler，而是定義一個可從資料採集逐步演進為 university data intelligence platform 的長期技術藍圖。

## Whitepaper Positioning

本文件定位為 Clawer 的 **Master Technical Architecture Document**，主要用途包括：

- 作為系統長期演進的最高架構參考
- 統一 crawler、database、analytics、recommendation 與 product layer 的設計語言
- 提供未來功能擴展、資料模型調整與平台演進時的核心依據

此文件偏重 **architecture / platform design / data model / recommendation system design**，而非單純的實作手冊。

因此，本文將同時描述：

- 系統目前的 V1 foundation
- 中長期的資料平台擴展方向
- 未來 recommendation engine 與 product layer 的技術藍圖



## How to Read This Whitepaper

閱讀順序建議如下：

1. **System Architecture Overview / System Layer Model**：先理解整體平台分層
2. **Data Platform Architecture Decisions**：再理解核心資料模型與資料流
3. **AI Recommendation Architecture**：最後理解 recommendation 與 decision engine 的長期方向
4. **Development Priorities / Milestones / Roadmap**：對照實際開發順序與長期演進規劃

若讀者的目標是實作當前版本，應優先聚焦 **Tier 1 / V1 school-level platform foundation**；若目標是理解長期產品方向，則應結合 Product Vision 與 AI Recommendation Architecture 一起閱讀。

---

## Table of Contents

1. System Architecture Overview (High-level)
2. System Scope
3. Executive Summary
4. 系統願景與現況評估 (Vision & Current State)
5. 核心技術架構與機制 (Core Architectural Strategy & Mechanisms)
6. 深度技術實作邏輯 (Detailed Implementation)
7. 匯出與格式化 (Export Capabilities)
8. 數據平台化架構決策 (Data Platform Architecture Decisions)
   - 8.1 Canonical Data Model
   - 8.2 Future Data Model Expansion
   - 8.3 SQL Schema (Reference Implementation)
   - 8.4 Recommended Indexes
   - 8.5 Table Responsibilities
8.6 Crawler Framework Architecture
8.7 Job-based Pipeline
8.8 Ranking Data Strategy
8.9 Platform Architecture
8.10 Architecture Principles
8.11 Entity Resolution Pipeline
8.12 AI Recommendation Architecture
   - 8.12.1 Multi-level Recommendation Roadmap
   - 8.12.2 Hybrid Recommendation Engine
   - 8.12.3 Recommendation Scoring Model
16. Major Project Milestones
17. 四年期發展路徑圖 (4-Year Roadmap)
18. 技術風險與維護策略 (Risk & Maintenance)
19. 模組完成度地圖 (Module Completion Map)

---


## System Architecture Overview (High-level)

The following diagram illustrates the long-term system architecture of Clawer as a university data intelligence platform.

```
                ┌─────────────────────┐
                │        CLI          │
                │     (Explorer)      │
                └──────────┬──────────┘
                           │
                     ┌─────▼─────┐
                     │  Crawler  │
                     │  Engine   │
                     └─────┬─────┘
                           │
                   Extraction Layer
                           │
            Python Validation / Normalization Layer
                           │
              C Data Normalization Engine (Prototype)
                           │
              ┌────────────▼────────────┐
              │ University Knowledge DB │
              │   (Rankings / Admission)│
              └────────────┬────────────┘
                           │
                     Analytics Layer
                           │
               AI Recommendation Engine
                           │
                 Future API / Web Platform
                 (Java Spring Boot Backend)
```

This architecture reflects the long-term design principle:

```
Crawler → Data Platform → Analytics → AI → Product
```

---

## System Layer Model (Architectural Layers)

為了更清楚描述 Clawer 的整體系統結構，可將整個平台抽象為五個主要技術層：

```
Layer 1 — Data Collection
    Ranking Crawlers / Admission Crawlers / Future Data Sources

Layer 2 — Data Quality & Normalization
    Python Validation / Safe Casting / C Data Normalization Engine

Layer 3 — Knowledge Base
    University Knowledge Base (Canonical Database)

Layer 4 — Analytics Layer
    Ranking Aggregation / Statistical Analysis / Recommendation Features

Layer 5 — Recommendation Engine
    Rule Filtering / Weighted Scoring / ML Refinement (Currently simulated in Spring Boot)

Layer 6 — Product Layer
    CLI Explorer / Future API / Future Web Platform (Currently powered by Java Spring Boot `servise_for_java`)
```

此分層模型可幫助理解 Clawer 的長期設計原則：

```
Data Collection → Knowledge Base → Analytics → AI Recommendation → Product
```

每一層均與上下層解耦，使系統可以逐步演進而不破壞既有架構。

## System Scope

Clawer is designed as a **university data intelligence platform** that aggregates global university rankings and admission requirements to support structured analysis and AI-assisted university decision making.

The system focuses on three core capabilities:

- **Data Aggregation**：自動採集多個國際大學排名與相關資料來源（QS、THE、ARWU 等）。
- **Structured Knowledge Base**：建立可查詢、可擴展的全球大學資料庫。
- **AI-assisted Decision Support**：利用分析與 AI 模型輔助選校與資訊比較。


The project is intentionally designed as a **long-term evolving system**, starting from a crawler-based data platform and gradually expanding into analytics, AI recommendation, and potential API/Web products.

### Executive Summary

Clawer 的核心不是單一爬蟲腳本，而是一個以 **data-first architecture** 為中心的長期系統。其發展順序明確為：

```
Crawler → Knowledge Base → Analytics → AI Recommendation → Product
```

因此，所有設計決策都遵循同一個原則：

- 先建立穩定的資料採集與資料模型
- 再建立可分析、可比對的資料平台
- 最後才向上發展 AI recommendation 與產品化介面

---

## 一、 系統願景與現況評估 (Vision & Current State)

### 1. 核心願景
建立一個能自動化、結構化並智慧分析全球大學排名與入學要求的長效型系統，支撐未來四年的留學數據需求。

### 2. 地基鞏固程度評估 (Foundational Solidity)
- **結構穩固性 (9/10)**：已形成明確的分層式系統結構，入口點、UI、crawler orchestration、fetcher、extractor、database writer、exporter 均已拆分。
- **環境適應力 (8/10)**：具備 NID 動態探測、同步 / 非同步抓取、分頁與 fallback 機制，能抵禦中小型網站改版與請求波動。
- **資料平台進展**：SQLite knowledge base、`clawer_main/schema.sql`、`clawer_main/db_writer.py`、crawl run tracking 與 raw source staging 已接入主流程；同時新增 **Clawer C Data Normalization Engine** 作為資料品質層的原型模組，代表系統已從單純 crawler 工具演進為 **crawler + knowledge base prototype with normalization engine direction**。
- **完成度概況**：採集引擎完成度約 80%，解析提取層約 70%，Python 正規化與驗證基線已建立，C 正規化引擎目前處於 prototype 階段；資料庫與 ingestion pipeline 已建立 baseline，entity resolution、ranking aggregation 與 AI recommendation 仍屬後續階段。

---

## 二、 核心技術架構與機制 (Core Architectural Strategy & Mechanisms)

### 1. 全域參數與組態機制 (Configuration Logic)
系統核心由 `Config` 類管理，採用 Python Dataclass 封裝，實現「參數化管理」：
- **網路請求控制**：透過 `asyncio.Semaphore` 限制最大進行中的協程數量 (`max_concurrent_requests = 200`)，並設定全域 30 秒中斷時間。
- **指數退避重試 (Exponential Backoff)**：`wait = retry_delay * (retry_backoff ** attempt)`，初始延遲 1.0s，退避倍率 2.0。

### 2. 數據獲取層：Schema-driven 與探針模式
為了應對頻繁改版，系統將從「硬編碼」轉向「配置驅動」：
- **Source Schema**：定義來源（如 QS）的 JSON/HTML 結構。
- **NID 自動發現算法**：啟動「探針模式」，透過多重 Regex 偵測鏈 (Script tags, HTML data attributes, API URLs) 定位 NID。
- **自動降級機制 (Fallback)**：若無法提取 NID，依據定義的關聯頁面列表自動跳轉，極大提高系統健壯性。

### 3. 解析提取層：視窗化滑動搜尋 (Windowed Extract)
- **視窗化算法**：設定 `window = 140`，在關鍵字前後 140 個字元內進行目標模式匹配，減少無關連數據干擾。
- **上下文隔離技術 (Context Isolation)**：利用 Regex 截取相關區段（如區分 Undergraduate 與 Postgraduate），避免學制要求混淆。
- **容錯機制**：欄位失效時標記 `unparsed` 並保留原始數據供後續稽核。

### 3.1 正規化引擎分層 (Normalization Engine Layering)

為了在資料進入 knowledge base 前提高一致性與可分析性，Clawer 的正規化層採取 **Python baseline + C prototype engine** 的雙層策略：

- **Python Normalization Baseline**：負責目前主流程中的 safe numeric casting、country normalization、欄位驗證與基本清洗。
- **Clawer C Data Normalization Engine**：作為高效能 prototype，聚焦於名稱正規化、國家標準化、排名區間解析、分數清洗與後續 duplicate detection 前處理。

目前 C engine 的定位不是取代整個 Python pipeline，而是作為未來可插拔的 **data quality accelerator / preprocessing module**。

### 4. 數據平台層：去重與實體識別 (Deduplication)
- **模糊匹配策略**：利用 Levenshtein 距離、縮寫擴展與 Token 匹配處理名稱不一致問題。
- **地理座標歸一化**：採用 `unicodedata` 進行 NFKD 正規化與字符過濾，並通過硬映射統一國家名稱。

---

## 三、 深度技術實作邏輯 (Detailed Implementation)

### 1. 特徵提取、驗證與正規化 (Extraction, Validation & Normalization)
- **數值解析**：針對分數範圍（如 `7.0-7.5`），執行算術平均運算 `(min + max) / 2` 輸出單一浮點數。
- **指標安全邊界**：
  * IELTS: `[0, 9.0]` | TOEFL: `[0, 120]` | GMAT: `[200, 800]` | GRE: `[260, 340]`
  * 若超出上述邊界，系統自動將該欄位設定為 `None`，防止統計偏差。
- **雙層正規化路徑**：短期由 Python pipeline 執行主流程驗證與 normalization；中長期則預留 C engine 處理高頻率字串清洗、rank parsing、score cleaning 與 duplicate-ready comparison string generation。

### 2. 區域過濾機制 (`_filter_nodes_for_region`)
區域排名核心邏輯包含三項原子操作（滿足其一即獲准）：
- **路徑匹配**：檢查 `resolved_url` 是否包含子區域 Slug。
- **標籤驗證**：檢查節點內部的 `region` 或 `subregion` 字串。
- **名單驗證**：檢查國家是否在預定義清單中。

### 3. 歸一化權重計算 (`calculate_overall_score`)
算法公式：$Score_{final} = \frac{\sum (Score_{raw} / Score_{max} \times 100)}{N_{valid}}$
確保不同量綱的分數 (如 GMAT 與 IELTS) 在總分權重中具有同等代表性。

---

## 四、 匯出與格式化 (Export Capabilities)

- **Console UI**：使用 Unicode Box-drawing Characters (`╔`, `═`, `║`) 構建高保真表格，寬度動態適配。
- **CSV 兼容性**：針對 CSV 匯出強制加入 UTF-8 BOM，解決 Windows Excel 第一列開頭亂碼問題。

---

## 五、 數據平台化架構決策 (Data Platform Architecture Decisions)

以下設計為目前專案已確認的 **V1 數據平台架構**，用於將現有的爬蟲工具升級為結構化數據系統。

### 1. 核心資料模型 (Canonical Data Model)

系統目前的 V1 / V1.5 canonical schema 已不再只是 school-level conceptual design，而是已開始落地為帶有 **warehouse-style dimensions / facts / raw lineage** 的 SQLite knowledge base。

目前核心資料表如下：

```
crawl_runs
countries
universities
university_aliases
raw_source_records
rankings
programs
degrees
admission_requirements
tuition
field_status_logs
```

資料表關係概念圖：

```
crawl_runs
   │
   ▼
raw_source_records

countries
   │
   ▼
universities ───────────── university_aliases
   │  │
   │  ├── rankings
   │  ├── admission_requirements
   │  ├── tuition
   │  └── programs ── degrees
   │
   └── field_status_logs
```

說明：

- `crawl_runs`：紀錄每次 crawler batch 的啟動、完成時間與狀態。
- `raw_source_records`：保存 raw / staging layer，用於來源追溯與後續重解析。
- `countries`：統一國家名稱與區域資料，是最基本的 dimension table。
- `universities`：系統核心實體表，是 canonical university identity 的主體。
- `university_aliases`：保存不同來源或不同名稱變體，支援未來 entity resolution。
- `rankings`：保存 ranking fact data（來源、類型、年份、rank、score、metrics_json）。
- `programs` / `degrees`：為未來 program-aware / degree-aware recommendation 預留的 dimension 結構。
- `admission_requirements`：保存 structured admission signals 與 raw parsing metadata。
- `tuition`：保存 tuition fact data，作為未來 budget fit 與 ROI analysis 的基礎。
- `field_status_logs`：記錄 parsing / normalization 狀態，支援資料品質治理。

### 1.1 Future Data Model Expansion

目前實作已從單純 school-centric schema 進一步演化為帶有 **crawl lineage + raw staging + structured fact tables** 的 knowledge base，但長期目標仍然是建立更完整的多層級資料模型：

```
University
   ↓
Program
   ↓
Degree
```

未來擴展方向包括：

- 將 admission / tuition / outcomes 更細緻地下沉到 program / degree level
- 在 canonical identity resolution 之上加入 alias、fuzzy matching 與 embedding matching
- 將 rankings、admission、tuition、career outcomes 與 third-party signals 統一轉化為 recommendation engine 的 decision signals
- 逐步建立 analytics-ready 與 ML-ready feature datasets
- 將 C-based normalization engine 視為可插拔 data quality layer，與 Python ingestion pipeline 透過 file exchange / ctypes / cffi / extension 等方式整合

因此，目前的 SQLite knowledge base 應被視為 **platform foundation + warehouse baseline**，而非最終資料模型。

### 1.2 SQL Schema (Reference Implementation)

**注意：目前實際的 `clawer_main/schema.sql` 已升級為 warehouse-style reference implementation，包含 crawl runs、raw source staging、dimensions、facts 與資料品質日志。**

目前 SQL schema 的核心結構可概括如下：

```sql
CREATE TABLE crawl_runs (
    crawl_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    ranking_type TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT DEFAULT 'running',
    notes TEXT
);

CREATE TABLE countries (
    country_id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_name TEXT NOT NULL UNIQUE,
    country_code TEXT UNIQUE,
    region_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE universities (
    university_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_slug TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    canonical_name TEXT,
    country_id INTEGER,
    city_name TEXT,
    website_url TEXT,
    qs_profile_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (country_id) REFERENCES countries(country_id)
);

CREATE TABLE university_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_school_name TEXT NOT NULL,
    match_type TEXT DEFAULT 'manual',
    confidence_score REAL DEFAULT 1.0,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    UNIQUE(source_name, source_school_name)
);

CREATE TABLE raw_source_records (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id INTEGER,
    source_name TEXT NOT NULL,
    record_type TEXT,
    ranking_type TEXT,
    source_url TEXT,
    raw_json TEXT,
    raw_text TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(crawl_run_id)
);

CREATE TABLE rankings (
    ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    raw_id INTEGER,
    ranking_source TEXT NOT NULL,
    ranking_type TEXT NOT NULL,
    ranking_year INTEGER,
    rank_start INTEGER,
    rank_end INTEGER,
    score REAL,
    metrics_json TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id)
);

CREATE TABLE admission_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    program_id INTEGER,
    degree_id INTEGER,
    raw_id INTEGER,
    source_url TEXT,
    gpa_min REAL,
    ielts_min REAL,
    toefl_min REAL,
    gre_min REAL,
    gmat_min REAL,
    application_deadline_text TEXT,
    raw_text TEXT,
    parsed_status TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id)
);
```

設計重點：

- **crawl_runs + raw_source_records** 提供 lineage 與 staging，方便 crawler batch 管理與未來重解析。
- **universities / countries / aliases** 作為 dimension layer，負責 canonical identity。
- **rankings / admission_requirements / tuition** 作為 fact-like tables，支撐 analytics 與 recommendation feature extraction。
- **metrics_json / raw_text / parsed_status** 保留 raw + structured hybrid design，兼顧可查詢性與可重建性。
- schema 已開始從傳統 crawler output storage 演化為 **analytics-friendly warehouse baseline**。

### 1.3 Recommended Indexes

目前實作中建議維持以下索引策略：

```sql
CREATE INDEX idx_countries_name ON countries(country_name);
CREATE INDEX idx_universities_slug ON universities(school_slug);
CREATE INDEX idx_universities_country ON universities(country_id);
CREATE INDEX idx_university_aliases_source_name ON university_aliases(source_name, source_school_name);
CREATE INDEX idx_raw_source_records_source_type ON raw_source_records(source_name, ranking_type);
CREATE INDEX idx_raw_source_records_crawl_run ON raw_source_records(crawl_run_id);
CREATE INDEX idx_rankings_university_year ON rankings(university_id, ranking_year);
CREATE INDEX idx_rankings_source_type ON rankings(ranking_source, ranking_type);
CREATE INDEX idx_rankings_raw ON rankings(raw_id);
CREATE INDEX idx_admission_requirements_university ON admission_requirements(university_id);
CREATE INDEX idx_field_status_logs_university ON field_status_logs(university_id);
```

這些索引主要支援：

- canonical university lookup
- country / ranking analytics
- raw lineage lookup
- crawl run traceability
- recommendation feature dataset construction

### 1.4 Table Responsibilities

#### crawl_runs
用於記錄每次 crawler batch 的執行狀態，是整個 warehouse pipeline 的 lineage 起點。

#### countries
作為基本 dimension table，統一國家名稱與區域資訊，避免同一國家在不同資料來源中碎片化。

#### universities
系統核心實體表。未來無論是 ranking、admission、tuition 或 recommendation，都應建立在 canonical `university_id` 之上。

#### university_aliases
目前已開始用於保存 source-specific school naming，未來將進一步擴展為完整的 entity resolution pipeline（manual → alias → fuzzy → embedding）。

#### raw_source_records
作為 raw / staging layer，保存 crawler 輸出的原始結構化資料、raw text 與來源資訊，確保所有 fact data 均可回溯。

#### rankings
保存 ranking fact data。此表只存 **原始 ranking records**，任何 ranking aggregation、normalization 與 composite score 應在 analytics layer 中計算。

#### admission_requirements
保存 admission 相關 fact data，並同時保留 parsing metadata（例如 `parsed_status`、`raw_text`、`application_deadline_text`），方便後續品質稽核與重新解析。

#### programs / degrees / tuition
目前主要作為 schema extension points，代表系統已為 future program-aware / degree-aware recommendation 預留資料模型基礎。

#### field_status_logs
此表不是主要業務資料表，而是資料品質治理與 parser traceability 的支撐表，應視為 trust / audit layer。

### 2. Crawler Framework 架構

系統由單一 crawler engine 驅動，不再使用獨立腳本。

```
Crawler Engine
     │
     ├─ Ranking Plugins
     ├─ Admission Crawlers
     └─ Future Data Sources (Tuition / Programs / Employment)
```

資料流程：

```
Source Page
↓
Fetcher
↓
Extractor
↓
Normalization
↓
Database
```

---

### 3. Job-based Pipeline

系統採用 **Job 級排程架構**：

```
qs_world
qs_subject
mit_admission
ucla_admission
ut_austin_admission
```

每個 Job 負責單一資料來源與 dataset。

優點：

- 易於排程
- 易於監控
- 易於錯誤隔離

---

### 4. Full Crawl 與 Incremental Update

V1 系統策略：

```
Full Crawl (Baseline)
+
Future Incremental Update
```

- Ranking datasets 先完整抓取（可達 1500+ universities）
- Admission / program pages 未來採 incremental refresh

---

### 5. Ranking Data Strategy

Ranking crawler 設計原則：

- 優先使用 **HTML extraction**（穩定性較高）
- API 僅作為未來優化

資料庫設計採用 **Unified Rankings Table Strategy**：

```
rankings
- ranking_source
- ranking_type
- university_id
- rank_start
- rank_end
- score
- metrics_json
- ranking_year
```

設計理念：

- **Single canonical rankings table**：所有排名來源（QS / THE / ARWU / future rankings）統一存入同一資料表，而非建立多個 ranking-specific tables。
- **rank_start / rank_end**：支援排名區間（例如 `201–250`）。
- **metrics_json**：儲存不同 ranking 的指標集合（如 QS 的 Academic Reputation、THE 的 Teaching / Research 等），避免 schema 膨脹。
- **ranking_source + ranking_type**：區分榜單來源與榜單類型（World / Subject / Sustainability / MBA 等）。

此策略確保系統未來能：

- 支援多 ranking 整合
- 進行 cross-ranking analytics
- 建立 AI ranking aggregation
- 支援未來 ranking source 的擴展

所有 ranking crawler 只負責寫入 **raw ranking data**，任何 normalization、scoring 或 AI ranking 將在 analytics layer 中計算。

### 6. Data Pipeline Long-term Structure

最終資料流：

```
Ranking Crawlers
Admission Crawlers
Future Data Sources
      ↓
University Knowledge Base
      ↓
Analytics Layer
      ↓
AI Recommendation Engine
```


### 6.1 End-to-End Data Pipeline (Operational View)

為了更清楚描述實際運作流程，下圖展示 crawler 到 AI recommendation 的完整資料流：

```
Crawler Jobs
     │
     ▼
Fetcher (HTTP / Async Requests)
     │
     ▼
Extractor (HTML / JSON Parsing)
     │
     ▼
Python Validation / Normalization Layer
     │
     ▼
C Data Normalization Engine (Prototype / Optional)
     │
     ▼
Database Writer
     │
     ▼
University Knowledge Base
     │
     ▼
Analytics Layer
     │
     ▼
AI Recommendation Engine
```

此 pipeline 明確分離：

- **採集層 (Crawling)**
- **資料處理層 (Extraction / Normalization)**
- **資料儲存層 (Knowledge Base)**
- **分析與決策層 (Analytics / AI)**

這種分層確保系統未來可以：

- 更換 crawler source 而不影響資料模型
- 重跑 normalization 與 analytics
- 在資料庫層之上構建新的產品功能

### 7.1 Platform Architecture

為了支援未來四年的產品化目標，Clawer 系統將逐步演進為一個 **University Data Platform**，並在其上建立 AI 決策層。此架構與目前的 crawler 系統保持相容，同時允許未來擴展 API 與 Web 平台。

整體架構如下：

```
                ┌──────────────────────────────┐
                │      CLI / Interactive UI    │
                └──────────────┬───────────────┘
                               │
                         ┌─────▼─────┐
                         │  Crawler  │
                         │Orchestrator│
                         └─────┬─────┘
                               │
                ┌──────────────┼──────────────┐
                │                              │
          Fetcher Layer                  Extractor Layer
                │                              │
                └──────────────┬──────────────┘
                               │
                       University Data Model
                               │
                Python Validation / Normalization Layer
                               │
                C Data Normalization Engine (Prototype)
                               │
                         DB Writer Layer
                               │
                 ┌─────────────▼─────────────┐
                 │ SQLite Knowledge Base /   │
                 │ Warehouse Baseline        │
                 └─────────────┬─────────────┘
                               │
                         Analytics Layer
                               │
                 ┌─────────────▼─────────────┐
                 │   AI Recommendation       │
                 │   & Decision Engine       │
                 └─────────────┬─────────────┘
                               │
                       Future API Platform
                               │
                       Future Web Platform
```

此設計遵循一個核心原則：

```
Crawler → Database → Analytics → AI → Product
```

說明：

- **Crawler Layer**：負責從 QS / THE / ARWU 等來源採集排名與相關資料。
- **University Knowledge Base**：系統的核心資料庫，儲存 canonical university data。
- **Analytics Layer**：負責 ranking aggregation、ROI analysis 與資料統計。
- **AI Decision Engine**：提供 personalized university recommendation。
- **API / Web Platform**：透過 `servise_for_java` (Spring Boot) 提供 REST API 端點（`/universities`, `/rankings`, `/recommendations`），並作為未來產品介面的服務後端。

此架構確保：

- Data pipeline 與 AI layer 解耦
- 未來能支援多 ranking 整合
- 系統可逐步產品化，而不影響現有 crawler 架構

### 7.2 Architecture Principles

為了確保 Clawer 在未來四年的擴展過程中保持可維護性與一致性，系統設計遵循以下核心原則：

- **Data-first Architecture**：優先建立穩定資料層，再向上發展 analytics 與 AI。
- **Schema-driven Extraction**：以資料結構與來源規格驅動採集邏輯，降低網站改版帶來的維護成本。
- **Layered Architecture**：Crawler、Normalization、Database、Analytics 與 AI Recommendation 分層實作，避免高耦合。
- **Source-agnostic Ranking System**：所有 ranking source 皆寫入統一的 canonical rankings schema，而非各自建立獨立系統。
- **Canonical Identity Resolution**：以 university_id 為核心，結合 manual mapping、alias、fuzzy matching 與 embedding matching 完成實體對齊。
- **Analytics-after-Storage**：所有 normalization、aggregation、AI scoring 皆在資料寫入後進行，避免 crawler 層過度複雜化。
- **Progressive Productization**：系統先完成 data platform，再逐步擴展為 API 與 Web product，而非一開始直接做完整產品介面。
- **Warehouse-first Persistence**：crawler output 不再只停留於 console / CSV，而是優先進入可追溯的 SQLite knowledge base。
- **Lineage-aware Data Design**：透過 `crawl_runs` 與 `raw_source_records` 保留資料來源、crawler batch 與解析上下文，支援未來品質治理與重解析。
- **Language-appropriate Modules**：對高頻率字串清洗與資料前處理採取 language-appropriate strategy，允許 Python 主流程與 C-based normalization engine 並存。

---

### 8. Entity Resolution Pipeline

為解決不同資料來源中學校名稱不一致的問題，系統採用多階段實體識別策略：

```
Raw School Name
      │
      ▼
Manual Mapping
      │
      ▼
Alias Table Lookup
      │
      ▼
Fuzzy Matching
      │
      ▼
Embedding Matching (AI)
      │
      ▼
Resolved school_id
```

說明：

- **Manual Mapping**：最高準確度，用於核心學校名稱。
- **Alias Table**：維護常見別名，例如 MIT / Massachusetts Institute of Technology。
- **Fuzzy Matching**：利用字串相似度處理小幅拼寫差異。
- **Embedding Matching**：透過語義向量比對處理複雜名稱變體。

Priority order：manual mapping → alias table → fuzzy matching → embedding matching

---

### 9. AI Recommendation Architecture

推薦系統在架構層可抽象為以下決策流程：

```
User Profile
   │
   ▼
Rule Filter
(Hard Constraints)
   │
   ▼
Candidate Set
   │
   ▼
University / Program / Degree Recommendation
   │
   ▼
Weighted Scoring Layer
   │
   ▼
ML Refinement Layer
   │
   ▼
Final Ranked Recommendations
```

此架構確保推薦系統具有三個關鍵特性：

- **可解釋性 (Explainability)**：Weighted scoring 能清楚說明推薦原因
- **可擴展性 (Extensibility)**：ML layer 可在未來逐步加入
- **多層級推薦能力 (Multi‑level Recommendation)**：同時支援 University / Program / Degree

第一階段由規則過濾不符合基本條件的候選項目，第二階段由 recommendation engine 計算推薦分數並排序。

長期目標不再只是 school-level recommendation，而是發展為 **multi-level recommendation system**：

```
V1：University-level Recommendation
V2：Program-aware Recommendation
V3：Degree-level Recommendation
V4：Multi-level Recommendation
```

也就是說，系統未來將同時支援：

- University recommendation
- Program recommendation
- Degree recommendation

此策略使 Clawer 從 ranking viewer 演進為真正的 education decision-support system。

---


#### 9.1 Multi-level Recommendation Roadmap

多層級推薦未來將依資料成熟度逐步推進：

- **University-level**：先回答「哪些學校適合你」
- **Program-aware**：再回答「哪些學程方向適合你」
- **Degree-level**：最後回答「哪些具體學位最適合你」

這樣的路線可避免一開始直接進入過度複雜的 degree-level recommendation。

#### 9.2 Hybrid Recommendation Engine

推薦系統的最終方向為 **Hybrid System (Rule + Weighted Scoring + ML Refinement)**。

其核心流程如下：

```
User Profile
   │
   ▼
Rule Filter
(Hard Constraints)
   │
   ▼
Candidate Set
   │
   ▼
Weighted Scoring Layer
   │
   ▼
ML Refinement Layer
   │
   ▼
Final Recommendations
```

設計原則：

- **Rule Filter**：先處理 IELTS / TOEFL / Budget / Country / Degree constraints
- **Weighted Scoring**：使用 ranking、admission probability、cost fit、location fit 等可解釋訊號計算基礎分數
- **ML Refinement**：未來當資料量足夠時，再用模型微調排序

這代表 recommendation engine 將不是單純的 ranking display，而是以多訊號融合為核心的 decision engine。

#### 9.3 Recommendation Scoring Model (Conceptual)

在 V1 / V2 階段，建議先以 weighted scoring 作為推薦核心：

```
RecommendationScore =
    CompositeRankingSignal
  + AdmissionProbability
  + BudgetFit
  + LocationPreference
  + OutcomeSignal
```

Where:

- **CompositeRankingSignal**：由 QS / THE / ARWU 等多來源 ranking 經過 normalization 與 aggregation 後形成
- **AdmissionProbability**：根據 GPA / IELTS / TOEFL 等條件估算錄取可能性
- **BudgetFit**：學費與預算匹配程度
- **LocationPreference**：國家或地區偏好
- **OutcomeSignal**：就業率、薪資、career outcome 或其他第三方訊號

此 scoring model 將作為 hybrid recommendation system 的可解釋核心，未來再由 ML layer 進一步微調排序。

---


---

## Development Priorities (Execution Strategy)

為避免專案範圍過度擴張（scope explosion），Clawer 的實際開發將分為三個優先級層級。  
此策略確保系統能 **先完成可運作的核心平台，再逐步擴展功能與 AI 層。**

### Tier 1 — 必做核心 (Foundational Platform)

這一層是整個系統能否成立的關鍵，必須優先完成。

核心目標：

```
Crawler → Normalization → Database → Query
```

包含：

- Ranking crawler（QS World Rankings）
- Canonical database schema（schools / rankings / admission tables）
- SQLite knowledge base
- 基本 Python normalization pipeline 與 C normalization engine prototype 對接方向
- CLI explorer / query interface
- Manual school mapping 機制

完成 Tier 1 之後，系統即具備：

- 基本資料平台能力
- 可持續更新的 university dataset
- 可查詢與分析的 ranking data

---

### Tier 2 — 該做擴展 (Data Platform Expansion)

在 Tier 1 穩定後逐步加入。

- Additional ranking sources（THE / ARWU）
- Admission requirements crawling
- Incremental update pipeline
- Alias table / fuzzy matching
- Ranking aggregation analytics
- 基礎 admission probability estimation
- Program taxonomy 初步設計
- 為 future degree-level data 預留 schema extension

此階段的目標是建立 **完整的 University Knowledge Base**。

---

### Tier 3 — 未來進化 (Advanced Intelligence Layer)

此層為長期目標，不影響核心平台運作。

- Hybrid recommendation engine
- Personalized university ranking
- Program-aware recommendation
- Degree-level recommendation
- LLM-based admission parsing
- Tuition / career outcome / third-party signal integration
- Future API platform
- Future web product

這一層將把 Clawer 從 **data platform** 推進為 **decision-support system**。

---

### Priority Principle

整個專案開發必須遵循以下順序：

```
Tier 1 → Tier 2 → Tier 3
```

任何新功能若影響 Tier 1 穩定性，應延後至 Tier 2 或 Tier 3。

此策略確保：

- 系統能快速產出可用成果
- 架構不會因過度設計而停滯
- 長期演進仍然保持清晰方向


## Major Project Milestones

本節描述的是 **平台能力里程碑 (platform capability milestones)**，用於定義系統在長期演進過程中必須達到的穩定能力節點。

實際開發優先順序仍應以 **Development Priorities (Tier 1 → Tier 2 → Tier 3)** 為準，以避免在早期階段過度擴展系統範圍。

The long-term development of Clawer is organized into a sequence of major technical milestones. Each milestone represents a stable platform capability that the system must achieve before moving to the next stage.

### Milestone 1 — Stable Crawling Infrastructure Capability

- 完成 ranking crawler 的穩定化
- 建立基本 extraction / normalization pipeline
- 支援 QS ranking dataset

### Milestone 2 — University Knowledge Base Capability

- 建立 canonical database schema
- 完成 school identity resolution
- 支援 admission requirements crawling

### Milestone 3 — Multi-Ranking Integration Capability

- 整合 QS / THE / ARWU rankings
- 建立 ranking aggregation
- 支援 cross-ranking analytics

### Milestone 4 — Multi-level AI-assisted Recommendation Capability

- 建立 hybrid recommendation engine
- 提供 university / program / degree multi-level recommendation
- 發展 AI decision support

---

## 十、 四年期發展路徑圖 (4-Year Roadmap)


Clawer 的四年演進路徑以「先資料平台、後 analytics、再 AI 與產品化」為核心原則。

### 已完成更新 Timeline

| 日期 | 更新內容 |
|---|---|
| 2026-02-04 | 初始錄取要求爬蟲 |
| 2026-02-05 | 修復模組路徑問題；添加 `beautifulsoup4` 和 `lxml` |
| 2026-02-11 ~ 2026-02-13 | 擴展排名邏輯和國家欄位支援 |
| 2026-02-14 | 控制台/UI 清理；學科超時處理完善 |
| 2026-02-15 | Brotli / SSL / 重試穩定性修復 |
| 2026-02-17 | 完成 v2.0 模組化重構 |
| 2026-02-19 | 預設啟用異步模式 |
| 2026-02-21 | 區域 / 永續性對齊與流程穩定 |
| 2026-02-24 | 添加學科和區域排名擴展；重新排序選單 |
| 2026-02-25 | 實作 QS 風格邊框、簡化標題、進度條 |
| 2026-02-28 | 性能優化與減少分頁工作 |
| 2026-03-06 | 添加 MBA / 商業碩士 / 學生城市排名並統一範圍選擇器 |
| 2026-03-08 | 爬蟲 → 資料庫資料匯入管線開發中 |
| 2026-03-09 | 優化 robots.txt 的合規機制，並完成 Clawer 的系統架構與長期發展規劃，使專案能從爬蟲工具演進為大學資料智慧平台 |
| 2026-03-11 | 建立私人repo |
| 2026-03-12 | 建立初始資料正規化引擎 |
| 2026-03-13 | 執行初始資料正規化引擎測試與修改 |
| 2026-03-15 | 專案結構模組化，分離 Python 主程式 (`clawer_main`) 與 C 正規化引擎 (`clawer_c_data_normalization_engine`) |
| 2026-03-16 | 建立初始java程式模組 |
| 2026-03-18 | java模組與主程式資料連接 |
### 階段 1：穩定化與規範化 (0–6 個月)
- **重點項目**：建立 `requirements.txt` 版本錨定、實作 `clawer_main/extractor.py` 的自動化單元測試、建立 HTML 靜態樣本庫以防止解析回歸，並完成 C normalization engine prototype 與主流程的邊界定義。

### 階段 2：基礎設施化與數據建模 (7–18 個月)
- **重點項目**：在既有 SQLite warehouse baseline 之上補強 PostgreSQL-ready schema、完成去重引擎邏輯、強化 crawl lineage / raw staging / data quality pipeline，並探索 C engine 與 Python ingestion pipeline 的整合方式。

### 階段 3：外部韌度與多源化 (19–30 個月)
- **重點項目**：整合住宅代理池、加入 THE/Shanghai ARWU 等其他國際排名、建立監控預警系統。

### 階段 4：智能分析與決策價值 (31–48 個月)
- **重點項目**：利用 LLM 輔助校驗複雜要求、完成 hybrid recommendation engine、逐步建立 university / program / degree multi-level recommendation，並產出趨勢預測報告。

---

## Product Vision (Long-term Platform Direction)

Clawer 的長期定位並非單一 crawler 工具，而是一個以 **university data intelligence** 為核心的資料平台。

在完整架構成熟後，平台可能支援以下產品形態：

- **University Data Explorer**：提供可查詢的全球大學資料平台
- **AI-assisted University Selection**：利用 recommendation engine 提供選校建議
- **Cross-ranking Analytics**：分析不同 ranking 之間的差異與趨勢
- **Education Decision Support System**：整合 ranking、admission、tuition、career outcomes 等訊號

其最終產品形態可抽象為：

```
University Data Platform
        ↓
Analytics Layer
        ↓
AI Decision Engine
        ↓
User-facing Products
```

此願景確保 Clawer 的技術架構能支撐未來的 API、Web 平台與資料分析產品。


## System Capability Map

為了更清楚描述 Clawer 在不同發展階段所具備的系統能力，下表將平台能力分為 **Foundation / Expansion / Intelligence / Productization** 四個層級。

| Capability Layer | Capability | Current Status | Long-term Direction |
| :--- | :--- | :---: | :--- |
| **Foundation** | Ranking crawling infrastructure | Active | 持續提升穩定性與可維護性 |
| **Foundation** | Canonical school-level schema | Active | 擴展為 program / degree-aware schema |
| **Foundation** | Manual school mapping | Active | 演進為 alias + fuzzy + embedding resolution |
| **Foundation** | SQLite-based knowledge base | Early | 升級為 PostgreSQL / analytics-ready storage |
| **Expansion** | Multi-ranking integration | Planned | 支援 QS / THE / ARWU / future sources |
| **Expansion** | Admission requirements ingestion | Planned | 擴展至更完整的 structured + raw admission data |
| **Expansion** | Program taxonomy | Planned | 建立 program-aware recommendation foundation |
| **Expansion** | Degree-level data model | Future | 支援 degree-aware comparison 與 recommendation |
| **Intelligence** | Ranking aggregation | Planned | 作為 recommendation engine 的 composite signal |
| **Intelligence** | Admission probability estimation | Planned | 作為 explainable recommendation feature |
| **Intelligence** | Hybrid recommendation engine | Future | Rule + weighted scoring + ML refinement |
| **Intelligence** | Multi-level recommendation | Future | University / Program / Degree recommendation |
| **Productization** | CLI explorer | Active | 持續作為 developer-facing interface |
| **Productization** | API layer | Future | 提供結構化資料與 recommendation service |
| **Productization** | Web platform | Future | 作為 user-facing decision support product |

此能力地圖的作用在於：

- 區分系統目前已具備的能力與未來方向
- 避免將 long-term vision 與 current implementation 混為一談
- 為未來 roadmap、priority 與 product evolution 提供更清楚的結構化視角

---

## 十一、 長期技術風險與維護策略 (Risk & Maintenance)

以下風險項目依據 crawler 系統、資料平台與 AI recommendation 三個層級進行整理。

| 風險範疇 | 風險項目 | 影響程度 | 緩解措施 |
| :--- | :--- | :---: | :--- |
| **技術層** | 網頁結構變動 | 極高 | 實施 Schema-driven 採集，降低維護成本。 |
| **生存層** | IP 封鎖與 WAF | 中 | 預留代理輪替接口，必要時導入 Headless 方案。 |
| **品質層** | 數據實體重複 | 高 | Priorities 第一階段後的去重引擎開發。 |

### 例行維護清單 (Routine Checklist)
- **季度**：抽核 Top 10 大學解析結果，驗證 DOM 結構穩定性。
- **隨時**：核心邏輯異動後，同步更新本技術主計畫書。

---

## 十二、 模組完成度地圖 (Module Completion Map)

下表描述目前各模組的相對成熟度，用於判斷未來開發優先順序。

| 模組名稱 | 功能描述 | 完成度 |
| :--- | :--- | :---: |
| **採集/網路層** | Async Stack, Endpoint Probing, Pagination | ~80% |
| **解析/提取層** | Requirement Extraction, Deadline Parsing, Status Tracking | ~75% |
| **Python 正規化/驗證層** | Country Canon, Safe Numeric Casting, Validation Baseline | ~60% |
| **C 正規化引擎** | Name / Country Normalization, Rank Parsing, Score Cleaning Prototype | ~25% |
| **去重 / 實體識別** | Alias Baseline, Manual Mapping, Future Fuzzy / Embedding | ~30% |
| **存儲/數據庫層** | Warehouse-style Schema, DB Writer, Crawl Run Tracking | ~55% |
| **驗證/質量層** | Raw Lineage, Field Status Logs, Parsing Metadata | ~35% |
| **分析/推薦前置層** | Ranking Aggregation / Recommendation Feature Design | ~20% |

---

> [!IMPORTANT]
> 本文件為 Clawer 專案的最高技術架構白皮書（Master Technical Architecture Whitepaper）。
>
> 所有重大技術決策、架構變更、資料模型調整與 recommendation system 演進，均應優先參考本文中的分層模型、設計原則與發展階段。
>
> 本白皮書的目的在於確保 Clawer 在長期演進過程中，始終維持：
> - 架構一致性
> - 資料模型可擴展性
> - recommendation system 的可解釋性與可演進性
> - platform foundation 與 product direction 之間的對齊
