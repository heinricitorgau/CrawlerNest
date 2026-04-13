DELETE FROM analytics.aggregated_rankings
WHERE ranking_year IN (2098, 2099)
   OR canonical_university_id BETWEEN 990001 AND 990040;

DELETE FROM analytics.aggregation_runs
WHERE ranking_year IN (2098, 2099)
   OR run_label = 'ranking_api_integration_test';

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id BETWEEN 990001 AND 990040;

DELETE FROM warehouse.university_alias
WHERE canonical_university_id BETWEEN 990001 AND 990040;

DELETE FROM warehouse.countries
WHERE country_id = 990004
   OR country_id = 990005
   OR country_id = 990006
   OR country_name = 'CrawlerNest Integrationland';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
SELECT 990001, 'CHE', 'Switzerland', 'Europe'
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.countries
    WHERE country_name = 'Switzerland'
);

UPDATE warehouse.countries
SET region_name = 'Europe'
WHERE country_name = 'Switzerland';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
SELECT 990002, 'USA', 'United States', 'North America'
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.countries
    WHERE country_name = 'United States'
);

UPDATE warehouse.countries
SET region_name = 'North America'
WHERE country_name = 'United States';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
SELECT 990003, 'NLD', 'Netherlands', 'Europe'
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.countries
    WHERE country_name = 'Netherlands'
);

UPDATE warehouse.countries
SET region_name = 'Europe'
WHERE country_name = 'Netherlands';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
SELECT 990005, 'GBR', 'United Kingdom', 'Europe'
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.countries
    WHERE country_name = 'United Kingdom'
);

UPDATE warehouse.countries
SET region_name = 'Europe'
WHERE country_name = 'United Kingdom';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
SELECT 990006, 'ESP', 'Spain', 'Europe'
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.countries
    WHERE country_name = 'Spain'
);

UPDATE warehouse.countries
SET region_name = 'Europe'
WHERE country_name = 'Spain';

INSERT INTO warehouse.countries (country_id, country_code, country_name, region_name)
VALUES (990004, 'TST', 'CrawlerNest Integrationland', 'Integration')
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
    990001,
    'eth-zurich-integration',
    'ETH Zurich',
    'eth zurich',
    country_id,
    'active'
FROM warehouse.countries
WHERE country_name = 'Switzerland'
ORDER BY country_id
LIMIT 1
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    country_id,
    status
)
SELECT
    990029,
    'university-of-barcelona-integration',
    'University of Barcelona',
    'university of barcelona',
    country_id,
    'active'
FROM warehouse.countries
WHERE country_name = 'Spain'
ORDER BY country_id
LIMIT 1
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    country_id,
    status
)
SELECT
    990028,
    'university-of-oxford-integration',
    'University of Oxford',
    'university of oxford',
    country_id,
    'active'
FROM warehouse.countries
WHERE country_name = 'United Kingdom'
ORDER BY country_id
LIMIT 1
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    country_id,
    status
)
SELECT
    990002,
    'massachusetts-institute-of-technology-integration',
    'Massachusetts Institute of Technology',
    'massachusetts institute of technology',
    country_id,
    'active'
FROM warehouse.countries
WHERE country_name = 'United States'
ORDER BY country_id
LIMIT 1
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    country_id,
    status
)
SELECT
    990003,
    'delft-university-of-technology-integration',
    'Delft University of Technology',
    'delft university of technology',
    country_id,
    'active'
FROM warehouse.countries
WHERE country_name = 'Netherlands'
ORDER BY country_id
LIMIT 1
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

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
    990004,
    'active'
FROM generate_series(4, 27) AS gs
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    country_id = EXCLUDED.country_id,
    status = EXCLUDED.status;

