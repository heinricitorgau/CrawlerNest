# Repository Structure Legacy Notes

> Legacy context: this file preserves the previous long-form repository
> structure narrative. For current onboarding and directory ownership, use
> [../REPOSITORY_MAP.md](../REPOSITORY_MAP.md).

# Original: Repository Structure

CrawlerNest 目前是「外層 repo + 內層產品 workspace」的雙層結構。
這份文件只回答一件事：**檔案現在怎麼放、主要開發應該看哪裡**。

如果你要理解系統怎麼運作、資料怎麼流、哪些服務彼此相依，請看：

- `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md`

如果你要知道 **現在應該先開發哪一層**，請優先以這組標記理解本文件：

- `MAINLINE`：目前主線，優先投入工程時間
- `CONTROLLED EXPANSION`：可以做，但不能先於主線穩定
- `DEV-SUPPORT`：存在且可運作，但不屬於 production truth path
- `LEGACY / COMPAT`：舊材料、外層殼層、過渡用途

## 1. Top-Level Layout

```text
repo-root/
├── README.md / README.zh-TW.md        # 專案總覽、啟動方式、常用命令
├── docs/                              # 架構、部署、參考文件
├── crawlernest/                       # [MAINLINE] 主要產品 workspace（目前最重要）
├── crawlernest_admission_crawler/     # [MAINLINE] importable admission pipeline/trust package
├── crawlernest_ranking_crawler/       # [MAINLINE] importable ranking pipeline package
├── crawlernest_crawler_core/          # [MAINLINE] importable shared crawler runtime package
├── crawlernest-samples/               # 外層樣本 / artifact 輸出
├── logs/                              # 執行日誌
├── test_*.py                          # focused Python regression tests
├── legacy/                            # [LEGACY / COMPAT] 外層舊版/相容殼層與過渡材料
└── docker-compose.postgres.yml        # 本機 PostgreSQL 輔助配置
```

Sibling development-support repo：

```text
../crawlernest-agents                  # [DEV-SUPPORT] CrawlerNest-specific AI-assisted development agents
```

`crawlernest-agents` 不是本 repo 的 production dependency。它提供 curated engineering agents、workflow templates、debug prompts、review prompts 與 docs helpers，未來會與 CrawlerNest 一起開發，但仍應被視為 development companion，而不是資料管線、API、推薦或 web runtime 的一部分。

## 2. Canonical Workspace

目前實際上的主產品開發、資料管線、API、前端與新 agent 模組，都在 `crawlernest/` 之下。

```text
crawlernest/
├── run_pipeline.py                    # Python pipeline 主入口
├── run_platform.py                    # 模組化平台啟動入口
├── verify_db.py                       # DB 驗證工具
├── clawer.db / clawer.db.bak          # 本機 SQLite / 備份資料
│
├── pipeline/                          # [MAINLINE] 高層命令路由與 pipeline stage 協調
├── interfaces/                        # [MAINLINE] 內層 CLI / API 入口
├── core/                              # [MAINLINE] service facade（ranking / recommendation / university）
├── agent/                             # [DEV-SUPPORT] 現行 Python agent 系統
│
├── crawlernest-crawler-core/          # [MAINLINE] 共用 crawler runtime，可獨立演進的子專案
├── crawlernest-extractors/            # [MAINLINE] 共用 fetch / extract helper
├── crawlernest-ranking-crawler/       # [MAINLINE] ranking crawler 與 source adapters
├── crawlernest-admission-crawler/     # [MAINLINE] admission crawler / site profiles
├── crawlernest-jobs/                  # [MAINLINE] job routing、命令分派、批次控制
├── crawlernest-db-writer/             # [MAINLINE] DB 寫入工具
├── crawlernest-core/                  # [MAINLINE] 核心領域引擎
├── crawlernest-schema/                # [MAINLINE] PostgreSQL / SQLite schema 與 query assets
├── crawlernest-analytics/             # [CONTROLLED EXPANSION] 匯出與分析工具
├── crawlernest-kb/                    # [MAINLINE] crawl snapshots、cache、checkpoint、knowledge artifacts
├── crawlernest-samples/               # [MAINLINE] 內層樣本資料
│
├── servise_for_java/                  # [MAINLINE] Spring Boot API（名稱為歷史拼字）
├── crawlernest-web/                   # [MAINLINE] Next.js 前端
├── crawlernest-autoeval/              # [DEV-SUPPORT] extractor / autoloop evaluation
│
├── crawlernest-api/                   # [LEGACY / COMPAT] 舊 API / 過渡材料
├── crawlernest-cli/                   # [LEGACY / COMPAT] 舊 CLI UI 材料
├── crawlernest-docs/                  # [LEGACY / COMPAT] 舊文件鏡像
├── crawlernest-infra/                 # [LEGACY / COMPAT] infra 備忘與配置
├── crawlernest-normalization-py/      # [MAINLINE] Python normalization bridge + fallback
├── crawlernest-recommendation/        # [LEGACY / COMPAT] 舊推薦模組材料
└── crawlernest-tests/                 # [MAINLINE] Python 測試區
```

