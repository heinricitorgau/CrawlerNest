# crawlernest-db-writer

Database ingestion and write logic for the CrawlerNest data-hub.

## Features
- **Dimension & Fact Management**: Specialized methods for upserting universities, rankings, and admission requirements.
- **Transaction Reliability**: 
    - Supports `rollback()` to clear aborted transaction states in PostgreSQL.
    - Integrated with `run_pipeline.py` for early commit of crawl sessions to ensure foreign key integrity.
- **Batch Processing**: Optimized `insert_X_batch` methods for high-throughput ingestion.

## Files
- `db_writer.py`: Main persistence service for dimensions and facts.
- `db.py`: Backward-compatible PostgreSQL connection helper for old imports.
- `postgres_pool.py`: Connection pooling management.
