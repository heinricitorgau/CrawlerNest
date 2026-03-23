-- =========================================================
-- CrawlerNest Ranking Aggregation Schema (PostgreSQL)
-- =========================================================
-- Depends on:
-- - warehouse.canonical_university
-- - warehouse.ranking_source (from multi_source_postgresql.sql)

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------
-- Aggregation run control / lineage
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.aggregation_runs (
    aggregation_run_id BIGSERIAL PRIMARY KEY,
    run_label TEXT,
    ranking_year INTEGER NOT NULL,
    aggregation_method_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running', -- running/finished/failed
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    input_record_count INTEGER NOT NULL DEFAULT 0,
    output_record_count INTEGER NOT NULL DEFAULT 0,
    config_json JSONB,
    notes TEXT
);

-- ---------------------------------------------------------
-- Source weight config (versioned)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.source_weight_config (
    source_weight_config_id BIGSERIAL PRIMARY KEY,
    aggregation_method_version TEXT NOT NULL,
    source_code TEXT NOT NULL, -- QS/THE/ARWU
    weight NUMERIC(8,6) NOT NULL CHECK (weight >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from DATE,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Aggregated rankings (explainable deterministic output)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.aggregated_rankings (
    aggregated_ranking_id BIGSERIAL PRIMARY KEY,
    aggregation_run_id BIGINT REFERENCES analytics.aggregation_runs(aggregation_run_id),
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_year INTEGER NOT NULL,
    display_rank INTEGER,
    composite_score NUMERIC(10,6),
    coverage_ratio NUMERIC(8,6), -- sum(weights_used) / sum(configured_weights)
    source_ranks_json JSONB NOT NULL,             -- {"QS":10,"THE":25,"ARWU":40}
    source_normalized_scores_json JSONB NOT NULL, -- {"QS":99.1,...}
    source_weights_used_json JSONB NOT NULL,      -- {"QS":0.4,...}
    aggregation_method_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (canonical_university_id, ranking_year, aggregation_method_version)
);

-- ---------------------------------------------------------
-- Helpful derived view (latest run per method/year)
-- ---------------------------------------------------------
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
) t
ON ar.ranking_year = t.ranking_year
AND ar.aggregation_method_version = t.aggregation_method_version
AND ar.aggregation_run_id = t.latest_run_id;

-- ---------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_aggregation_runs_year_method
    ON analytics.aggregation_runs(ranking_year, aggregation_method_version, started_at);

CREATE INDEX IF NOT EXISTS idx_aggregated_rankings_year_rank
    ON analytics.aggregated_rankings(ranking_year, aggregation_method_version, display_rank);

CREATE INDEX IF NOT EXISTS idx_aggregated_rankings_canonical
    ON analytics.aggregated_rankings(canonical_university_id, ranking_year);

CREATE INDEX IF NOT EXISTS idx_source_weight_config_method_source
    ON analytics.source_weight_config(aggregation_method_version, source_code, is_active);

CREATE UNIQUE INDEX IF NOT EXISTS uq_source_weight_config_version_source_effective
    ON analytics.source_weight_config(
        aggregation_method_version,
        source_code,
        COALESCE(effective_from, DATE '1970-01-01')
    );
