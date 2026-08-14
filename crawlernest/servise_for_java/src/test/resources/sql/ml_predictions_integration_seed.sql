-- One model run with two estimates: one inside the model's support and one
-- outside it, so the endpoint's supported_only filter and its unsupported-row
-- caveat both have something to act on.
--
-- Uses the 990001+ canonical university ids seeded by
-- rankings_integration_seed.sql, and a distinctive model_name so cleanup can
-- target exactly these rows.

INSERT INTO analytics.ml_model_runs (
    model_name, model_version, target, trained_at,
    training_rows, inference_rows,
    feature_names_json, metrics_json, baseline_metrics_json,
    support_threshold, notes
) VALUES (
    'ml_predictions_integration_test',
    'test-0001',
    'qs_overall_score',
    TIMESTAMPTZ '2099-01-01 00:00:00+00',
    600,
    2,
    '["Academic Reputation","Employer Reputation"]'::jsonb,
    '{"rmse_mean": 0.175, "r2_mean": 0.9999}'::jsonb,
    '{"rmse": 0.783, "r2": 0.9983}'::jsonb,
    2.137164,
    'Integration test fixture.'
);

INSERT INTO analytics.ml_predictions (
    ml_run_id, canonical_university_id, ranking_year,
    predicted_value, support_distance, is_supported
)
SELECT r.ml_run_id, 990001, 2099, 42.5000, 1.100000, TRUE
  FROM analytics.ml_model_runs r
 WHERE r.model_name = 'ml_predictions_integration_test';

INSERT INTO analytics.ml_predictions (
    ml_run_id, canonical_university_id, ranking_year,
    predicted_value, support_distance, is_supported
)
SELECT r.ml_run_id, 990002, 2099, 30.2500, 9.900000, FALSE
  FROM analytics.ml_model_runs r
 WHERE r.model_name = 'ml_predictions_integration_test';

-- A second target, so the endpoints have something to leak into each other if
-- their target filter is ever dropped. The values are chosen to make a leak
-- obvious: probabilities are 0-1 while the scores above are tens, and both
-- endpoints sort by predicted_value descending.
INSERT INTO analytics.ml_model_runs (
    model_name, model_version, target, trained_at,
    training_rows, inference_rows,
    feature_names_json, metrics_json, baseline_metrics_json,
    support_threshold, notes
) VALUES (
    'ml_disagreement_integration_test',
    'test-0001',
    'qs_the_disagreement',
    TIMESTAMPTZ '2099-01-01 00:00:00+00',
    820,
    1,
    '["Academic Reputation","Employer Reputation"]'::jsonb,
    '{"roc_auc": 0.8133, "pr_auc": 0.4696}'::jsonb,
    '{"roc_auc": 0.5, "pr_auc": 0.2}'::jsonb,
    2.137164,
    'Integration test fixture.'
);

INSERT INTO analytics.ml_predictions (
    ml_run_id, canonical_university_id, ranking_year,
    predicted_value, support_distance, is_supported
)
SELECT r.ml_run_id, 990003, 2099, 0.9600, 1.050000, TRUE
  FROM analytics.ml_model_runs r
 WHERE r.model_name = 'ml_disagreement_integration_test';
