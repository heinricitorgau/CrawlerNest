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
--
-- The one mapping table for every source that names universities. It began
-- ranking-only, keyed by ranking_source_id, while admission pages wrote a
-- parallel warehouse.source_mapping keyed by source_name -- two tables, two
-- vocabularies, and a view (warehouse.v_entity_mapping) papering over the
-- split. source_code is now the key for every source:
--
--   * a ranking row carries both source_code and ranking_source_id, and the
--     composite foreign key below makes the two agree;
--   * any other source (university_site) carries source_code alone, with
--     ranking_source_id NULL, so every ranking reader -- all of which join on
--     ranking_source_id -- keeps seeing exactly the rows it saw before.
--
-- source_code also references warehouse.entity_source; that foreign key is
-- added in mapping_review_postgresql.sql, which creates the registry.
CREATE TABLE IF NOT EXISTS warehouse.source_university_mapping (
    source_mapping_id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL,
    ranking_source_id SMALLINT
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

-- Migration: ranking_source_id -> source_code. No-ops once applied.
ALTER TABLE warehouse.source_university_mapping
    ADD COLUMN IF NOT EXISTS source_code TEXT;

UPDATE warehouse.source_university_mapping m
SET source_code = rs.source_code
FROM warehouse.ranking_source rs
WHERE rs.ranking_source_id = m.ranking_source_id
  AND m.source_code IS NULL;

ALTER TABLE warehouse.source_university_mapping
    ALTER COLUMN source_code SET NOT NULL;

ALTER TABLE warehouse.source_university_mapping
    ALTER COLUMN ranking_source_id DROP NOT NULL;

-- A unique index rather than a constraint: the foreign key below depends on it,
-- and the usual DROP-then-ADD would fail on every bootstrap after the first.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ranking_source_id_code
    ON warehouse.ranking_source (ranking_source_id, source_code);

-- A ranking row's two keys name the same source. MATCH SIMPLE skips the check
-- when ranking_source_id is NULL, which is exactly the non-ranking case.
ALTER TABLE warehouse.source_university_mapping
    DROP CONSTRAINT IF EXISTS fk_source_university_mapping_ranking_code;
ALTER TABLE warehouse.source_university_mapping
    ADD CONSTRAINT fk_source_university_mapping_ranking_code
    FOREIGN KEY (ranking_source_id, source_code)
    REFERENCES warehouse.ranking_source (ranking_source_id, source_code);

-- The key every writer upserts on. (ranking_source_id, source_entity_id)
-- stays for the ranking writers that still name it; for ranking rows the two
-- keys are equivalent, and a NULL ranking_source_id never collides.
CREATE UNIQUE INDEX IF NOT EXISTS uq_source_university_mapping_source_entity
    ON warehouse.source_university_mapping (source_code, source_entity_id);

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
    universe_type TEXT NOT NULL DEFAULT 'global', -- global/region/subject/special
    universe_key TEXT NOT NULL DEFAULT 'global',  -- global/europe/computer-science/mba
    rank_position INTEGER,
    score NUMERIC(8,4),
    score_scale NUMERIC(8,4),                   -- optional: source-native score max
    source_version TEXT,
    source_url TEXT,
    metadata JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id TEXT,
    CHECK (rank_position IS NULL OR rank_position > 0),
    CHECK (score IS NULL OR score >= 0)
);

ALTER TABLE warehouse.ranking_record
    ADD COLUMN IF NOT EXISTS universe_type TEXT NOT NULL DEFAULT 'global';

ALTER TABLE warehouse.ranking_record
    ADD COLUMN IF NOT EXISTS universe_key TEXT NOT NULL DEFAULT 'global';

ALTER TABLE warehouse.ranking_record
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE warehouse.ranking_record
    ADD COLUMN IF NOT EXISTS run_id TEXT;

ALTER TABLE warehouse.ranking_record
    DROP CONSTRAINT IF EXISTS ranking_record_canonical_university_id_ranking_source_id_ra_key;

ALTER TABLE warehouse.ranking_record
    DROP CONSTRAINT IF EXISTS uq_ranking_record_universe;

ALTER TABLE warehouse.ranking_record
    ADD CONSTRAINT uq_ranking_record_universe
    UNIQUE (canonical_university_id, ranking_source_id, ranking_year, ranking_type, universe_type, universe_key);

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

CREATE INDEX IF NOT EXISTS idx_ranking_record_universe
    ON warehouse.ranking_record(ranking_source_id, ranking_year, universe_type, universe_key, rank_position);

CREATE INDEX IF NOT EXISTS idx_ranking_record_canonical
    ON warehouse.ranking_record(canonical_university_id, ranking_year);

CREATE INDEX IF NOT EXISTS idx_ranking_record_year
    ON warehouse.ranking_record(ranking_year);

CREATE INDEX IF NOT EXISTS idx_missing_entity_source_created
    ON analytics.missing_entity_log(source_code, created_at);

CREATE INDEX IF NOT EXISTS idx_source_ingestion_source_started
    ON analytics.source_ingestion_log(source_code, started_at);
