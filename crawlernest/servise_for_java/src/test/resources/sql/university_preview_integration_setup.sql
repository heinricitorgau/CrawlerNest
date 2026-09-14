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
