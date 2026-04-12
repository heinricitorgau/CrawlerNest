# CrawlerNest System Architecture

這份文件描述的是 **CrawlerNest 整體系統怎麼運作**，不是 repo 的檔案樹。  
重點放在資料流、系統分層、執行路徑、以及各子系統之間的責任邊界。

## 1. System Mission

CrawlerNest 不是單一爬蟲，也不是單一網站，而是一個由下列能力組成的教育資料平台：

- 多來源排名資料採集
- canonical identity / normalization / entity resolution
- multi-source ranking aggregation
- explainable recommendation / comparison / trust layer
- Spring Boot API product layer
- Next.js website product layer
- evaluation-driven mini-agent development layer

---

## 2. Full System View

```mermaid
flowchart TD
    SRC["External Data Sources<br/>QS / THE / ARWU / university sites"]

    subgraph INGEST["Ingestion Layer"]
        EXT["Extractors / Crawlers"]
        PIPE["Pipeline Orchestrator"]
    end

    subgraph CANON["Canonical & Processing Layer"]
        NORM["Normalization"]
        ER["Entity Resolution"]
        MS["Multi-Source Integration"]
        AGG["Ranking Aggregation"]
    end

    subgraph DATA["Storage & Knowledge Layer"]
        RAW["Raw / Staging Data"]
        WH["Warehouse Truth"]
        ANA["Analytics Views"]
        KB["Knowledge Artifacts / Caches / Snapshots"]
    end

    subgraph DECISION["Decision Layer"]
        REC["Recommendation Engine"]
        CMP["Comparison Logic"]
        TRUST["Trust / Evidence Layer"]
    end

    subgraph PRODUCT["Product Layer"]
        API["Spring Boot API"]
        WEB["Next.js Web"]
    end

    subgraph DEVX["Evaluation-Driven Dev Layer"]
        TASK["Task"]
        GEN["Generate"]
        EVAL["Evaluate"]
        REFINE["Refine"]
    end

    SRC --> EXT
    EXT --> PIPE
    PIPE --> NORM
    NORM --> ER
    ER --> MS
    MS --> AGG

    PIPE --> RAW
    ER --> WH
    MS --> WH
    AGG --> ANA
    PIPE --> KB

    WH --> REC
    ANA --> REC
    ANA --> CMP
    ANA --> TRUST

    REC --> API
    CMP --> API
    TRUST --> API
    ANA --> API
    API --> WEB

    TASK --> GEN
    GEN --> EVAL
    EVAL --> REFINE
    REFINE --> GEN
```

---

## 3. Layered Architecture

```mermaid
flowchart TB
    L1["1. Source Layer<br/>public ranking sources / university sources"]
    L2["2. Ingestion Layer<br/>crawler / extractor / pipeline orchestration"]
    L3["3. Canonical Layer<br/>normalization / entity resolution / source linking"]
    L4["4. Aggregation Layer<br/>warehouse truth / analytics views / ranking aggregation"]
    L5["5. Decision Layer<br/>recommendation / compare / trust / evidence"]
    L6["6. Product Layer<br/>Spring Boot API / Next.js UI"]
    L7["7. Dev Acceleration Layer<br/>mini-agent + evaluator + refinement loop"]

    L1 --> L2 --> L3 --> L4 --> L5 --> L6
    L7 -. supports improvement, not runtime truth .-> L2
    L7 -. supports improvement, not runtime truth .-> L3
    L7 -. supports improvement, not runtime truth .-> L5
```

### Layer meanings

- `Source Layer`
  外部來源，包含 QS / THE / ARWU 與部分學校站點資料。
- `Ingestion Layer`
  負責抓取、解析、節流、job orchestration、resume 與 ingest 入口。
- `Canonical Layer`
  把來源世界轉成平台自己的 identity truth，解決名稱差異、國家別名、source entity linking。
- `Aggregation Layer`
  把多來源排名轉成可查詢、可解釋、可比較的 warehouse/analytics truth。
- `Decision Layer`
  在 aggregated truth 上做 recommendation、compare、trust、evidence summary。
- `Product Layer`
  對外提供 API 與網站介面。
- `Dev Acceleration Layer`
  Mini-agent + evaluator，用於改進系統，不直接定義 production ranking truth。

---

## 4. Core Runtime Path

這是 CrawlerNest 最重要的主路徑：

```mermaid
flowchart LR
    A["Source Fetch"] --> B["Extraction"]
    B --> C["Normalization"]
    C --> D["Entity Resolution"]
    D --> E["Multi-Source Records"]
    E --> F["Ranking Aggregation"]
    F --> G["Analytics / Read Models"]
    G --> H["API Responses"]
    H --> I["Web Product"]
```

### Runtime intent

- `Source Fetch`
  從外部資料源抓到 ranking/university facts。
- `Extraction`
  解析成較穩定的 payload。
- `Normalization`
  標準化名稱、國家、數值、ranking metadata。
- `Entity Resolution`
  對齊到 `canonical_university`。
- `Multi-Source Records`
  保留 QS/THE/ARWU 各自的 source truth，不互相覆蓋。
- `Ranking Aggregation`
  產生 aggregated rank、coverage、evidence、trust-related signals。
- `Analytics / Read Models`
  提供 product 端穩定查詢視圖。
- `API Responses`
  封裝產品查詢、推薦、比較。
- `Web Product`
  呈現 rankings browser、university detail、recommendation、compare。

---

