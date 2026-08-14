-- Runs before rankings_integration_cleanup.sql: ml_predictions references
-- warehouse.canonical_university, so these rows must go first.
-- ON DELETE CASCADE on ml_run_id removes the predictions with the run.

DELETE FROM analytics.ml_model_runs
WHERE model_name IN ('ml_predictions_integration_test', 'ml_disagreement_integration_test');
