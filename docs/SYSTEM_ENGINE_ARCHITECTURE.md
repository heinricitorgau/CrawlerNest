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
    A["Source fetch"] --> B["Crawler / extractor"]
    B --> C["Normalized records"]
    C --> D["Staging / ingest / write"]
    D --> E["Entity resolution"]
    E --> F["Multi-source integration"]
    F --> G["Ranking aggregation"]
    G --> H["Recommendation / comparison"]
    H --> I["Service facade"]
    I --> J["API surfaces"]
    J --> K["Web product"]
```

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
    I --> J["report"]
    J --> K["seed"]
    K --> L["refresh"]
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

## 4. Ingestion And Crawl View

```mermaid
flowchart LR
    SRC["QS / THE / ARWU / university sites"]
    PIPE["run_pipeline.py"]
    PSTAGE["pipeline/"]
    JOBS["crawlernest-jobs/"]
    RC["ranking-crawler"]
    AC["admission-crawler"]
    EXT["extractors"]
    WRITE["db-writer"]
    KB["kb / checkpoint / snapshot"]

    SRC --> PIPE
    SRC --> JOBS
    PIPE --> PSTAGE
    PSTAGE --> RC
    PSTAGE --> AC
    JOBS --> RC
    JOBS --> AC
    RC --> EXT
    AC --> EXT
    EXT --> WRITE
    PIPE --> KB
```

## 5. Core Domain View

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

## 6. Service And Product View

```mermaid
flowchart LR
    CORE["crawlernest-core/"] --> FACADE["core/services/"]
    FACADE --> JAVA["servise_for_java"]
    FACADE --> PAPI["interfaces/api/agent_api"]
    FACADE --> PCLI["interfaces/cli/agent_cli"]
    JAVA --> WEB["crawlernest-web"]
    PAPI --> WEB
```

```mermaid
flowchart TD
    subgraph JavaAPI["servise_for_java"]
        J1["api/"]
        J2["service/"]
        J3["repository/"]
        J4["dto/"]
        J5["domain/"]
        J6["model/"]
        J7["config/"]
        J8["util/"]
    end

    subgraph WebUI["crawlernest-web/src/app"]
        W1["rankings"]
        W2["recommendations"]
        W3["compare"]
        W4["universities"]
        W5["agent"]
        W6["preview"]
        W7["api/*"]
    end
```

## 7. Agent And Improvement View

```mermaid
flowchart LR
    AG["crawlernest/agent/"] --> PAPI["agent_api"]
    AG --> PCLI["agent_cli"]
    MINI["crawlernest-mini-agent/"] --> AG
    EVAL["crawlernest-autoeval/"] -. evaluate / improve .-> AG
    EVAL -. evaluate / improve .-> EXT["crawlernest-extractors/"]
```

```mermaid
flowchart TD
    subgraph AgentStack["crawlernest/agent/"]
        A1["engine"]
        A2["planner"]
        A3["orchestration"]
        A4["tools"]
        A5["web_agent"]
        A6["memory_long_term"]
        A7["policies"]
        A8["validation"]
        A9["self_improvement"]
    end
```

## 8. Data Assets And Persistence

```mermaid
flowchart LR
    SCHEMA["crawlernest-schema/"] --> PG["PostgreSQL"]
    KB["crawlernest-kb/"] --> LOCAL["snapshots / caches / checkpoints / local DB"]
    SAMPLES["crawlernest-samples/"] --> ART["sample / preview / normalized / staging artifacts"]
    SQLITE["clawer.db"] --> LOCAL
    PG --> FACADE["core/services/"]
```

## 9. Canonical Module Map

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