## 2.1 Outer Importable Packages

外層 root 也保留幾個可直接 import 的 Python packages。這些不是 legacy；它們是目前 pipeline / tests 會直接引用的主線模組，命名上使用 underscore 以符合 Python import convention。

```text
crawlernest_admission_crawler/         # [MAINLINE] admission pipeline + trust layer
├── models.py                          # admission records / normalized rows
├── validator.py                       # admission staging validation
├── resolver.py                        # deterministic resolved admission fields
├── signals.py                         # AdmissionSignal schema / confidence / validation
├── deadline_interpretation.py         # deadline priority interpretation
├── normalize.py
├── entity_resolver.py
├── warehouse_mapper.py
├── warehouse_writer.py
├── writer.py
└── crawlers/

crawlernest_ranking_crawler/           # [MAINLINE] ranking pipeline package
├── engine.py
├── models.py
├── validator.py
├── trust_layer.py
├── aggregator.py
├── entity_resolver.py
├── warehouse_mapper.py
├── warehouse_writer.py
└── sources/

crawlernest_crawler_core/              # [MAINLINE] importable shared crawler runtime
├── __init__.py
└── logger.py
```

注意：內層 `crawlernest/crawlernest-admission-crawler/` 與外層 `crawlernest_admission_crawler/` 目前並存。前者偏 crawler workspace / historical subproject layout；後者是 Python import path 與 focused tests 使用的 package。新增 admission trust schema、resolver、validation tests 時，優先確認 import path 是 `crawlernest_admission_crawler`。

## 3. Most Important Paths

### 3.1 Entrypoints

```text
crawlernest/run_pipeline.py            # [MAINLINE] ranking / admission / ingest / resolve 相關主入口
crawlernest/run_platform.py            # [CONTROLLED EXPANSION] 模組化 path bootstrap + clawer_main 啟動
crawlernest/verify_db.py               # [MAINLINE] DB 健檢
crawlernest/interfaces/cli/agent_cli/  # [DEV-SUPPORT] 現行 agent CLI
crawlernest/interfaces/api/agent_api/  # [DEV-SUPPORT] 現行 Python agent API server
```

### 3.2 Data Pipeline

```text
crawlernest/pipeline/                  # [MAINLINE]
├── bootstrap.py                       # repo/module path bootstrap
├── cli.py                             # parser 建置
├── router.py                          # 高層 command dispatch
├── stages/crawl_stage.py              # crawl stage
├── stages/write_stage.py              # write stage
└── utils/normalization.py             # 共用 normalization helper
```

### 3.3 Crawlers And Shared Runtime

```text
crawlernest/crawlernest-crawler-core/  # [MAINLINE] logger / runtime primitive / shared crawler subproject
crawlernest/crawlernest-extractors/    # [MAINLINE] fetcher.py / extractor.py
crawlernest/crawlernest-ranking-crawler/
├── sources/                           # QS 等 source modules
└── extractors/                        # ranking extraction helpers

crawlernest/crawlernest-admission-crawler/  # [MAINLINE]
├── crawlers/                          # admission crawlers
├── extractors/                        # admission extraction helpers
└── site_profiles/                     # site-specific profiles

補充原則：

- `crawlernest-crawler-core/` 可以單獨維護與版本化思考，但仍屬於目前主產品 workspace 的 shared dependency。
- 它只承接 crawler runtime primitive，不承接 ranking-specific、admission-specific、或 recommendation-specific 邏輯。
- admission trust schema / resolver 的 importable implementation 目前位於外層 `crawlernest_admission_crawler/`。
```

### 3.4 Core Domain Engine

```text
crawlernest/crawlernest-core/          # [MAINLINE]
├── entity_resolution/                 # canonical identity / alias linking
├── multi_source/                      # [CONTROLLED EXPANSION] QS / THE / ARWU 多來源整合
├── ranking_aggregation/               # [CONTROLLED EXPANSION] aggregated ranking engine
├── recommendation_engine/             # [CONTROLLED EXPANSION] explainable recommendation engine
├── comparison/                        # [CONTROLLED EXPANSION] compare workflow
├── constants/                         # country / region / preset constants
├── utils/                             # shared helpers
└── src/                               # 補充實作與資產
```

### 3.5 Service Facade And Interfaces

