-- Modelling-layer tables and view, mirroring
-- crawlernest/crawlernest-schema/ml_postgresql.sql. Layered on top of
-- rankings_integration_setup.sql, which provides warehouse.canonical_university
-- and warehouse.countries.

CREATE TABLE IF NOT EXISTS analytics.ml_model_runs (
    ml_run_id                BIGSERIAL PRIMARY KEY,
    model_name               TEXT NOT NULL,
    model_version            TEXT NOT NULL,
    target                   TEXT NOT NULL,
    trained_at               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    training_rows            INTEGER NOT NULL,
    inference_rows           INTEGER NOT NULL,
    feature_names_json       JSONB NOT NULL,
    metrics_json             JSONB NOT NULL,
    baseline_metrics_json    JSONB NOT NULL,
    support_threshold        NUMERIC(12,6),
    notes                    TEXT,
    CONSTRAINT ck_ml_model_runs_rows CHECK (training_rows >= 0 AND inference_rows >= 0)
);

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
    is_estimated             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_ml_predictions_is_estimated CHECK (is_estimated),
    CONSTRAINT uq_ml_predictions_run_university
        UNIQUE (ml_run_id, canonical_university_id, ranking_year)
);

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
