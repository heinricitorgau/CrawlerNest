# Repository Structure

CrawlerNest 目前採用「外層 workspace + 內層產品 workspace」的雙層 repo 佈局。  
這份文件專注在 **檔案 / 目錄架構**，幫助快速理解專案放了哪些東西、主要開發該看哪裡。

如果你要看的是系統怎麼運作、資料怎麼流、推薦與 aggregation 引擎怎麼分層，請改看：

- `docs/SYSTEM_ENGINE_ARCHITECTURE.md`

## 1. Top-Level Repository Layout

```text
repo-root/
├── README.md / README.zh-TW.md        # 專案總覽與使用說明
├── docs/                              # 架構、部署、參考文件
├── logs/                              # 本機或節點執行日誌
├── lobster-01/                        # Lobster-01 節點 runtime / deployment 資產
├── crawlernest/                       # 主產品與資料平台 workspace
├── agent/                             # agent / evaluator 開發層程式
├── mini_agent/                        # 輕量 agent 實驗或獨立介面
├── cli/                               # CLI 側程式
├── web/                               # 外層 web 程式
└── .vscode/                           # IDE 設定
```

## 2. Main Product Workspace

CrawlerNest 目前的主要可執行系統與產品模組大多位於 `crawlernest/` 之下。

```text
crawlernest/
├── run_pipeline.py                    # Python ingestion / crawl / ingest 主入口
├── run_platform.py                    # 平台模組啟動與整合入口
├── verify_db.py                       # PostgreSQL 驗證工具
├── pipeline/                          # 分段 pipeline 輔助模組
├── scripts/                           # 維運、migration、smoke test 腳本
│
├── crawlernest-core/                  # 核心領域邏輯
├── crawlernest-extractors/            # 爬蟲 / extractor
├── crawlernest-jobs/                  # job orchestration
├── crawlernest-db-writer/             # DB 寫入邏輯
├── crawlernest-schema/                # SQL schema / analytics / warehouse
├── crawlernest-analytics/             # 分析與匯出工具
├── crawlernest-tests/                 # Python 測試
├── crawlernest-kb/                    # snapshots / caches / knowledge artifacts
│
├── servise_for_java/                  # Spring Boot API
├── crawlernest-web/                   # Next.js 前端產品
│
├── crawlernest-autoeval/              # AutoEval dataset / report / runner
├── crawlernest-mini-agent/            # mini-agent 產品層 / 實驗層
│
├── crawlernest-api/                   # 舊 API / 過渡材料
├── crawlernest-recommendation/        # 舊推薦模組或 sidecar 材料
├── crawlernest-normalization/         # 舊 normalization 實作
├── crawlernest-normalization-py/      # Python normalization 側資料
├── crawlernest-cli/                   # CLI UX 工具
├── crawlernest-docs/                  # 舊文件鏡像
├── crawlernest-samples/               # 範例資料
└── crawlernest-infra/                 # 基礎設施資產與備忘
```

## 3. Core Development Areas

### 3.1 Runtime Entrypoints

```text
crawlernest/run_pipeline.py            # 最重要的 Python pipeline 入口
crawlernest/run_platform.py            # 平台層整合入口
crawlernest/verify_db.py               # DB 驗證與檢查
```

### 3.2 Python Core Modules

```text
crawlernest/crawlernest-core/
├── entity_resolution/                 # canonical identity / alias linking
├── multi_source/                      # QS/THE/ARWU 多來源整合
├── ranking_aggregation/               # aggregated ranking truth
├── recommendation_engine/             # explainable recommendation engine
├── comparison/                        # compare workflow 邏輯
├── constants/                         # 國家、區域、主題等常數
├── utils/                             # 共用工具
└── src/                               # 其他核心程式碼整理區
```

### 3.3 API Layer

```text
crawlernest/servise_for_java/src/main/java/clawer/
├── api/                               # REST controllers
├── service/                           # 業務邏輯
├── repository/                        # DB query / repository
├── dto/                               # request / response DTO
├── model/                             # model
├── domain/                            # domain objects
├── domain/ranking/                    # ranking domain 子模組
├── config/                            # Spring configuration
└── util/                              # 共用工具
```

### 3.4 Frontend Layer

```text
crawlernest/crawlernest-web/src/
├── app/                               # Next.js App Router pages
├── app/api/                           # API proxy / route handlers
├── app/rankings/                      # 排名頁
├── app/recommendations/               # 推薦頁
├── app/compare/                       # 比較頁
├── app/universities/                  # 學校詳情頁
├── components/                        # UI components
├── hooks/                             # React hooks
├── lib/                               # frontend utilities / data access
├── types/                             # TS types
└── __tests__/                         # frontend tests
```

## 4. Suggested Reading Order

第一次進 repo 建議用這個順序看：

1. `README.md`
2. `docs/REPO_STRUCTURE.md`
3. `docs/SYSTEM_ENGINE_ARCHITECTURE.md`
4. `crawlernest/run_pipeline.py`
5. `crawlernest/crawlernest-core/`
6. `crawlernest/servise_for_java/`
7. `crawlernest/crawlernest-web/`

## 5. Current Canonical Working Paths

目前最常碰的主路徑如下：

- Pipeline: `crawlernest/run_pipeline.py`
- Python core: `crawlernest/crawlernest-core/`
- Schema: `crawlernest/crawlernest-schema/`
- API: `crawlernest/servise_for_java/`
- Frontend: `crawlernest/crawlernest-web/`
- Knowledge artifacts: `crawlernest/crawlernest-kb/`
- Operations scripts: `crawlernest/scripts/`

## 6. Structural Notes

- repo 採雙層 workspace，功能上正常，但第一次看會有點混淆
- `servise_for_java/` 是歷史拼字，若要改名應獨立 migration
- `crawlernest/` 內同時存在 active modules 與 legacy / sidecar materials
- `.next/`、`target/`、`__pycache__/` 這類 build/cache 產物不應視為核心架構