```text
crawlernest/core/services/             # [MAINLINE]
├── ranking_service.py
├── recommendation_service.py          # recommendation facade + admissionResolved metadata + compact decision summary
└── university_service.py

crawlernest/interfaces/api/agent_api/  # [DEV-SUPPORT]
├── dto.py
├── handler.py
└── server.py

crawlernest/interfaces/cli/agent_cli/  # [DEV-SUPPORT]
├── __main__.py
└── main.py
```

這層的角色是把 `crawlernest-core/`、`agent/` 與資料來源包成較穩定的 CLI / API 邊界。

### 3.6 Agent System

```text
crawlernest/agent/                     # [DEV-SUPPORT]
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
crawlernest/servise_for_java/src/main/java/clawer/  # [MAINLINE]
├── api/
├── service/
├── repository/
├── dto/
├── model/
├── domain/
├── config/
└── util/

crawlernest/crawlernest-web/src/       # [MAINLINE]
├── app/                               # App Router pages
├── app/api/                           # API proxy / route handlers
├── app/rankings/
├── app/recommendations/               # recommendation flow, decision banner, export text
├── app/compare/
├── app/universities/
├── app/agent/
├── app/preview/
├── components/                        # shared UI, including AdmissionSignalBadge
├── hooks/
├── lib/
├── types/
└── __tests__/                         # page/component tests, including recommendation export and admission signal badge
```

### 3.8 Data, Schema, Evaluation

```text
crawlernest/crawlernest-schema/        # [MAINLINE] SQL schema / queries / subject ranking ids
crawlernest/crawlernest-kb/            # [MAINLINE] snapshot / resolution cache / checkpoint / local DB
crawlernest/crawlernest-samples/       # [MAINLINE] examples / csv / demo artifacts
crawlernest/crawlernest-autoeval/      # [DEV-SUPPORT] datasets / runners / reports / sandbox
crawlernest/crawlernest-analytics/     # [CONTROLLED EXPANSION] exporter / analytics helpers
```

### 3.9 Focused Test Files

```text
test_admission_signals.py              # [MAINLINE] AdmissionSignal schema / confidence / validation tests
test_admission_resolver.py             # [MAINLINE] deterministic admission resolver tests
crawlernest/crawlernest-tests/test_recommendation_engine.py
                                        # [MAINLINE] recommendation service, decision messaging, compact summary tests
crawlernest/crawlernest-web/src/__tests__/AdmissionSignalBadge.test.tsx
                                        # [MAINLINE] admission trust UI badge tests
crawlernest/crawlernest-web/src/__tests__/RecommendationPageExport.test.tsx
                                        # [MAINLINE] decision summary export / banner tests
```

## 4. Reading Order

第一次進 repo，建議用這個順序理解：

1. `README.md`
2. `docs/architecture/REPO_STRUCTURE.md`
3. `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md`
5. `crawlernest/run_pipeline.py`
6. `crawlernest/pipeline/`
7. `crawlernest/crawlernest-admission-crawler/`
8. `crawlernest_admission_crawler/`
9. `crawlernest/crawlernest-normalization-py/` (bridge) / `crawlernest/crawlernest-normalization/` (C engine)
10. `crawlernest/crawlernest-core/`
11. `crawlernest/core/services/`
12. `crawlernest/servise_for_java/`
13. `crawlernest/crawlernest-web/`
14. `crawlernest/agent/`（確認主線後再看）

## 5. Practical Notes

- `crawlernest/` 是目前 canonical workspace；外層 `agent/`、`mini_agent/`、`interfaces/`、`web/` 比較像早期原型或兼容殼層。
- 若你的目標是跟著現在的主線開發，請優先看所有標為 `MAINLINE` 的路徑，再看 `CONTROLLED EXPANSION`，最後才看 `DEV-SUPPORT`。
- `servise_for_java/` 是歷史拼字；若之後要改名，應視為獨立 migration，不建議在一般重構中順手調整。
- `crawlernest-web/.next/`、`node_modules/`、`servise_for_java/target/`、各處 `__pycache__/` 都是 build/cache 產物，不應列入核心架構理解。
- `crawlernest-kb/` 與 `crawlernest-samples/` 都會出現資料 artifact；前者偏 runtime snapshots / cache / checkpoint，後者偏範例與預覽輸出。
- `admissionResolved`、`decisionSummaryCompact`、AdmissionSignalBadge 與 Decision Snapshot export 屬於 decision product / explainability layer；它們的主要實作散落在 outer admission package、`crawlernest/core/services/recommendation_service.py` 與 `crawlernest/crawlernest-web/src/`。
- 文件與測試中若同時看到 hyphenated subproject path 與 underscored Python package path，請以實際 import path 為準。
