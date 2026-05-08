# System And Engine Architecture Legacy Notes

> Legacy context: this file preserves the previous long-form system and engine
> architecture narrative. For current architecture, data flow, and API maps, use
> [../ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md),
> [../DATA_FLOW.md](../DATA_FLOW.md), and [../API_SURFACE.md](../API_SURFACE.md).

# Original: System And Engine Architecture

以圖為主；repo 目錄對照請看 `docs/architecture/REPO_STRUCTURE.md`。

本文件是 **CrawlerNest 唯一的 system / engine architecture 文件**。
它同時承擔兩個角色：

1. 說明目前可執行的主線架構
2. 說明較長期的 vision architecture

也就是說，這份文件不再拆成 execution / vision 兩份，而是用同一份文件清楚區分：
- 現在真正該跑、該維護、該驗證的是什麼
- 長期要演進到哪裡

目前 CrawlerNest 的主線仍應遵守 correctness-first 的 no-skip 順序：

1. 穩定 crawl / extract
2. 穩定 normalization / canonical mapping
3. 正式化 warehouse / API contract
4. 建立 admission-aware recommendation
5. 最後才逐步擴大 agent autonomy

foundation 規範文件仍然是主線執行邊界的重要補充，但 system / engine 的總敘事，以這一份文件為唯一來源。

## 0. Current Executable Architecture

目前真正應該被視為 production-oriented mainline 的，是這條路徑：

`crawl -> extract -> normalize -> write -> warehouse -> API -> web`

在 execution reality 中，CrawlerNest 應理解為三個區域：

1. **Active Data Pipeline**
2. **Controlled Expansion**
3. **Development Support / Future Expansion**

```mermaid
flowchart TD
    subgraph LAYER_A["Layer A: Active Data Pipeline (RUNNING)"]
        direction LR

        subgraph INGEST_ACTIVE["Ingestion"]
            PIPE_A["[ACTIVE] run_pipeline.py / pipeline/"]
            JOBS_A["[ACTIVE] crawlernest-jobs/"]
            RCRAWL_A["[ACTIVE] crawlernest-ranking-crawler/"]
            ACRAWL_A["[LIMITED] crawlernest-admission-crawler/"]
            EXT_A["[ACTIVE] crawlernest-extractors/"]
        end

        subgraph CORE_ACTIVE["Core Domain"]
            NORM_A["[ACTIVE] normalization"]
            WRITE_A["[ACTIVE] crawlernest-db-writer/"]
            ER_A["[ACTIVE] entity_resolution"]
            WH_A["[ACTIVE] warehouse (ranking + admission)"]
        end

        subgraph INTERFACE_ACTIVE["Interface"]
            JAVA_A["[ACTIVE] servise_for_java / REST API"]
            WEB_A["[ACTIVE] crawlernest-web"]
        end
    end

    subgraph LAYER_B["Layer B: Controlled Expansion (PARTIAL)"]
        direction LR
        ADM_ENRICH["[LIMITED] admission enrichment / pilot scope"]
        BASIC_REC["[ACTIVE] recommendation_engine / decision product metadata"]
        ADM_TRUST["[ACTIVE] admission trust signals / resolver"]
    end

    subgraph LAYER_C["Layer C: Development Support / Future Expansion"]
        direction LR
        AGG_F["[FUTURE] multi_source + ranking_aggregation"]
        AGENT_F["[DEV-SUPPORT] crawlernest/agent/"]
        MINI_F["[DEV-SUPPORT] crawlernest-mini-agent/"]
        AUTOEVAL_F["[DEV-SUPPORT] crawlernest-autoeval/"]
        CAGENTS_F["[DEV-SUPPORT] ../crawlernest-agents"]
    end

    PIPE_A --> JOBS_A
    JOBS_A --> RCRAWL_A
    JOBS_A --> ACRAWL_A
    RCRAWL_A --> EXT_A
    ACRAWL_A --> EXT_A
    EXT_A --> NORM_A
    NORM_A --> WRITE_A
    WRITE_A --> ER_A
    ER_A --> WH_A
    WH_A --> JAVA_A
    JAVA_A --> WEB_A

    ACRAWL_A -. pilot feed .-> ADM_ENRICH
    ADM_ENRICH -. signal layer .-> ADM_TRUST
    ADM_TRUST -. metadata only .-> BASIC_REC
    WH_A -. optional read .-> BASIC_REC
    BASIC_REC -. optional API path .-> JAVA_A
    ADM_ENRICH -. controlled write .-> WH_A

    ER_A -. future expansion .-> AGG_F
    WH_A -. future expansion .-> AGG_F

    AUTOEVAL_F -. dev support only .-> AGENT_F
    MINI_F -. dev support only .-> AGENT_F
    CAGENTS_F -. engineering companion .-> AGENT_F
```

