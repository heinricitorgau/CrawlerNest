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

    subgraph LAYER_C["Layer C: Development Support / Future Expansion"]
        direction LR
        AGG["[FUTURE] multi_source + ranking_aggregation"]
        AGENT["[DEV-SUPPORT] crawlernest/agent/"]
        MINI["[DEV-SUPPORT] crawlernest-mini-agent/"]
        AUTOEVAL["[DEV-SUPPORT] crawlernest-autoeval/"]
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

這份文件的重點不是否認 agent / autoeval 的存在，而是明確指出：

- 它們存在
- 它們可以運作
- 但它們不是現在的 mainline production truth path

這份 v2 刻意降級或移出：

- `recommendation_engine`：只作為 `[LIMITED]` 的 basic / rule-based / optional 能力
- `multi_source`、`ranking_aggregation`：標為 `[FUTURE]`
- `crawlernest/agent/`、`crawlernest-mini-agent/`、`crawlernest-autoeval/`：標為 `[DEV-SUPPORT]`，代表它們屬於開發支援與受控 improvement path，不屬於 production pipeline，也不應先於 admission / canonical / warehouse 主線被擴張

## 3. Design Principle

- Agent is not part of production data path.
- Admission crawler is in controlled pilot stage.
- Data correctness > automation.
- Correctness-first sequencing overrides capability breadth.
- Development support layers may evolve, but must not outrun crawl / normalization / canonical / warehouse stability.

## 4. Regression-Safe Pipeline & Eval Loop (Phase 4)

- The Admission Extraction Pipeline has entered the regression-safe + eval verification stage:
        - All anomaly signals (input_truncated, invalid_ielts, source_host_mismatch, etc.) are fully observable
        - Integration regression tests verify all anomaly signals using snapshot HTML
        - CLI summary outputs anomaly breakdown at the end of the pipeline
        - Golden dataset + eval runner (`crawlernest-autoeval/runners/run_extractor_eval.py`) can verify if a pattern fix in `admission_text_extractor.py` improves or maintains the score
        - Every extractor pattern fix must pass:
                - golden eval (required_fill_rate, exact_match_rate, error_count, score)
                - regression tests (`test_crawlers.py`)
                - pipeline summary (`AdmissionCrawlerEngine.run()`)

- Eval Example:
        ```
        python3 crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --dataset crawlernest/crawlernest-autoeval/datasets/admission_goldens/samples.json --extractor-file crawlernest/crawlernest-admission-crawler/extractors/admission_text_extractor.py
        ```
        - required_fill_rate: 1.00
        - exact_match_rate: 1.00
        - optional_fill_rate: 0.87
        - error_count: 0
        - score: 0.87

- Safety mechanism: Any pattern fix must be regression-safe, must not break anomaly observability or existing tests, and all pipeline output must be traceable to anomaly breakdown.
