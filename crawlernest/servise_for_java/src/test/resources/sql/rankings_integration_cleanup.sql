DELETE FROM warehouse.admission_record
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM analytics.aggregated_rankings
WHERE ranking_year IN (2098, 2099, 2100)
   OR canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM analytics.aggregation_runs
WHERE ranking_year IN (2098, 2099, 2100)
   OR run_label IN ('ranking_api_integration_test', 'ranking_api_integration_test_shadow');

DELETE FROM warehouse.ranking_decision_preview
WHERE ranking_year IN (2098, 2099, 2100)
   OR normalized_university_name LIKE 'integration test university %'
   OR normalized_university_name IN (
       'eth zurich',
       'massachusetts institute of technology',
       'delft university of technology',
       'university of oxford',
       'university of barcelona'
   );

DELETE FROM warehouse.university_alias
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM warehouse.countries
WHERE country_id BETWEEN 990001 AND 990006
   OR country_name = 'CrawlerNest Integrationland';
