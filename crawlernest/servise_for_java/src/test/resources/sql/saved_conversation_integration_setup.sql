-- Mirrors the tables AuthSchemaInitializer creates at application startup.
-- CREATE TABLE IF NOT EXISTS means these are no-ops against a bootstrapped
-- database, so the test runs on the real tables; the definitions only
-- materialize on a bare one.
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.app_user (
    id            BIGSERIAL    PRIMARY KEY,
    email         VARCHAR(320) UNIQUE NOT NULL,
    password_hash VARCHAR(72)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouse.saved_conversation (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES warehouse.app_user(id),
    session_id  VARCHAR(64)  NOT NULL,
    title       VARCHAR(200) NOT NULL,
    turns_json  JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT saved_conversation_user_session_key UNIQUE (user_id, session_id)
);

-- savingAConversationTouchesNoPipelineTable() queries these three pipeline
-- tables directly to prove the conversation write path never touches them.
-- They come from the crawler pipeline, not from anything this test class
-- inserts, so on a bootstrapped database (local dev) these CREATE TABLE IF
-- NOT EXISTS are no-ops and the test runs against the real tables -- same as
-- above. On CI's bare database they used to exist only if surefire happened
-- to run RankingApiIntegrationTest (rankings_integration_setup.sql) first;
-- default test order is filesystem/classpath scan order, which is not
-- guaranteed stable, so whether this test passed depended on discovery order
-- rather than on anything it asserts. Definitions copied verbatim from
-- rankings_integration_setup.sql so both stay self-contained the same way.
CREATE TABLE IF NOT EXISTS warehouse.countries (
    country_id SERIAL PRIMARY KEY,
    country_code TEXT UNIQUE,
    country_name TEXT NOT NULL UNIQUE,
    region_name TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS warehouse.ranking_source (
    ranking_source_id SMALLSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_version TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.source_university_mapping (
    source_mapping_id BIGSERIAL PRIMARY KEY,
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_entity_id TEXT NOT NULL,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    match_method TEXT NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE (ranking_source_id, source_entity_id)
);

CREATE TABLE IF NOT EXISTS warehouse.ranking_record (
    ranking_record_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_mapping_id BIGINT
        REFERENCES warehouse.source_university_mapping(source_mapping_id),
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
    CHECK (score IS NULL OR score >= 0)
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
