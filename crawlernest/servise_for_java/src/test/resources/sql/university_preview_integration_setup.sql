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

CREATE TABLE IF NOT EXISTS warehouse.ranking_records_preview (
    id BIGSERIAL PRIMARY KEY,
    university_name TEXT NOT NULL,
    normalized_university_name TEXT NOT NULL,
    source TEXT NOT NULL,
    rank INTEGER NOT NULL,
    year INTEGER NOT NULL,
    source_url TEXT,
    extracted_at TIMESTAMPTZ NOT NULL,
    ranking_year INTEGER NOT NULL,
    universe_type TEXT NOT NULL,
    universe_key TEXT NOT NULL,
    canonical_university_id BIGINT,
    entity_resolution_status TEXT NOT NULL,
    source_resolution_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.admission_records_preview (
    id BIGSERIAL PRIMARY KEY,
    university_name TEXT NOT NULL,
    normalized_university_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    country TEXT,
    ielts_requirement DOUBLE PRECISION,
    toefl_requirement INTEGER,
    extracted_at TIMESTAMPTZ NOT NULL,
    canonical_university_id BIGINT,
    entity_resolution_status TEXT NOT NULL,
    raw_payload JSONB
);
