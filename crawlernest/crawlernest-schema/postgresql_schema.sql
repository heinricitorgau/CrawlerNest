-- =========================================================
-- CrawlerNest PostgreSQL Schema (AI-Feature-Ready)
-- =========================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pgvector is optional. For broad local compatibility, embeddings are stored as JSONB.

-- Create Schemas
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- =========================================================
-- WAREHOUSE LAYER (Canonical Dimensions & Facts)
-- =========================================================

-- Lineage / Control
CREATE TABLE warehouse.crawl_runs (
    crawl_run_id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    ranking_type TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'running',
    notes TEXT
);

-- Dimensions
CREATE TABLE warehouse.countries (
    country_id SERIAL PRIMARY KEY,
    country_code TEXT UNIQUE,
    country_name TEXT NOT NULL UNIQUE,
    region_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouse.universities (
    university_id SERIAL PRIMARY KEY,
    school_slug TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    canonical_name TEXT,
    country_id INTEGER REFERENCES warehouse.countries(country_id),
    city_name TEXT,
    website_url TEXT,
    qs_profile_path TEXT,
    embedding JSONB,        -- Optional embedding payload; upgrade to pgvector later if installed
    metadata JSONB,         -- Flexible metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouse.university_aliases (
    alias_id SERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL REFERENCES warehouse.universities(university_id),
    source_name TEXT NOT NULL,
    source_school_name TEXT NOT NULL,
    match_type TEXT DEFAULT 'manual',
    confidence_score REAL DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_name, source_school_name)
);

CREATE TABLE warehouse.programs (
    program_id SERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL REFERENCES warehouse.universities(university_id),
    program_name TEXT NOT NULL,
    canonical_program_name TEXT,
    program_category TEXT,
    department_name TEXT,
    study_field TEXT,
    source_url TEXT,
    embedding JSONB,        -- Optional embedding payload; upgrade to pgvector later if installed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(university_id, program_name)
);

CREATE TABLE warehouse.degrees (
    degree_id SERIAL PRIMARY KEY,
    program_id INTEGER NOT NULL REFERENCES warehouse.programs(program_id),
    degree_name TEXT NOT NULL,
    degree_level TEXT,
    duration_text TEXT,
    delivery_mode TEXT,
    source_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(program_id, degree_name, degree_level)
);

-- Facts
CREATE TABLE warehouse.rankings (
    ranking_id SERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL REFERENCES warehouse.universities(university_id),
    raw_id INTEGER, -- Will reference staging.raw_source_records
    ranking_source TEXT NOT NULL,
    ranking_type TEXT NOT NULL,
    ranking_year INTEGER,
    rank_start INTEGER,
    rank_end INTEGER,
    score REAL,
    metrics_json JSONB, -- Stored as JSONB for indexing
    source_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (rank_start > 0),
    CHECK (rank_end > 0),
    CHECK (score >= 0)
);

CREATE TABLE warehouse.admission_requirements (
    requirement_id SERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL REFERENCES warehouse.universities(university_id),
    program_id INTEGER REFERENCES warehouse.programs(program_id),
    degree_id INTEGER REFERENCES warehouse.degrees(degree_id),
    raw_id INTEGER,
    source_url TEXT,
    gpa_min REAL,
    ielts_min REAL,
    toefl_min REAL,
    gre_min REAL,
    gmat_min REAL,
    application_deadline_text TEXT,
    raw_text TEXT,
    parsed_status TEXT,
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (gpa_min >= 0),
    CHECK (ielts_min >= 0),
    CHECK (toefl_min >= 0),
    CHECK (gre_min >= 0),
    CHECK (gmat_min >= 0)
);

-- =========================================================
-- STAGING LAYER (Raw Ingestion)
-- =========================================================

CREATE TABLE staging.raw_source_records (
    raw_id SERIAL PRIMARY KEY,
    crawl_run_id INTEGER REFERENCES warehouse.crawl_runs(crawl_run_id),
    source_name TEXT NOT NULL,
    record_type TEXT,
    ranking_type TEXT,
    source_url TEXT,
    raw_json JSONB, -- Native JSONB
    raw_text TEXT,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- QUALITY / AUDIT LAYER
-- =========================================================

CREATE TABLE analytics.field_status_logs (
    status_id SERIAL PRIMARY KEY,
    university_id INTEGER REFERENCES warehouse.universities(university_id),
    raw_id INTEGER,
    field_name TEXT,
    field_raw_value TEXT,
    field_normalized_value TEXT,
    field_status TEXT,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =========================================================
-- INDEXES
-- =========================================================

-- GIN Indexes for JSONB
CREATE INDEX idx_rankings_metrics_json ON warehouse.rankings USING GIN (metrics_json);
CREATE INDEX idx_raw_source_records_json ON staging.raw_source_records USING GIN (raw_json);

-- Standard Indexes
CREATE INDEX idx_universities_slug ON warehouse.universities(school_slug);
CREATE INDEX idx_rankings_uni_year ON warehouse.rankings(university_id, ranking_year);
CREATE INDEX idx_programs_uni ON warehouse.programs(university_id);

-- If pgvector is installed later, embedding columns can be migrated from JSONB to vector
-- and indexed with HNSW / IVFFLAT.
