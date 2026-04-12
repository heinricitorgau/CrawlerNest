# CrawlerNest System And Engine Architecture

這份文件描述的是 **CrawlerNest 系統架構與核心引擎架構**。  
如果你要看 repo / 目錄怎麼分布，請改看：

- `docs/REPO_STRUCTURE.md`

## 1. Full System View

```mermaid
flowchart TD
    SRC["External Sources<br/>QS / THE / ARWU / university sites"]

    subgraph INGEST["Ingestion Layer"]
        EXT["Crawler / Extractor"]
        PIPE["Pipeline Orchestrator"]
    end

    subgraph CANON["Canonical Layer"]
        NORM["Normalization"]
        ER["Entity Resolution"]
        MS["Multi-Source Integration"]
    end

    subgraph DATA["Data Layer"]
        RAW["Raw / staging"]
        WH["Warehouse truth"]
        ANA["Analytics views"]
        KB["Knowledge artifacts / caches / snapshots"]
    end

    subgraph ENGINE["Decision Engine Layer"]
        AGG["Ranking Aggregation Engine"]
        REC["Recommendation Engine"]
        CMP["Comparison Logic"]
        TRUST["Trust / Evidence Layer"]
    end

    subgraph PRODUCT["Product Layer"]
        API["Spring Boot API"]
        WEB["Next.js Web"]
    end

    subgraph DEVX["Mini-Agent Dev Layer"]
        TASK["Task"]
        GEN["Generate"]
        EVAL["Evaluate"]
        REFINE["Refine"]
    end

    SRC --> EXT --> PIPE
    PIPE --> NORM --> ER --> MS
    PIPE --> RAW
    PIPE --> KB
    MS --> WH
    WH --> AGG
    AGG --> ANA
    ANA --> REC
    ANA --> CMP
    ANA --> TRUST
    REC --> API
    CMP --> API
    TRUST --> API
    ANA --> API
    API --> WEB

    TASK --> GEN --> EVAL --> REFINE --> GEN
```

## 2. Main Production Truth Path

```mermaid
flowchart LR
    A["Source fetch"] --> B["Extraction"]
    B --> C["Normalization"]
    C --> D["Entity Resolution"]
    D --> E["Multi-Source Records"]
    E --> F["Aggregation"]
    F --> G["Analytics / Read Models"]
    G --> H["API"]
    H --> I["Web Product"]
```

這條路徑代表真正會影響產品資料真相的主鏈：

- 外部來源資料進來
- 轉成平台可理解格式
- 對齊 canonical identity
- 保留 source truth
- 再做 aggregated truth
- 最後提供給 API 與產品層

## 3. Data Engine Architecture

```mermaid
sequenceDiagram
    participant S as Source
    participant E as Extractor
    participant P as Pipeline
    participant N as Normalize
    participant R as Entity Resolution
    participant M as Multi-Source
    participant A as Aggregation
    participant D as PostgreSQL

    S->>E: raw source payload
    E->>P: extracted facts
    P->>N: normalize fields
    N->>R: resolve canonical identity
    R->>M: standardized ranking records
    M->>D: source-specific rows
    M->>A: integrated ranking records
    A->>D: aggregated rankings / analytics views
```

### Core data rules

- source rows 不互相覆蓋
- canonical linking 先於平台 truth
- aggregation 只建立平台層 truth，不抹掉來源差異
- product 層消費的是 analytics/read model，不是原始 crawler payload

## 4. Aggregation Engine

```mermaid
flowchart LR
    QS["QS rank"] --> AGG["Aggregation Engine"]
    THE["THE rank"] --> AGG
    ARWU["ARWU rank"] --> AGG
    CFG["Source weights / aggregation config"] --> AGG
    AGG --> OUT1["Aggregated rank"]
    AGG --> OUT2["Composite score(display only)"]
    AGG --> OUT3["Coverage ratio"]
    AGG --> OUT4["Evidence / source detail"]
```

### Aggregation intent

- 聚合是 deterministic analytics，不是 ML
- ranking order 以來源 rank 為核心
- composite score 只是輔助顯示，不是排序真相
- coverage 與 source evidence 會一起保留給後續 decision layer

## 5. Recommendation Engine

```mermaid
flowchart TD
    AR["Aggregated rankings"] --> REC["Recommendation Engine"]
    ADM["IELTS / admission constraints"] --> REC
    PREF["Country / target rank / risk profile"] --> REC

    REC --> FIL["Eligibility filtering"]
    FIL --> SCORE["Base scoring"]
    SCORE --> ADJ["Preference / risk adjustment"]
    ADJ --> CAT["Reach / Target / Safety"]
    CAT --> EXP["Explanation / confidence / warnings"]
    EXP --> API["Recommendation API payload"]
```

### Recommendation intent

- 目前是 explainable deterministic rule engine
- 先過 eligibility，再算 score，再做風險與偏好修正
- 最後輸出 category、confidence、explanation，不只給一個分數

## 6. Trust / Evidence Engine

```mermaid
flowchart LR
    SR["Source ranks"] --> EVI["Evidence Builder"]
    SC["Source coverage"] --> EVI
    DIS["Source disagreement"] --> EVI
    EVI --> TR["Trust signal"]
    EVI --> RS["Ranking evidence summary"]
    TR --> API["API payload"]
    RS --> API
```

### Trust intent

- 不把來源差異藏起來
- 讓產品層直接看到 evidence / disagreement / coverage
- 把不確定性顯式交給使用者，而不是假裝資料永遠完整一致

## 7. Product Architecture

```mermaid
sequenceDiagram
    participant U as User
    participant W as Next.js Web
    participant A as Spring Boot API
    participant X as Analytics Views
    participant C as Canonical Metadata

    U->>W: rankings / compare / recommend request
    W->>A: HTTP request
    A->>X: query ranking / recommendation views
    A->>C: join university metadata
    X-->>A: analytics truth
    C-->>A: canonical metadata
    A-->>W: structured response
    W-->>U: UI rendering
```

## 8. Mini-Agent Development Loop

這層不是 production truth engine，而是 **開發改進引擎**。

```mermaid
flowchart LR
    T["Human-defined task"] --> G["Generate"]
    G --> E["Evaluate"]
    E --> R["Refine"]
    R --> G
    E --> H["Human adoption decision"]
```

### Role

- 幫助 extractor / parser / workflow refinement
- 用 evaluator 限制 hallucination 與脆弱修改
- 加速開發，但不直接產生 ranking truth

## 9. Boundary Summary

```mermaid
flowchart TD
    subgraph PROD["Production Runtime"]
        A["Ingestion"] --> B["Canonical"]
        B --> C["Aggregation"]
        C --> D["Decision"]
        D --> E["API / Web"]
    end

    subgraph IMPROVE["Improvement Loop"]
        F["Task"] --> G["Generate"]
        G --> H["Evaluate"]
        H --> I["Refine"]
    end

    IMPROVE -. improves implementation quality .-> PROD
```

## 10. Minimal Implementation Mapping

- `crawlernest/run_pipeline.py`
  pipeline orchestrator
- `crawlernest/crawlernest-extractors/`
  extraction layer
- `crawlernest/crawlernest-core/entity_resolution/`
  canonical engine
- `crawlernest/crawlernest-core/multi_source/`
  source integration engine
- `crawlernest/crawlernest-core/ranking_aggregation/`
  aggregation engine
- `crawlernest/crawlernest-core/recommendation_engine/`
  recommendation engine
- `crawlernest/servise_for_java/`
  product API
- `crawlernest/crawlernest-web/`
  product UI
- `agent/evaluator.py`
  evaluator logic
