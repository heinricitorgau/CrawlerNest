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

-- admission-requirement-views:start
-- The admission columns added on 2026-09-14 and the two views every admission
-- reader goes through. Copied from crawlernest-schema/admission_postgresql.sql;
-- test_admission_readers.py fails if these copies drift from it. On a
-- bootstrapped database the columns already exist and the views are replaced
-- with identical definitions.
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS source_mapping_id BIGINT;
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS faculty TEXT;
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS programme_name TEXT;
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS programme_key TEXT NOT NULL DEFAULT '';
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS requirement_scope TEXT NOT NULL DEFAULT 'unspecified';
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS intake_year INTEGER;
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS intake_year_basis TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;
ALTER TABLE warehouse.admission_record ADD COLUMN IF NOT EXISTS fetch_mode TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE warehouse.admission_record DROP CONSTRAINT IF EXISTS uq_admission_record_source_entity;
ALTER TABLE warehouse.admission_record ADD CONSTRAINT uq_admission_record_source_entity
    UNIQUE NULLS NOT DISTINCT (source_code, source_entity_id, degree_level, programme_key, intake_year);

CREATE OR REPLACE VIEW warehouse.v_admission_requirement_institution AS
WITH scoped AS (
    SELECT
        ar.*,
        ar.requirement_scope IN ('institution_minimum', 'unspecified') AS applies_to_institution,
        MAX(ar.intake_year) FILTER (
            WHERE ar.requirement_scope IN ('institution_minimum', 'unspecified')
        ) OVER (PARTITION BY ar.canonical_university_id, ar.degree_level) AS newest_institution_intake
    FROM warehouse.admission_record ar
    WHERE ar.canonical_university_id IS NOT NULL
),
institution AS (
    SELECT
        canonical_university_id,
        degree_level,
        MIN(ielts_requirement) AS ielts_requirement,
        MIN(toefl_requirement) AS toefl_requirement,
        MIN(duolingo_requirement) AS duolingo_requirement,
        MIN(gpa_requirement) AS gpa_requirement,
        MIN(application_deadline) AS application_deadline,
        MIN(source_url) AS source_url,
        COUNT(*)::integer AS institution_row_count,
        COUNT(ielts_requirement)::integer AS institution_ielts_row_count,
        (
            COUNT(DISTINCT ielts_requirement) > 1
            OR COUNT(DISTINCT toefl_requirement) > 1
            OR COUNT(DISTINCT duolingo_requirement) > 1
            OR COUNT(DISTINCT gpa_requirement) > 1
        ) AS values_differ,
        CASE
            WHEN bool_and(requirement_scope = 'institution_minimum') THEN 'institution_minimum'
            ELSE 'unspecified'
        END AS requirement_scope,
        MAX(intake_year) AS intake_year,
        CASE
            WHEN MAX(intake_year) IS NULL THEN 'unknown'
            WHEN bool_and(intake_year_basis = 'page_stated') THEN 'page_stated'
            ELSE 'deadline_inferred'
        END AS intake_year_basis,
        bool_and(fetched_at IS NOT NULL) AS fetch_dates_recorded,
        (MIN(fetched_at) AT TIME ZONE 'UTC')::date AS oldest_fetched_on,
        (MIN(extracted_at) AT TIME ZONE 'UTC')::date AS oldest_extracted_on
    FROM scoped
    WHERE applies_to_institution
      AND intake_year IS NOT DISTINCT FROM newest_institution_intake
    GROUP BY canonical_university_id, degree_level
),
programme AS (
    SELECT
        canonical_university_id,
        degree_level,
        COUNT(*)::integer AS programme_row_count,
        COUNT(ielts_requirement)::integer AS programme_ielts_row_count,
        bool_and(fetched_at IS NOT NULL) AS fetch_dates_recorded,
        (MIN(fetched_at) AT TIME ZONE 'UTC')::date AS oldest_fetched_on,
        (MIN(extracted_at) AT TIME ZONE 'UTC')::date AS oldest_extracted_on
    FROM scoped
    WHERE NOT applies_to_institution
    GROUP BY canonical_university_id, degree_level
)
SELECT
    canonical_university_id,
    degree_level,
    i.ielts_requirement,
    i.toefl_requirement,
    i.duolingo_requirement,
    i.gpa_requirement,
    i.application_deadline,
    i.source_url,
    COALESCE(i.institution_row_count, 0) AS institution_row_count,
    COALESCE(i.institution_ielts_row_count, 0) AS institution_ielts_row_count,
    COALESCE(i.values_differ, FALSE) AS values_differ,
    i.requirement_scope,
    i.intake_year,
    COALESCE(i.intake_year_basis, 'unknown') AS intake_year_basis,
    COALESCE(p.programme_row_count, 0) AS programme_row_count,
    COALESCE(p.programme_ielts_row_count, 0) AS programme_ielts_row_count,
    COALESCE(i.fetch_dates_recorded, TRUE) AND COALESCE(p.fetch_dates_recorded, TRUE) AS fetch_dates_recorded,
    LEAST(i.oldest_fetched_on, p.oldest_fetched_on) AS oldest_fetched_on,
    LEAST(i.oldest_extracted_on, p.oldest_extracted_on) AS oldest_extracted_on
FROM institution i
FULL OUTER JOIN programme p USING (canonical_university_id, degree_level);

CREATE OR REPLACE VIEW warehouse.v_admission_requirement_summary AS
SELECT
    canonical_university_id,
    MIN(ielts_requirement) AS ielts_requirement,
    MIN(toefl_requirement) AS toefl_requirement,
    MIN(duolingo_requirement) AS duolingo_requirement,
    MIN(gpa_requirement) AS gpa_requirement,
    MIN(application_deadline) AS application_deadline,
    COUNT(*) FILTER (WHERE institution_row_count > 0)::integer AS degree_level_count,
    SUM(institution_row_count)::integer AS institution_row_count,
    SUM(institution_ielts_row_count)::integer AS institution_ielts_row_count,
    SUM(programme_row_count)::integer AS programme_row_count,
    SUM(programme_ielts_row_count)::integer AS programme_ielts_row_count,
    bool_or(values_differ) AS values_differ,
    (SUM(institution_ielts_row_count) + SUM(programme_ielts_row_count)) = 0 AS ielts_missing,
    bool_and(fetch_dates_recorded) AS fetch_dates_recorded,
    MIN(oldest_fetched_on) AS oldest_fetched_on,
    MIN(oldest_extracted_on) AS oldest_extracted_on
FROM warehouse.v_admission_requirement_institution
GROUP BY canonical_university_id;
-- admission-requirement-views:end
