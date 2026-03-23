-- =========================================================
-- CrawlerNest Multi-Source Ranking Integration Schema
-- =========================================================
-- Requires entity_resolution_postgresql.sql (canonical_university)

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------
-- Source registry
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.ranking_source (
    ranking_source_id SMALLSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,     -- QS / THE / ARWU
    source_name TEXT NOT NULL,
    source_version TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Source university mapping (source entity -> canonical university)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.source_university_mapping (
    source_mapping_id BIGSERIAL PRIMARY KEY,
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_entity_id TEXT NOT NULL,       -- source unique id/path/url hash
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    match_method TEXT NOT NULL,           -- exact/normalized/fuzzy/embedding/manual
    confidence_score NUMERIC(5,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE (ranking_source_id, source_entity_id)
);

-- ---------------------------------------------------------
-- Ranking facts (one row per source + year + type + university)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.ranking_record (
    ranking_record_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_mapping_id BIGINT
        REFERENCES warehouse.source_university_mapping(source_mapping_id),
    ranking_year INTEGER NOT NULL,
    ranking_type TEXT NOT NULL DEFAULT 'world', -- world/regional/subject...
    rank_position INTEGER,
    score NUMERIC(8,4),
    score_scale NUMERIC(8,4),                   -- optional: source-native score max
    source_version TEXT,
    source_url TEXT,
    metadata JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (rank_position IS NULL OR rank_position > 0),
    CHECK (score IS NULL OR score >= 0),
    UNIQUE (canonical_university_id, ranking_source_id, ranking_year, ranking_type)
);

-- ---------------------------------------------------------
-- Optional future aggregation materialization table
-- (structure only, no ML logic implemented)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.ranking_aggregate_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    snapshot_date DATE NOT NULL,
    weighted_rank_score NUMERIC(10,4),   -- reserved for weighted ranking
    normalized_score NUMERIC(10,4),      -- reserved for score normalization
    composite_rank INTEGER,              -- reserved for composite rank
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canonical_university_id, snapshot_date)
);

-- ---------------------------------------------------------
-- Observability / diagnostics
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.source_ingestion_log (
    ingestion_log_id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL,
    batch_id TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    records_in INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    unresolved_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    details_json JSONB
);

CREATE TABLE IF NOT EXISTS analytics.missing_entity_log (
    missing_entity_log_id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL,
    source_entity_id TEXT,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    country_hint TEXT,
    ranking_year INTEGER,
    ranking_type TEXT,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analytics.merge_diagnostics (
    diagnostics_id BIGSERIAL PRIMARY KEY,
    batch_id TEXT,
    source_code TEXT,
    total_records INTEGER NOT NULL DEFAULT 0,
    unique_resolution_keys INTEGER NOT NULL DEFAULT 0,
    duplicate_resolution_saves INTEGER NOT NULL DEFAULT 0,
    avg_candidates NUMERIC(10,4),
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_source_uni_mapping_canonical
    ON warehouse.source_university_mapping(canonical_university_id);

CREATE INDEX IF NOT EXISTS idx_ranking_record_source_year
    ON warehouse.ranking_record(ranking_source_id, ranking_year, ranking_type, rank_position);

CREATE INDEX IF NOT EXISTS idx_ranking_record_canonical
    ON warehouse.ranking_record(canonical_university_id, ranking_year);

CREATE INDEX IF NOT EXISTS idx_ranking_record_year
    ON warehouse.ranking_record(ranking_year);

CREATE INDEX IF NOT EXISTS idx_missing_entity_source_created
    ON analytics.missing_entity_log(source_code, created_at);

CREATE INDEX IF NOT EXISTS idx_source_ingestion_source_started
    ON analytics.source_ingestion_log(source_code, started_at);
