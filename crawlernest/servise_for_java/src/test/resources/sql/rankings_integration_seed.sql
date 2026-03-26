DELETE FROM analytics.aggregated_rankings
WHERE ranking_year IN (2098, 2099)
   OR canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM analytics.aggregation_runs
WHERE ranking_year IN (2098, 2099)
   OR run_label = 'ranking_api_integration_test';

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM warehouse.countries
WHERE country_id = 990001
   OR country_code = 'TST';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
VALUES (990001, 'TST', 'Testland', 'Integration')
ON CONFLICT (country_id) DO UPDATE
SET country_code = EXCLUDED.country_code,
    country_name = EXCLUDED.country_name,
    region_name = EXCLUDED.region_name;

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    country_id,
    status
)
SELECT
    990000 + gs,
    'integration-test-university-' || gs,
    'Integration Test University ' || LPAD(gs::text, 2, '0'),
    'integration test university ' || LPAD(gs::text, 2, '0'),
    990001,
    'active'
FROM generate_series(1, 25) AS gs
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO analytics.aggregation_runs (
    aggregation_run_id,
    run_label,
    ranking_year,
    aggregation_method_version,
    status,
    input_record_count,
    output_record_count
)
VALUES (
    990001,
    'ranking_api_integration_test',
    2099,
    'rank_agg_test_v1',
    'finished',
    25,
    25
)
ON CONFLICT (aggregation_run_id) DO UPDATE
SET run_label = EXCLUDED.run_label,
    ranking_year = EXCLUDED.ranking_year,
    aggregation_method_version = EXCLUDED.aggregation_method_version,
    status = EXCLUDED.status,
    input_record_count = EXCLUDED.input_record_count,
    output_record_count = EXCLUDED.output_record_count;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    display_rank,
    composite_score,
    coverage_ratio,
    source_ranks_json,
    source_normalized_scores_json,
    source_weights_used_json,
    aggregation_method_version
)
SELECT
    990001,
    990000 + gs,
    2099,
    gs,
    100.0 - gs,
    1.0,
    '{"QS": 1, "THE": 2}'::jsonb,
    '{"QS": 99.0, "THE": 98.0}'::jsonb,
    '{"QS": 0.5, "THE": 0.5}'::jsonb,
    'rank_agg_test_v1'
FROM generate_series(1, 25) AS gs
ON CONFLICT (canonical_university_id, ranking_year, aggregation_method_version) DO UPDATE
SET aggregation_run_id = EXCLUDED.aggregation_run_id,
    display_rank = EXCLUDED.display_rank,
    composite_score = EXCLUDED.composite_score,
    coverage_ratio = EXCLUDED.coverage_ratio,
    source_ranks_json = EXCLUDED.source_ranks_json,
    source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
    source_weights_used_json = EXCLUDED.source_weights_used_json;