INSERT INTO warehouse.university_alias (
    canonical_university_id,
    alias_text,
    alias_normalized,
    source_name,
    is_primary,
    is_abbreviation
)
VALUES
    (990001, 'ETH', 'eth', 'manual', FALSE, TRUE),
    (990002, 'MIT', 'mit', 'manual', FALSE, TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO analytics.aggregation_runs (
    aggregation_run_id,
    run_label,
    ranking_year,
    universe_type,
    universe_key,
    aggregation_method_version,
    status,
    input_record_count,
    output_record_count
)
VALUES (
    990001,
    'ranking_api_integration_test',
    2099,
    'global',
    'global',
    'rank_agg_test_v1',
    'finished',
    28,
    28
)
ON CONFLICT (aggregation_run_id) DO UPDATE
SET run_label = EXCLUDED.run_label,
    ranking_year = EXCLUDED.ranking_year,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    aggregation_method_version = EXCLUDED.aggregation_method_version,
    status = EXCLUDED.status,
    input_record_count = EXCLUDED.input_record_count,
    output_record_count = EXCLUDED.output_record_count;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    universe_type,
    universe_key,
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
    'global',
    'global',
    CASE
        WHEN gs = 26 THEN 25
        WHEN gs = 27 THEN 26
        ELSE gs
    END,
    100.0 - gs,
    1.0,
    '{"QS": 1, "THE": 2}'::jsonb,
    '{"QS": 99.0, "THE": 98.0}'::jsonb,
    '{"QS": 0.5, "THE": 0.5}'::jsonb,
    'rank_agg_test_v1'
FROM generate_series(1, 27) AS gs
ON CONFLICT (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version) DO UPDATE
SET aggregation_run_id = EXCLUDED.aggregation_run_id,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    display_rank = EXCLUDED.display_rank,
    composite_score = EXCLUDED.composite_score,
    coverage_ratio = EXCLUDED.coverage_ratio,
    source_ranks_json = EXCLUDED.source_ranks_json,
    source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
    source_weights_used_json = EXCLUDED.source_weights_used_json;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    universe_type,
    universe_key,
    display_rank,
    composite_score,
    coverage_ratio,
    source_ranks_json,
    source_normalized_scores_json,
    source_weights_used_json,
    aggregation_method_version
)
VALUES (
    990001,
    990028,
    2099,
    'global',
    'global',
    28,
    72.0,
    1.0,
    '{"QS": 28, "THE": 28}'::jsonb,
    '{"QS": 72.0, "THE": 72.0}'::jsonb,
    '{"QS": 0.5, "THE": 0.5}'::jsonb,
    'rank_agg_test_v1'
)
ON CONFLICT (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version) DO UPDATE
SET aggregation_run_id = EXCLUDED.aggregation_run_id,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    display_rank = EXCLUDED.display_rank,
    composite_score = EXCLUDED.composite_score,
    coverage_ratio = EXCLUDED.coverage_ratio,
    source_ranks_json = EXCLUDED.source_ranks_json,
    source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
    source_weights_used_json = EXCLUDED.source_weights_used_json;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    universe_type,
    universe_key,
    display_rank,
    composite_score,
    coverage_ratio,
    source_ranks_json,
    source_normalized_scores_json,
    source_weights_used_json,
    aggregation_method_version
)
VALUES (
    990001,
    990029,
    2099,
    'global',
    'global',
    29,
    71.0,
    1.0,
    '{"QS": 29, "THE": 29}'::jsonb,
    '{"QS": 71.0, "THE": 71.0}'::jsonb,
    '{"QS": 0.5, "THE": 0.5}'::jsonb,
    'rank_agg_test_v1'
)
ON CONFLICT (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version) DO UPDATE
SET aggregation_run_id = EXCLUDED.aggregation_run_id,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    display_rank = EXCLUDED.display_rank,
    composite_score = EXCLUDED.composite_score,
    coverage_ratio = EXCLUDED.coverage_ratio,
    source_ranks_json = EXCLUDED.source_ranks_json,
    source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
    source_weights_used_json = EXCLUDED.source_weights_used_json;

