# System And Engine Architecture Execution

`docs/SYSTEM_ENGINE_ARCHITECTURE.md` 是 v1 全景藍圖；這份文件是 v2，目前可執行的 MVP / controlled system。

## 1. Current Executable Architecture

```mermaid
flowchart TD
    subgraph LAYER_A["Layer A: Active Data Pipeline (RUNNING)"]
        direction LR

        subgraph INGEST["Ingestion"]
            PIPE["[ACTIVE] run_pipeline.py / pipeline/"]
            JOBS["[ACTIVE] crawlernest-jobs/"]
            RCRAWL["[ACTIVE] crawlernest-ranking-crawler/"]
            ACRAWL["[LIMITED] crawlernest-admission-crawler/"]
            EXT["[ACTIVE] crawlernest-extractors/"]
        end

        subgraph CORE["Core Domain"]
            NORM["[ACTIVE] normalization (basic)"]
            WRITE["[ACTIVE] crawlernest-db-writer/"]
            ER["[ACTIVE] entity_resolution (minimal viable)"]
            WH["[ACTIVE] warehouse (ranking + admission)"]
        end

        subgraph INTERFACE["Interface"]
            JAVA["[ACTIVE] servise_for_java / REST API"]
            WEB["[ACTIVE] crawlernest-web"]
        end
    end

    subgraph LAYER_B["Layer B: Controlled Expansion (PARTIAL)"]
        direction LR
        ADM_ENRICH["[LIMITED] admission enrichment / pilot scope"]
        BASIC_REC["[LIMITED] recommendation_engine (basic / rule-based / optional)"]
    end

    subgraph LAYER_C["Layer C: Future / Disabled (NOT ACTIVE)"]
        direction LR
        AGG["[FUTURE] multi_source + ranking_aggregation"]
        AGENT["[DISABLED] crawlernest/agent/"]
        MINI["[DISABLED] crawlernest-mini-agent/"]
        AUTOEVAL["[DISABLED] crawlernest-autoeval/"]
    end

    PIPE --> JOBS
    JOBS --> RCRAWL
    JOBS --> ACRAWL
    RCRAWL --> EXT
    ACRAWL --> EXT
    EXT --> NORM
    NORM --> WRITE
    WRITE --> ER
    ER --> WH
    WH --> JAVA
    JAVA --> WEB

    ACRAWL -. pilot feed .-> ADM_ENRICH
    WH -. optional read .-> BASIC_REC
    BASIC_REC -. optional API path .-> JAVA
    ADM_ENRICH -. controlled write .-> WH

    ER -. future expansion .-> AGG
    WH -. future expansion .-> AGG

    AUTOEVAL -. dev support only .-> AGENT
    MINI -. dev support only .-> AGENT
```

## 2. Execution vs Vision

v1 (`docs/SYSTEM_ENGINE_ARCHITECTURE.md`) 描述的是長期完整藍圖，包含更完整的 multi-source aggregation、recommendation、agent loop 與自動改進能力。  
v2 只保留目前應該真的上線、維護、驗證的執行主鏈：`crawl -> extract -> normalize -> write -> warehouse -> API -> web`。

這份 v2 刻意降級或移出：

- `recommendation_engine`：只作為 `[LIMITED]` 的 basic / rule-based / optional 能力
- `multi_source`、`ranking_aggregation`：標為 `[FUTURE]`
- `crawlernest/agent/`、`crawlernest-mini-agent/`、`crawlernest-autoeval/`：標為 `[DISABLED]`，只屬於 development support，不屬於 production pipeline

## 3. Design Principle

- Agent is not part of production data path.
- Admission crawler is in controlled pilot stage.
- Data correctness > automation.
