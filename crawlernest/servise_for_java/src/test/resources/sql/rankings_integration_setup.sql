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

CREATE TABLE IF NOT EXISTS analytics.aggregation_runs (
    aggregation_run_id BIGSERIAL PRIMARY KEY,
    run_label TEXT,
    ranking_year INTEGER NOT NULL,
    aggregation_method_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    input_record_count INTEGER NOT NULL DEFAULT 0,
    output_record_count INTEGER NOT NULL DEFAULT 0,
    config_json JSONB,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS analytics.aggregated_rankings (
    aggregated_ranking_id BIGSERIAL PRIMARY KEY,
    aggregation_run_id BIGINT REFERENCES analytics.aggregation_runs(aggregation_run_id),
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_year INTEGER NOT NULL,
    display_rank INTEGER,
    composite_score NUMERIC(10,6),
    coverage_ratio NUMERIC(8,6),
    source_ranks_json JSONB NOT NULL,
    source_normalized_scores_json JSONB NOT NULL,
    source_weights_used_json JSONB NOT NULL,
    aggregation_method_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canonical_university_id, ranking_year, aggregation_method_version)
);

CREATE OR REPLACE VIEW analytics.v_aggregated_rankings_latest AS
SELECT ar.*
FROM analytics.aggregated_rankings ar
JOIN (
    SELECT
        ranking_year,
        aggregation_method_version,
        MAX(aggregation_run_id) AS latest_run_id
    FROM analytics.aggregated_rankings
    GROUP BY ranking_year, aggregation_method_version
) latest
  ON ar.ranking_year = latest.ranking_year
 AND ar.aggregation_method_version = latest.aggregation_method_version
 AND ar.aggregation_run_id = latest.latest_run_id;
