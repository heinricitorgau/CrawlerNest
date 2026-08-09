-- ---------------------------------------------------------------------------
-- CrawlerNest modelling layer storage
--
-- Estimates produced by crawlernest/crawlernest-ml/ live here and nowhere else.
-- They are deliberately kept out of analytics.aggregated_rankings: a published
-- rank and a model's guess at a withheld score are different kinds of claim,
-- and mixing them in one table is how the second quietly starts being read as
-- the first.
--
-- Two rules are enforced by the schema rather than by convention:
--
--   * ml_predictions.is_estimated cannot be set false. The column exists so a
--     consumer can read it, not so a writer can turn the disclosure off.
--   * every prediction carries its support distance and flag, so no consumer
--     can surface an estimate without also having the means to say how far
--     outside the training data it sits.
--
-- Applied by `run_pipeline.py bootstrap-postgres`.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS analytics;

-- One row per training run. Metrics are stored beside the baseline they were
-- measured against, because a model metric with no baseline is not a result.
CREATE TABLE IF NOT EXISTS analytics.ml_model_runs (
    ml_run_id                BIGSERIAL PRIMARY KEY,
    model_name               TEXT NOT NULL,
    model_version            TEXT NOT NULL,
    target                   TEXT NOT NULL,
    trained_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    training_rows            INTEGER NOT NULL,
    inference_rows           INTEGER NOT NULL,
    feature_names_json       JSONB NOT NULL,
    metrics_json             JSONB NOT NULL,
    baseline_metrics_json    JSONB NOT NULL,
    support_threshold        NUMERIC(12,6),
    notes                    TEXT,
    CONSTRAINT ck_ml_model_runs_rows CHECK (training_rows >= 0 AND inference_rows >= 0)
);

CREATE INDEX IF NOT EXISTS idx_ml_model_runs_name_time
    ON analytics.ml_model_runs (model_name, trained_at DESC);

-- One row per estimated value.
CREATE TABLE IF NOT EXISTS analytics.ml_predictions (
    ml_prediction_id         BIGSERIAL PRIMARY KEY,
    ml_run_id                BIGINT NOT NULL
                                 REFERENCES analytics.ml_model_runs(ml_run_id) ON DELETE CASCADE,
    canonical_university_id  BIGINT NOT NULL
                                 REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_year             INTEGER NOT NULL,
    predicted_value          NUMERIC(12,4) NOT NULL,
    support_distance         NUMERIC(12,6) NOT NULL,
    is_supported             BOOLEAN NOT NULL,
    -- Not a flag a writer may clear: everything in this table is an estimate.
    is_estimated             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_ml_predictions_is_estimated CHECK (is_estimated),
    CONSTRAINT uq_ml_predictions_run_university
        UNIQUE (ml_run_id, canonical_university_id, ranking_year)
);

CREATE INDEX IF NOT EXISTS idx_ml_predictions_university
    ON analytics.ml_predictions (canonical_university_id, ranking_year);

CREATE INDEX IF NOT EXISTS idx_ml_predictions_supported
    ON analytics.ml_predictions (ml_run_id, is_supported);

-- Latest run per *target*, with the university names resolved. The API reads
-- this view rather than the tables so "latest" is defined in one place.
--
-- Keyed on target rather than model_name deliberately. Two models estimating the
-- same quantity are competitors, not colleagues: picking the latest per model
-- would return both of their answers for the same university, silently
-- concatenated. One target has one current answer, and the most recent run is
-- it.
CREATE OR REPLACE VIEW analytics.v_ml_predictions_latest AS
WITH latest_run AS (
    SELECT DISTINCT ON (target)
           ml_run_id, model_name, model_version, target, trained_at, support_threshold
      FROM analytics.ml_model_runs
     ORDER BY target, trained_at DESC, ml_run_id DESC
)
SELECT r.model_name,
       r.model_version,
       r.target,
       r.trained_at,
       r.support_threshold,
       p.canonical_university_id,
       cu.display_name AS university_name,
       cu.canonical_slug AS slug,
       c.country_name,
       p.ranking_year,
       p.predicted_value,
       p.support_distance,
       p.is_supported,
       p.is_estimated
  FROM latest_run r
  JOIN analytics.ml_predictions p ON p.ml_run_id = r.ml_run_id
  JOIN warehouse.canonical_university cu
       ON cu.canonical_university_id = p.canonical_university_id
  LEFT JOIN warehouse.countries c ON c.country_id = cu.country_id;
