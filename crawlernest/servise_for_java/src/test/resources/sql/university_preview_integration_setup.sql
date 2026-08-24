CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.canonical_university (
    canonical_university_id BIGSERIAL PRIMARY KEY,
    canonical_slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    display_name_normalized TEXT NOT NULL,
    native_name TEXT,
    country_id INTEGER,
    city_name TEXT,
    website_url TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.university_alias (
    alias_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    alias_text TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    language_code VARCHAR(12),
    script_code VARCHAR(8),
    source_name TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_abbreviation BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Mirrors warehouse.ranking_source / warehouse.ranking_record from
-- crawlernest-schema/multi_source_postgresql.sql. CREATE TABLE IF NOT EXISTS
-- means that against a bootstrapped database these are no-ops and the test runs
-- on the real tables; the definitions below only materialize on a bare one.
-- source_mapping_id keeps its type but drops the FK, so this fixture does not
-- have to stand up warehouse.source_university_mapping as well.
CREATE TABLE IF NOT EXISTS warehouse.ranking_source (
    ranking_source_id SMALLSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_version TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.ranking_record (
    ranking_record_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_mapping_id BIGINT,
    ranking_year INTEGER NOT NULL,
    ranking_type TEXT NOT NULL DEFAULT 'world',
    universe_type TEXT NOT NULL DEFAULT 'global',
    universe_key TEXT NOT NULL DEFAULT 'global',
    rank_position INTEGER,
    score NUMERIC(8,4),
    score_scale NUMERIC(8,4),
    source_version TEXT,
    source_url TEXT,
    metadata JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id TEXT,
    CHECK (rank_position IS NULL OR rank_position > 0),
    CHECK (score IS NULL OR score >= 0),
    CONSTRAINT uq_ranking_record_universe UNIQUE (
        canonical_university_id,
        ranking_source_id,
        ranking_year,
        ranking_type,
        universe_type,
        universe_key
    )
);

CREATE TABLE IF NOT EXISTS warehouse.admission_record (
    id BIGSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL DEFAULT 'university_site',
    source_entity_id TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL,
    university_name TEXT NOT NULL,
    normalized_university_name TEXT NOT NULL,
    country TEXT,
    canonical_university_id BIGINT,
    entity_resolution_status TEXT NOT NULL,
    degree_level TEXT NOT NULL DEFAULT 'unknown',
    ielts_requirement DOUBLE PRECISION,
    toefl_requirement INTEGER,
    duolingo_requirement INTEGER,
    gpa_requirement DOUBLE PRECISION,
    application_deadline DATE,
    raw_payload JSONB,
    extracted_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_admission_record_source_entity
        UNIQUE (source_code, source_entity_id, degree_level)
);
