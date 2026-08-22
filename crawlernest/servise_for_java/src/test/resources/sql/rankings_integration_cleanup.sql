DELETE FROM warehouse.admission_record
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM warehouse.ranking_records_preview
WHERE canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM analytics.aggregated_rankings
WHERE ranking_year IN (2098, 2099)
   OR canonical_university_id BETWEEN 990001 AND 990030;

DELETE FROM analytics.aggregation_runs
WHERE ranking_year IN (2098, 2099)
   OR run_label = 'ranking_api_integration_test';

DELETE FROM warehouse.ranking_decision_preview
WHERE ranking_year IN (2098, 2099)
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
