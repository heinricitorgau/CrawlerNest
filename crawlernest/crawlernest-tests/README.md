# crawlernest-tests

Integration and regression tests for the CrawlerNest platform.

## Usage
Run tests from the project root:
```bash
python3 crawlernest-tests/run_tests.py
```

## Files
- `run_tests.py`: Unified test runner.
- `test_ranking_api.py`: Robust API tests with mocks.
- `test_extractor.py`: Unit tests for parsing logic.
- `test_fetcher.py`: Unit tests for network fetchers.
- `test_db_writer.py`: Integration tests for the database layer.