### 0.1 Execution Principles

- Agent is not part of production data path.
- Admission crawler is in controlled pilot stage.
- Data correctness > automation.
- Correctness-first sequencing overrides capability breadth.
- Development support layers may evolve, but must not outrun crawl / normalization / canonical / warehouse stability.
- Admission trust signals are metadata for explanation, not scoring inputs.
- Decision summaries, assistant replies, UI badges, and exports must stay aligned to the same deterministic recommendation result.
- `../crawlernest-agents` may support engineering workflows, review, debugging, and documentation, but it is not part of production runtime or production truth.

### 0.2 Regression-Safe Admission Loop

Admission extraction 的改進應理解為受控 improvement loop，而不是 production truth path 的替代品。

- anomaly signals 必須可觀測
- extractor pattern fix 必須先過 eval / regression / summary
- pipeline output 必須能回溯到 anomaly breakdown
- extracted admission values must first become `AdmissionSignal`
- resolved admission values enter recommendation output as `admissionResolved` metadata only

## 1. System Overview

```mermaid
flowchart TD
    SRC["External Sources<br/>QS / THE / ARWU / university sites"]

    subgraph INGEST["Ingestion And Crawl"]
        PIPE["run_pipeline.py"]
        PSTAGE["pipeline/"]
        JOBS["crawlernest-jobs/"]
        RCRAWL["crawlernest-ranking-crawler/"]
        ACRAWL["crawlernest-admission-crawler/"]
        EXT["crawlernest-extractors/"]
        WRITE["crawlernest-db-writer/"]
        KB["crawlernest-kb/"]
    end

    subgraph CORE["Core Domain"]
        NORM["normalize"]
        ER["entity_resolution"]
        MS["multi_source"]
        AGG["ranking_aggregation"]
        ASIG["admission signals / resolver"]
        REC["recommendation_engine"]
        CMP["comparison"]
        SCHEMA["crawlernest-schema/"]
    end

    subgraph SERVICE["Service And Interface"]
        FACADE["core/services/"]
        PAPI["interfaces/api/agent_api"]
        PCLI["interfaces/cli/agent_cli"]
        JAVA["servise_for_java"]
    end

    subgraph PRODUCT["Product"]
        WEB["crawlernest-web"]
    end

    subgraph AGENT["Agent And Improvement"]
        AGS["crawlernest/agent/"]
        MINI["crawlernest-mini-agent/"]
        EVAL["crawlernest-autoeval/"]
    end

    SRC --> PIPE
    SRC --> JOBS
    PIPE --> PSTAGE
    PSTAGE --> RCRAWL
    PSTAGE --> ACRAWL
    JOBS --> RCRAWL
    JOBS --> ACRAWL
    RCRAWL --> EXT
    ACRAWL --> EXT
    EXT --> NORM
    PIPE --> WRITE
    PIPE --> KB
    WRITE --> ER
    NORM --> ER
    SCHEMA --> ER
    ER --> MS
    SCHEMA --> MS
    MS --> AGG
    SCHEMA --> AGG
    ACRAWL --> ASIG
    ASIG --> REC
    AGG --> REC
    AGG --> CMP
    AGG --> FACADE
    REC --> FACADE
    CMP --> FACADE
    FACADE --> JAVA
    FACADE --> PAPI
    FACADE --> PCLI
    JAVA --> WEB
    PAPI --> WEB
    AGS --> PAPI
    AGS --> PCLI
    MINI --> AGS
    EVAL -. improve .-> AGS
    EVAL -. improve .-> EXT
```

