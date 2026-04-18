# System And Engine Architecture

以圖為主；repo 目錄對照請看 `docs/REPO_STRUCTURE.md`。

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

## 5. Agent And Improvement View

```mermaid
flowchart LR
    AG["crawlernest/agent/"] --> PAPI["agent_api"]
    AG --> PCLI["agent_cli"]
    MINI["crawlernest-mini-agent/"] --> AG
    EVAL["crawlernest-autoeval/"] -. evaluate / improve .-> AG
    EVAL -. evaluate / improve .-> EXT["crawlernest-extractors/"]
```

## 6. Data Assets And Persistence

```mermaid
flowchart LR
    SCHEMA["crawlernest-schema/"] --> PG["PostgreSQL"]
    KB["crawlernest-kb/"] --> LOCAL["snapshots / caches / checkpoints / local DB"]
    SAMPLES["crawlernest-samples/"] --> ART["sample / preview / normalized / staging artifacts"]
    SQLITE["clawer.db"] --> LOCAL
    PG --> FACADE["core/services/"]
```

## 7. Canonical Module Map

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

## 8. Regression-Safe Pipeline & Eval Loop

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
