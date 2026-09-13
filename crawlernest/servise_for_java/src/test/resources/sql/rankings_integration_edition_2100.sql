-- A second edition of the rankings fixture, 2100, with different ranks.
--
-- Copied from the 2099 global rows after rankings_integration_seed.sql has run.
-- Source ranks are set to QS 500 / THE 900 so that any read which picks this
-- edition up by mistake is visible in its output (a rank spread of 400, not 1).
-- rankings_integration_cleanup.sql removes it.

INSERT INTO analytics.aggregation_runs (
    aggregation_run_id, run_label, ranking_year, universe_type, universe_key,
    aggregation_method_version, status, input_record_count, output_record_count
)
VALUES (990100, 'ranking_api_integration_test_shadow', 2100, 'global', 'global',
        'rank_agg_test_v1', 'finished', 29, 29)
ON CONFLICT (aggregation_run_id) DO NOTHING;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id, canonical_university_id, ranking_year, universe_type, universe_key,
    display_rank, composite_score, coverage_ratio, source_ranks_json,
    source_normalized_scores_json, source_weights_used_json, aggregation_method_version
)
SELECT 990100, canonical_university_id, 2100, universe_type, universe_key,
       display_rank + 100, composite_score / 2, coverage_ratio,
       '{"QS": 500, "THE": 900}'::jsonb, source_normalized_scores_json,
       source_weights_used_json, aggregation_method_version
FROM analytics.aggregated_rankings
WHERE ranking_year = 2099 AND universe_type = 'global' AND universe_key = 'global'
ON CONFLICT DO NOTHING;

INSERT INTO warehouse.ranking_decision_preview (
    normalized_university_name, ranking_year, aggregated_rank, source_count, std_deviation,
    trust_score, trust_level, sources, aggregation_explain, trust_explain
)
SELECT normalized_university_name, 2100, aggregated_rank + 100, source_count, std_deviation,
       trust_score, trust_level, '{"QS": 500, "THE": 900}'::jsonb, aggregation_explain, trust_explain
FROM warehouse.ranking_decision_preview
WHERE ranking_year = 2099
ON CONFLICT DO NOTHING;
