# crawlernest-schema

Source of truth for the CrawlerNest database schema.

For the ranking pipeline, schema responsibilities are now more explicitly split across:

- staging-oriented persistence for controlled ingest
- warehouse landing structures for warehouse-ready ranking rows
- canonical and alias structures for deterministic entity resolution
- aggregation and recommendation schemas that remain downstream of the landing/resolution path

## Files
- `postgresql_schema.sql`: Base PostgreSQL warehouse/staging schema.
- `entity_resolution_postgresql.sql`: Canonical university and alias schema.
- `multi_source_postgresql.sql`: Multi-source ranking integration schema.
- `ranking_aggregation_postgresql.sql`: Aggregated ranking schema.
- `recommendation_postgresql.sql`: Recommendation and candidate-view schema.
- `subject_ranking_ids.json`: Mapping of subject IDs used by the crawler.
