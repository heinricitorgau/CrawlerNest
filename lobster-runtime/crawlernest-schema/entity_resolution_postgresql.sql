-- =========================================================
-- CrawlerNest Entity Resolution Schema (PostgreSQL)
-- =========================================================
-- Purpose:
-- 1) Canonical university dimension
-- 2) One-to-many multilingual aliases
-- 3) Source-to-canonical mappings with confidence metadata
-- 4) Resolution event log for unresolved / review workflows

CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------
-- 1) Canonical university entity
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.canonical_university (
    canonical_university_id BIGSERIAL PRIMARY KEY,
    canonical_slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    display_name_normalized TEXT NOT NULL,
    native_name TEXT,
    country_id INTEGER REFERENCES warehouse.countries(country_id),
    city_name TEXT,
    website_url TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- 2) University aliases (multilingual, one-to-many)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.university_alias (
    alias_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    alias_text TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    language_code VARCHAR(12),  -- e.g. en, zh-TW
    script_code VARCHAR(8),     -- e.g. Latn, Hans, Hant
    source_name TEXT,           -- e.g. QS / THE / ARWU / website
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_abbreviation BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- 3) Source mapping (source entity -> canonical entity)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.source_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,          -- QS/THE/ARWU/university_site
    source_entity_id TEXT NOT NULL,     -- source unique identifier/path/nid/url hash
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    matched_alias_id BIGINT
        REFERENCES warehouse.university_alias(alias_id),
    match_method TEXT NOT NULL,         -- exact / normalized / fuzzy / embedding / manual
    confidence_score NUMERIC(5,4) NOT NULL,
    threshold_used NUMERIC(5,4),
    review_status TEXT NOT NULL DEFAULT 'auto_accepted', -- auto_accepted/manual_review/rejected
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE (source_name, source_entity_id)
);

-- ---------------------------------------------------------
-- 4) Resolution events / unresolved logging
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.entity_resolution_event (
    event_id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_entity_id TEXT,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    country_hint TEXT,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    match_method TEXT,
    confidence_score NUMERIC(5,4),
    outcome TEXT NOT NULL,              -- matched / unresolved / review
    canonical_university_id BIGINT,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_canonical_university_norm_name
    ON warehouse.canonical_university(display_name_normalized);

CREATE INDEX IF NOT EXISTS idx_university_alias_norm
    ON warehouse.university_alias(alias_normalized);

CREATE INDEX IF NOT EXISTS idx_university_alias_norm_trgm
    ON warehouse.university_alias USING GIN (alias_normalized gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_university_alias_source
    ON warehouse.university_alias(source_name, alias_normalized);

CREATE UNIQUE INDEX IF NOT EXISTS uq_university_alias_dedup
    ON warehouse.university_alias(
        canonical_university_id,
        alias_normalized,
        COALESCE(language_code, ''),
        COALESCE(source_name, '')
    );

CREATE INDEX IF NOT EXISTS idx_source_mapping_source_entity
    ON warehouse.source_mapping(source_name, source_entity_id);

CREATE INDEX IF NOT EXISTS idx_source_mapping_canonical
    ON warehouse.source_mapping(canonical_university_id);

CREATE INDEX IF NOT EXISTS idx_er_event_outcome_created
    ON analytics.entity_resolution_event(outcome, created_at);