## 2. Production Truth Path

```mermaid
flowchart LR
    A["crawl"] --> B["raw"]
    B --> C["normalized"]
    C --> D["staging"]
    D --> E["validate"]
    E --> F["ingest"]
    F --> G["warehouse preview"]
    G --> H["warehouse landing"]
    H --> I["resolve"]
    I --> J["multi-source"]
    J --> K["aggregation"]
    K --> L["recommendation / comparison"]
    L --> M["service facade"]
    M --> N["API surfaces"]
    N --> O["web product"]
```

Admission values have a stricter trust path before they appear in recommendation UI:

```mermaid
flowchart LR
    A["raw admission extraction"] --> B["AdmissionSignal"]
    B --> C["validate signal"]
    C --> D["ResolvedAdmissionField"]
    D --> E["admissionResolved metadata"]
    E --> F["decision messaging"]
    E --> G["UI badges"]
    E --> H["assistant reply"]
    E --> I["export snapshot"]

    D -. no scoring impact .-> J["recommendation item metadata only"]
```

This branch is deliberately read-only from the recommendation engine's perspective. It may append deterministic explanation text for conflict, low confidence, or consistent high-confidence requirements, but it must not change candidate filtering, scoring, grouping, or ranking.

## 3. Runtime Surfaces

```mermaid
flowchart TD
    subgraph Runtime["Executable Surfaces"]
        RP["crawlernest/run_pipeline.py"]
        RPLAT["crawlernest/run_platform.py"]
        PAPI["crawlernest/interfaces/api/agent_api/server.py"]
        PCLI["crawlernest/interfaces/cli/agent_cli/main.py"]
        JAVA["crawlernest/servise_for_java/"]
        WEB["crawlernest/crawlernest-web/"]
    end

    RP --> DATA["Data production path"]
    RPLAT --> JOB["clawer_main / modular runtime"]
    PAPI --> AGENT["Python agent API"]
    PCLI --> AGENTCLI["Python agent CLI"]
    JAVA --> PRODUCT["Spring Boot product API"]
    WEB --> UI["Next.js product UI"]
```

## 4. Core Domain View

```mermaid
flowchart LR
    ER["entity_resolution"] --> MS["multi_source"]
    MS --> AGG["ranking_aggregation"]
    AGG --> REC["recommendation_engine"]
    AGG --> CMP["comparison"]
    CONST["constants / utils"] --> ER
    CONST --> MS
    CONST --> AGG
    CONST --> REC
    CONST --> CMP
```

## 5. Admission Trust And Decision Product View

```mermaid
flowchart TD
    RAW["Extractor output<br/>ielts / toefl / gpa / deadline"] --> SIG["AdmissionSignal<br/>field / value / source / confidence / evidence / status"]
    SIG --> VAL["Signal validation<br/>allowed fields / ranges / dates / status"]
    VAL --> RES["ResolvedAdmissionField<br/>deterministic merge per field"]
    RES --> META["admissionResolved<br/>value / confidence / sourceCount / status"]

    META --> ITEM["Recommendation item extension"]
    ITEM --> DEC["decisionOutput messaging"]
    ITEM --> PLAN["applicationPlans / planConfidenceReason"]
    ITEM --> ASSIST["assistant reply"]
    ITEM --> UI["AdmissionSignalBadge + summary banner"]
    ITEM --> EXPORT["Decision Snapshot export"]

    DEC -. messaging only .-> PRODUCT["Decision product"]
    PLAN -. messaging only .-> PRODUCT
    ASSIST -. aligned copy .-> PRODUCT
    UI -. aligned display .-> PRODUCT
    EXPORT -. aligned record .-> PRODUCT
```