## 5. Data Pipeline Architecture

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

    S->>E: HTML / JSON / source payload
    E->>P: extracted records
    P->>N: normalize names, country, score, rank
    N->>R: resolve canonical identity
    R->>M: standardized ranking records
    M->>D: source-specific ranking rows
    M->>A: unified source-aligned records
    A->>D: aggregated rankings + analytics views
```

### Key design rule

- source rows保留原貌
- aggregation 才產生平台層 truth
- recommendation / compare 只消費 canonical + analytics truth

也就是說：

**來源真相、平台真相、產品輸出** 是三個不同層次，不混在一起。

---

## 6. Storage Model

```mermaid
flowchart TD
    P["Pipeline"] --> STG["Staging / raw facts"]
    P --> KB["Knowledge artifacts / snapshots / caches"]
    ER["Entity Resolution"] --> CANON["Canonical identity tables"]
    MS["Multi-Source integration"] --> RR["warehouse.ranking_record"]
    AGG["Aggregation"] --> AV["analytics.v_aggregated_rankings_latest"]
    REC["Recommendation engine"] --> RV["analytics recommendation results / candidates"]
    API["Spring Boot API"] --> AV
    API --> CANON
    API --> RV
```

### Why this matters

- 不是所有爬到的資料都會直接出現在前端
- 資料必須經過 canonical linking 與 ranking record/backfill
- 最後還要進入 analytics/read model，產品層才看得到

---

## 7. Decision System Architecture

```mermaid
flowchart LR
    AR["Aggregated Rankings"] --> REC["Recommendation Engine"]
    ADM["Admission / IELTS / constraints"] --> REC
    PREF["User Preference / risk profile / country policy"] --> REC
    REC --> CAT["Reach / Target / Safety grouping"]
    REC --> EXPLAIN["Explanation / confidence / warning"]
    CAT --> API["API Response"]
    EXPLAIN --> API
```

### Decision principles

- 不是黑箱 ML
- 目前以 deterministic rule-based engine 為主
- 先 explainable，再 intelligent
- ranking evidence 與 confidence 是第一級輸出，不只是附加資訊

---

## 8. Product Request Path

```mermaid
sequenceDiagram
    participant U as User
    participant W as Next.js Web
    participant A as Spring Boot API
    participant X as Analytics Views
    participant C as Canonical Metadata

    U->>W: filter / shortlist / compare / recommend
    W->>A: HTTP request
    A->>X: query rankings / recommendation candidates
    A->>C: join university metadata / country / slug
    X-->>A: ranking truth / evidence
    C-->>A: canonical metadata
    A-->>W: product response
    W-->>U: rankings table / detail / compare / recommendation UI
```

---

## 9. Trust and Explainability Model

CrawlerNest 的產品策略不是只輸出「排名結果」，而是一起輸出：

- source evidence
- source disagreement
- coverage ratio
- recommendation confidence
- explanation text
- warnings / gaps / missing data

```mermaid
flowchart TD
    SR["QS / THE / ARWU source ranks"] --> EVI["Evidence Layer"]
    EVI --> AG["Aggregated Rank"]
    EVI --> TR["Trust Signal"]
    AG --> REC["Recommendation / Compare"]
    TR --> REC
    EVI --> API["API payload"]
    TR --> API
    REC --> API
```

這代表系統不是在隱藏不確定性，而是在把不確定性產品化。

---

## 10. Mini-Agent / Evaluation Layer

這層是 **開發輔助系統**，不是 production ranking runtime 本體。

```mermaid
flowchart LR
    T["Human-defined task"] --> G["Generator"]
    G --> E["Evaluator"]
    E --> R["Refiner"]
    R --> G
    E --> H["Human review / adoption decision"]
```

### Role in the whole platform

- 幫助 extractor / parser / workflow refinement
- 透過 evaluator 降低亂改主系統的風險
- 加速開發，但不直接決定資料真相

換句話說：

**Mini-Agent 是 improvement loop，不是 truth source。**

---

## 11. System Boundary Summary

```mermaid
flowchart TD
    subgraph PROD["Production Truth Path"]
        A["Sources"] --> B["Ingestion"]
        B --> C["Canonical"]
        C --> D["Aggregation"]
        D --> E["Decision"]
        E --> F["API/Web"]
    end

    subgraph SIDE["Controlled Improvement Path"]
        G["Task"] --> H["Generate"]
        H --> I["Evaluate"]
        I --> J["Refine"]
    end

    SIDE -. improves implementation quality .-> PROD
```

---

## 12. Implementation Mapping

只保留最小必要的實作對應，方便把系統圖對回程式：

- `crawlernest/run_pipeline.py`
  Ingestion pipeline 主入口
- `crawlernest/crawlernest-extractors/`
  source acquisition / extraction
- `crawlernest/crawlernest-core/entity_resolution/`
  canonical identity linking
- `crawlernest/crawlernest-core/multi_source/`
  QS/THE/ARWU source integration
- `crawlernest/crawlernest-core/ranking_aggregation/`
  aggregated ranking truth
- `crawlernest/crawlernest-core/recommendation_engine/`
  explainable deterministic recommendation
- `crawlernest/servise_for_java/`
  product API layer
- `crawlernest/crawlernest-web/`
  website product layer
- `agent/evaluator.py`
  mini-agent evaluation logic

---

## 13. One-Sentence Summary

CrawlerNest 的本質是：

**把多來源教育排名資料，經過 canonical 化、aggregation、explainable decision、API productization，最後交付成可查詢、可比較、可推薦的教育資料系統；而 mini-agent layer 只負責加速這個系統的演進，不直接取代它。**
