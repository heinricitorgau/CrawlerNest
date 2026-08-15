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
    universe_type TEXT NOT NULL DEFAULT 'global',
    universe_key TEXT NOT NULL DEFAULT 'global',
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
    universe_type TEXT NOT NULL DEFAULT 'global',
    universe_key TEXT NOT NULL DEFAULT 'global',
    display_rank INTEGER,
    composite_score NUMERIC(10,6),
    coverage_ratio NUMERIC(8,6), -- sum(weights_used) / sum(configured_weights)
    source_ranks_json JSONB NOT NULL,             -- {"QS":10,"THE":25,"ARWU":40}
    source_normalized_scores_json JSONB NOT NULL, -- {"QS":99.1,...}
    source_weights_used_json JSONB NOT NULL,      -- {"QS":0.222,...} null where a source is absent
    aggregation_method_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE analytics.aggregation_runs
    ADD COLUMN IF NOT EXISTS universe_type TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregation_runs
    ADD COLUMN IF NOT EXISTS universe_key TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregated_rankings
    ADD COLUMN IF NOT EXISTS universe_type TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregated_rankings
    ADD COLUMN IF NOT EXISTS universe_key TEXT NOT NULL DEFAULT 'global';

ALTER TABLE analytics.aggregated_rankings
    DROP CONSTRAINT IF EXISTS aggregated_rankings_canonical_university_id_ranking_year_ag_key;

ALTER TABLE analytics.aggregated_rankings
    DROP CONSTRAINT IF EXISTS uq_aggregated_rankings_universe;

ALTER TABLE analytics.aggregated_rankings
    ADD CONSTRAINT uq_aggregated_rankings_universe
    UNIQUE (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version);

-- ---------------------------------------------------------
-- Helpful derived view (latest run per method/year)
-- ---------------------------------------------------------
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

-- ---------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_aggregation_runs_year_method
    ON analytics.aggregation_runs(ranking_year, universe_type, universe_key, aggregation_method_version, started_at);

CREATE INDEX IF NOT EXISTS idx_aggregated_rankings_year_rank
    ON analytics.aggregated_rankings(ranking_year, universe_type, universe_key, aggregation_method_version, display_rank);

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