Design constraints:

- `admissionResolved` is explainability metadata.
- Conflict and low-confidence states stay visible instead of being hidden.
- `decisionSummaryCompact` is the shared compact source for UI banner, assistant top line, and text export.
- No admission trust signal changes recommendation scoring, filtering, grouping, or ranking.
- The resolver is deterministic and conservative; it does not perform probabilistic inference.

## 6. Agent And Improvement View

```mermaid
flowchart LR
    AG["crawlernest/agent/"] --> PAPI["agent_api"]
    AG --> PCLI["agent_cli"]
    MINI["crawlernest-mini-agent/"] --> AG
    EVAL["crawlernest-autoeval/"] -. evaluate / improve .-> AG
    EVAL -. evaluate / improve .-> EXT["crawlernest-extractors/"]
```

## 7. Data Assets And Persistence

```mermaid
flowchart LR
    SCHEMA["crawlernest-schema/"] --> PG["PostgreSQL"]
    KB["crawlernest-kb/"] --> LOCAL["snapshots / caches / checkpoints / local DB"]
    SAMPLES["crawlernest-samples/"] --> ART["sample / preview / normalized / staging artifacts"]
    SQLITE["clawer.db"] --> LOCAL
    PG --> FACADE["core/services/"]
```

## 8. Canonical Module Map

```mermaid
mindmap
  root((CrawlerNest))
    Pipeline
      run_pipeline.py
      pipeline/
      crawlernest-jobs/
      crawlernest-db-writer/
    Crawlers
      crawlernest-extractors/
      crawlernest-ranking-crawler/
      crawlernest-admission-crawler/
      crawlernest-kb/
    Core
      crawlernest-core/
      entity_resolution
      multi_source
      ranking_aggregation
      recommendation_engine
      admission signals / resolver
      comparison
    Interfaces
      core/services/
      interfaces/api/agent_api/
      interfaces/cli/agent_cli/
      servise_for_java/
      crawlernest-web/
    Agent
      crawlernest/agent/
      crawlernest-mini-agent/
      crawlernest-autoeval/
    Data
      crawlernest-schema/
      crawlernest-samples/
      clawer.db
```

## 9. Regression-Safe Pipeline & Eval Loop

這一節描述的是 admission extraction 與 controlled improvement loop 的理想成熟形態。
它代表我們希望逐步抵達的工程安全基線，但不表示 agent / eval loop 已取代資料主線本身。

- **Admission Extraction Pipeline** is now at Phase 4 "controlled improvement loop":
  - All anomaly signals (e.g., input_truncated, invalid_ielts, source_host_mismatch) are fully observable
  - Integration regression tests verify all anomaly signals using snapshot HTML
  - CLI summary outputs anomaly breakdown at the end of the pipeline
  - Golden dataset + eval runner (`crawlernest-autoeval/runners/run_extractor_eval.py`) can directly verify if a pattern fix in `admission_text_extractor.py` improves or maintains the score
  - Every extractor pattern fix must pass:
    - golden eval (required_fill_rate, exact_match_rate, error_count, score)
    - regression tests (`test_crawlers.py`)
    - pipeline summary (`AdmissionCrawlerEngine.run()`)

- **Eval Example**
  ```
  python3 crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --dataset crawlernest/crawlernest-autoeval/datasets/admission_goldens/samples.json --extractor-file crawlernest/crawlernest-admission-crawler/extractors/admission_text_extractor.py
  ```
  - required_fill_rate: 1.00
  - exact_match_rate: 1.00
  - optional_fill_rate: 0.87
  - error_count: 0
  - score: 0.87

- **Safety Mechanism**
  - Any pattern fix must be regression-safe, must not break anomaly observability or existing tests
  - All pipeline output must be traceable to anomaly breakdown
