CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

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

CREATE TABLE IF NOT EXISTS warehouse.canonical_university_link (
    canonical_university_link_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    university_id INTEGER NOT NULL,
    link_method TEXT NOT NULL DEFAULT 'manual',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.admission_requirements (
    admission_requirement_id BIGSERIAL PRIMARY KEY,
    university_id INTEGER NOT NULL,
    ielts_min NUMERIC(4,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.ranking_decision_preview (
    normalized_university_name TEXT NOT NULL,
    ranking_year INTEGER NOT NULL,
    aggregated_rank DOUBLE PRECISION,
    source_count INTEGER,
    std_deviation DOUBLE PRECISION,
    trust_score DOUBLE PRECISION,
    trust_level TEXT,
    sources JSONB NOT NULL DEFAULT '{}'::jsonb,
    aggregation_explain JSONB NOT NULL DEFAULT '{}'::jsonb,
    trust_explain JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ranking_decision_preview_test
        UNIQUE (normalized_university_name, ranking_year)
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

-- Source-comparison and evidence queries read warehouse.ranking_record directly. The
-- fixtures deliberately leave it empty (those endpoints fall back to the preview tables),
-- but the table must exist or the context fails on a database the pipeline has not built.
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

CREATE TABLE IF NOT EXISTS analytics.aggregation_runs (
    aggregation_run_id BIGSERIAL PRIMARY KEY,
    run_label TEXT,
    ranking_year INTEGER NOT NULL,
    universe_type TEXT NOT NULL DEFAULT 'global',
    universe_key TEXT NOT NULL DEFAULT 'global',
    aggregation_method_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    input_record_count INTEGER NOT NULL DEFAULT 0,
    output_record_count INTEGER NOT NULL DEFAULT 0,
    config_json JSONB,
    notes TEXT
);

ALTER TABLE analytics.aggregation_runs
    ADD COLUMN IF NOT EXISTS universe_type TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregation_runs
    ADD COLUMN IF NOT EXISTS universe_key TEXT NOT NULL DEFAULT 'global';

CREATE TABLE IF NOT EXISTS analytics.aggregated_rankings (
    aggregated_ranking_id BIGSERIAL PRIMARY KEY,
    aggregation_run_id BIGINT REFERENCES analytics.aggregation_runs(aggregation_run_id),
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_year INTEGER NOT NULL,
    universe_type TEXT NOT NULL DEFAULT 'global',
    universe_key TEXT NOT NULL DEFAULT 'global',
    display_rank INTEGER,
    composite_score NUMERIC(10,6),
    coverage_ratio NUMERIC(8,6),
    source_ranks_json JSONB NOT NULL,
    source_normalized_scores_json JSONB NOT NULL,
    source_weights_used_json JSONB NOT NULL,
    aggregation_method_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE analytics.aggregated_rankings
    ADD COLUMN IF NOT EXISTS universe_type TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregated_rankings
    ADD COLUMN IF NOT EXISTS universe_key TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregated_rankings
    DROP CONSTRAINT IF EXISTS aggregated_rankings_canonical_university_id_ranking_year_ag_key;

ALTER TABLE analytics.aggregated_rankings
    DROP CONSTRAINT IF EXISTS uq_aggregated_rankings_universe_test;

ALTER TABLE analytics.aggregated_rankings
    ADD CONSTRAINT uq_aggregated_rankings_universe_test
    UNIQUE (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version);

CREATE OR REPLACE VIEW analytics.v_aggregated_rankings_latest AS
WITH ranked_finished_runs AS (
    SELECT
        arun.aggregation_run_id,
        arun.ranking_year,
        arun.universe_type,
        arun.universe_key,
        arun.aggregation_method_version,
        ROW_NUMBER() OVER (
            PARTITION BY arun.ranking_year, arun.universe_type, arun.universe_key
            ORDER BY arun.finished_at DESC NULLS LAST, arun.aggregation_run_id DESC
        ) AS run_order
    FROM analytics.aggregation_runs arun
    WHERE arun.status = 'finished'
),
latest_finished_runs AS (
    SELECT
        aggregation_run_id,
        ranking_year,
        universe_type,
        universe_key,
        aggregation_method_version
    FROM ranked_finished_runs
    WHERE run_order = 1
),
latest_run_rows AS (
    SELECT
        ar.aggregated_ranking_id,
        ar.aggregation_run_id,
        ar.canonical_university_id,
        ar.ranking_year,
        ar.universe_type,
        ar.universe_key,
        ar.display_rank AS stored_display_rank,
        ar.composite_score,
        ar.coverage_ratio,
        ar.source_ranks_json,
        ar.source_normalized_scores_json,
        ar.source_weights_used_json,
        ar.aggregation_method_version,
        ar.created_at,
        ar.updated_at,
        latest.aggregation_method_version AS run_method_version
    FROM analytics.aggregated_rankings ar
    JOIN latest_finished_runs latest
      ON ar.ranking_year = latest.ranking_year
     AND ar.universe_type = latest.universe_type
     AND ar.universe_key = latest.universe_key
     AND ar.aggregation_run_id = latest.aggregation_run_id
),
deduped_latest AS (
    SELECT *
    FROM (
        SELECT
            lrr.*,
            ROW_NUMBER() OVER (
                PARTITION BY lrr.ranking_year, lrr.universe_type, lrr.universe_key, lrr.canonical_university_id
                ORDER BY
                    CASE
                        WHEN lrr.aggregation_method_version = lrr.run_method_version THEN 0
                        ELSE 1
                    END,
                    lrr.updated_at DESC,
                    lrr.aggregated_ranking_id DESC
            ) AS canonical_order
        FROM latest_run_rows lrr
    ) ranked_rows
    WHERE canonical_order = 1
)
SELECT
    aggregated_ranking_id,
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    CASE
        WHEN stored_display_rank IS NULL THEN NULL
        ELSE ROW_NUMBER() OVER (
            PARTITION BY ranking_year, universe_type, universe_key
            ORDER BY stored_display_rank ASC NULLS LAST, canonical_university_id ASC
        )::INTEGER
    END AS display_rank,
    composite_score,
    coverage_ratio,
    source_ranks_json,
    source_normalized_scores_json,
    source_weights_used_json,
    aggregation_method_version,
    created_at,
    updated_at
    ,
    universe_type,
    universe_key
FROM deduped_latest;