INSERT INTO warehouse.ranking_decision_preview (
    normalized_university_name,
    ranking_year,
    aggregated_rank,
    source_count,
    std_deviation,
    trust_score,
    trust_level,
    sources,
    aggregation_explain,
    trust_explain
)
SELECT
    cu.display_name_normalized,
    ar.ranking_year,
    ar.display_rank::double precision,
    2,
    1.0,
    88.0,
    'high',
    ar.source_ranks_json,
    jsonb_build_object(
        'sources', ar.source_ranks_json,
        'aggregated_rank', ar.display_rank::double precision,
        'source_count', 2,
        'std_deviation', 1.0,
        'aggregation_method', ar.aggregation_method_version
    ),
    jsonb_build_object(
        'coverage_score', 0.6667,
        'consistency_score', 80.0,
        'std_deviation', 1.0,
        'notes', jsonb_build_array(
            'Two ranking sources available.',
            'Ranking sources show strong agreement.'
        )
    )
FROM analytics.aggregated_rankings ar
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = ar.canonical_university_id
WHERE ar.ranking_year = 2099
  AND ar.universe_type = 'global'
  AND ar.universe_key = 'global'
ON CONFLICT (normalized_university_name, ranking_year) DO UPDATE
SET aggregated_rank = EXCLUDED.aggregated_rank,
    source_count = EXCLUDED.source_count,
    std_deviation = EXCLUDED.std_deviation,
    trust_score = EXCLUDED.trust_score,
    trust_level = EXCLUDED.trust_level,
    sources = EXCLUDED.sources,
    aggregation_explain = EXCLUDED.aggregation_explain,
    trust_explain = EXCLUDED.trust_explain,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO analytics.aggregation_runs (
    aggregation_run_id,
    run_label,
    ranking_year,
    universe_type,
    universe_key,
    aggregation_method_version,
    status,
    input_record_count,
    output_record_count
)
VALUES (
    990002,
    'ranking_api_integration_test_europe',
    2099,
    'region',
    'europe',
    'rank_agg_test_v1',
    'finished',
    4,
    4
)
ON CONFLICT (aggregation_run_id) DO UPDATE
SET run_label = EXCLUDED.run_label,
    ranking_year = EXCLUDED.ranking_year,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    aggregation_method_version = EXCLUDED.aggregation_method_version,
    status = EXCLUDED.status,
    input_record_count = EXCLUDED.input_record_count,
    output_record_count = EXCLUDED.output_record_count;

INSERT INTO analytics.aggregated_rankings (
    aggregation_run_id,
    canonical_university_id,
    ranking_year,
    universe_type,
    universe_key,
    display_rank,
    composite_score,
    coverage_ratio,
    source_ranks_json,
    source_normalized_scores_json,
    source_weights_used_json,
    aggregation_method_version
)
VALUES
    (990002, 990001, 2099, 'region', 'europe', 1, 99.0, 1.0, '{"QS": 1}'::jsonb, '{"QS": 99.0}'::jsonb, '{"QS": 1.0}'::jsonb, 'rank_agg_test_v1'),
    (990002, 990003, 2099, 'region', 'europe', 2, 93.0, 1.0, '{"QS": 3}'::jsonb, '{"QS": 93.0}'::jsonb, '{"QS": 1.0}'::jsonb, 'rank_agg_test_v1'),
    (990002, 990028, 2099, 'region', 'europe', 3, 72.0, 1.0, '{"QS": 28}'::jsonb, '{"QS": 72.0}'::jsonb, '{"QS": 1.0}'::jsonb, 'rank_agg_test_v1'),
    (990002, 990029, 2099, 'region', 'europe', 4, 68.0, 1.0, '{"QS": 45}'::jsonb, '{"QS": 68.0}'::jsonb, '{"QS": 1.0}'::jsonb, 'rank_agg_test_v1')
ON CONFLICT (canonical_university_id, ranking_year, universe_type, universe_key, aggregation_method_version) DO UPDATE
SET aggregation_run_id = EXCLUDED.aggregation_run_id,
    universe_type = EXCLUDED.universe_type,
    universe_key = EXCLUDED.universe_key,
    display_rank = EXCLUDED.display_rank,
    composite_score = EXCLUDED.composite_score,
    coverage_ratio = EXCLUDED.coverage_ratio,
    source_ranks_json = EXCLUDED.source_ranks_json,
    source_normalized_scores_json = EXCLUDED.source_normalized_scores_json,
    source_weights_used_json = EXCLUDED.source_weights_used_json;
