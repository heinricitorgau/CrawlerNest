# Repository Structure

CrawlerNest 目前是「外層 repo + 內層產品 workspace」的雙層結構。
這份文件只回答一件事：**檔案現在怎麼放、主要開發應該看哪裡**。

如果你要理解系統怎麼運作、資料怎麼流、哪些服務彼此相依，請看：

- `docs/SYSTEM_ENGINE_ARCHITECTURE.md`

## 1. Top-Level Layout

```text
repo-root/
├── README.md / README.zh-TW.md        # 專案總覽、啟動方式、常用命令
├── docs/                              # 架構、部署、參考文件
├── crawlernest/                       # 主要產品 workspace（目前最重要）
├── crawlernest-samples/               # 外層樣本 / artifact 輸出
├── lobster-01/                        # 節點部署與 runtime 資產
├── logs/                              # 執行日誌
├── agent/                             # 外層舊版/簡化 agent 原型
├── mini_agent/                        # 外層簡化 mini-agent 原型
├── interfaces/                        # 外層介面殼層
├── web/                               # 外層 web 殼層
├── runtime/                           # 外層 runtime 設定
├── scripts/                           # 外層腳本
└── docker-compose.postgres.yml        # 本機 PostgreSQL 輔助配置
```

## 2. Canonical Workspace

目前實際上的主產品開發、資料管線、API、前端與新 agent 模組，都在 `crawlernest/` 之下。

```text
crawlernest/
├── run_pipeline.py                    # Python pipeline 主入口
├── run_platform.py                    # 模組化平台啟動入口
├── verify_db.py                       # DB 驗證工具
├── clawer.db / clawer.db.bak          # 本機 SQLite / 備份資料
│
├── pipeline/                          # 高層命令路由與 pipeline stage 協調
├── interfaces/                        # 內層 CLI / API 入口
├── core/                              # service facade（ranking / recommendation / university）
├── agent/                             # 現行 Python agent 系統
│
├── crawlernest-crawler-core/          # 共用 crawler runtime
├── crawlernest-extractors/            # 共用 fetch / extract helper
├── crawlernest-ranking-crawler/       # ranking crawler 與 source adapters
├── crawlernest-admission-crawler/     # admission crawler / site profiles
├── crawlernest-jobs/                  # job routing、命令分派、批次控制
├── crawlernest-db-writer/             # DB 寫入工具
├── crawlernest-core/                  # 核心領域引擎
├── crawlernest-schema/                # PostgreSQL / SQLite schema 與 query assets
├── crawlernest-analytics/             # 匯出與分析工具
├── crawlernest-kb/                    # crawl snapshots、cache、checkpoint、knowledge artifacts
├── crawlernest-samples/               # 內層樣本資料
│
├── servise_for_java/                  # Spring Boot API（名稱為歷史拼字）
├── crawlernest-web/                   # Next.js 前端
├── crawlernest-mini-agent/            # 獨立 mini-agent 產品 / runtime / Rust crates
├── crawlernest-autoeval/              # extractor / autoloop evaluation
│
├── crawlernest-api/                   # 舊 API / 過渡材料
├── crawlernest-cli/                   # 舊 CLI UI 材料
├── crawlernest-docs/                  # 舊文件鏡像
├── crawlernest-infra/                 # infra 備忘與配置
├── crawlernest-normalization/         # normalization 實作（含 C engine）
├── crawlernest-normalization-py/      # Python normalization 材料
├── crawlernest-recommendation/        # 舊推薦模組材料
└── crawlernest-tests/                 # Python 測試區
```

## 3. Most Important Paths

### 3.1 Entrypoints

```text
crawlernest/run_pipeline.py            # ranking / admission / ingest / resolve 相關主入口
crawlernest/run_platform.py            # 模組化 path bootstrap + clawer_main 啟動
crawlernest/verify_db.py               # DB 健檢
crawlernest/interfaces/cli/agent_cli/  # 現行 agent CLI
crawlernest/interfaces/api/agent_api/  # 現行 Python agent API server
```

### 3.2 Data Pipeline

```text
crawlernest/pipeline/
├── bootstrap.py                       # repo/module path bootstrap
├── cli.py                             # parser 建置
├── router.py                          # 高層 command dispatch
├── stages/crawl_stage.py              # crawl stage
├── stages/write_stage.py              # write stage
└── utils/normalization.py             # 共用 normalization helper
```

### 3.3 Crawlers And Shared Runtime

```text
crawlernest/crawlernest-crawler-core/  # logger / runtime primitive
crawlernest/crawlernest-extractors/    # fetcher.py / extractor.py
crawlernest/crawlernest-ranking-crawler/
├── sources/                           # QS 等 source modules
└── extractors/                        # ranking extraction helpers

crawlernest/crawlernest-admission-crawler/
├── crawlers/                          # admission crawlers
├── extractors/                        # admission extraction helpers
└── site_profiles/                     # site-specific profiles
```

### 3.4 Core Domain Engine

```text
crawlernest/crawlernest-core/
├── entity_resolution/                 # canonical identity / alias linking
├── multi_source/                      # QS / THE / ARWU 多來源整合
├── ranking_aggregation/               # aggregated ranking engine
├── recommendation_engine/             # explainable recommendation engine
├── comparison/                        # compare workflow
├── constants/                         # country / region / preset constants
├── utils/                             # shared helpers
└── src/                               # 補充實作與資產
```

### 3.5 Service Facade And Interfaces

```text
crawlernest/core/services/
├── ranking_service.py
├── recommendation_service.py
└── university_service.py

crawlernest/interfaces/api/agent_api/
├── dto.py
├── handler.py
└── server.py

crawlernest/interfaces/cli/agent_cli/
├── __main__.py
└── main.py
```

這層的角色是把 `crawlernest-core/`、`agent/` 與資料來源包成較穩定的 CLI / API 邊界。

### 3.6 Agent System

```text
crawlernest/agent/
├── engine/                            # agent engine
├── planner/                           # planning
├── orchestration/                     # task orchestration
├── tools/                             # ranking / university / recommendation tools
├── web_agent/                         # 面向 web product 的 agent stack
├── memory_long_term/                  # long-term memory
├── service/ / services/               # service facade
├── policies/                          # policy modules
├── validation/                        # validation
└── self_improvement/                  # self-improvement workflows
```

### 3.7 Product Surfaces

```text
crawlernest/servise_for_java/src/main/java/clawer/
├── api/
├── service/
├── repository/
├── dto/
├── model/
├── domain/
├── config/
└── util/

crawlernest/crawlernest-web/src/
├── app/                               # App Router pages
├── app/api/                           # API proxy / route handlers
├── app/rankings/
├── app/recommendations/
├── app/compare/
├── app/universities/
├── app/agent/
├── app/preview/
├── components/
├── hooks/
├── lib/
├── types/
└── __tests__/
```

### 3.8 Data, Schema, Evaluation

```text
crawlernest/crawlernest-schema/        # SQL schema / queries / subject ranking ids
crawlernest/crawlernest-kb/            # snapshot / resolution cache / checkpoint / local DB
crawlernest/crawlernest-samples/       # examples / csv / demo artifacts
crawlernest/crawlernest-autoeval/      # datasets / runners / reports / sandbox
crawlernest/crawlernest-analytics/     # exporter / analytics helpers
```

## 4. Reading Order

第一次進 repo，建議用這個順序理解：

1. `README.md`
2. `docs/REPO_STRUCTURE.md`
3. `docs/SYSTEM_ENGINE_ARCHITECTURE.md`
4. `crawlernest/run_pipeline.py`
5. `crawlernest/pipeline/`
6. `crawlernest/crawlernest-core/`
7. `crawlernest/core/services/`
8. `crawlernest/interfaces/api/agent_api/`
9. `crawlernest/servise_for_java/`
10. `crawlernest/crawlernest-web/`

## 5. Practical Notes

- `crawlernest/` 是目前 canonical workspace；外層 `agent/`、`mini_agent/`、`interfaces/`、`web/` 比較像早期原型或兼容殼層。
- `servise_for_java/` 是歷史拼字；若之後要改名，應視為獨立 migration，不建議在一般重構中順手調整。
- `crawlernest-web/.next/`、`node_modules/`、`servise_for_java/target/`、各處 `__pycache__/` 都是 build/cache 產物，不應列入核心架構理解。
- `crawlernest-kb/` 與 `crawlernest-samples/` 都會出現資料 artifact；前者偏 runtime snapshots / cache / checkpoint，後者偏範例與預覽輸出。
