# crawlernest-jobs

Job-based crawling pipelines and orchestration.

This module is no longer the desired long-term home for all crawler behavior.
Its role is to coordinate jobs, pipeline commands, and batch execution around the crawler engines.

## Files
- `crawler.py`: Legacy coordination logic for crawler execution.
- `clawer_main.py`: Entry point for starting crawls.
- `pipeline_command_router.py`: command routing used by `run_pipeline.py`.
- `qs_universe_crawlers.py`, `the_crawler.py`, `arwu_crawler.py`: existing source-specific crawl implementations that should gradually be wrapped or migrated behind `crawlernest_ranking_crawler/` (repo root).

## Boundary

- shared transport/runtime concerns belong in `crawlernest-crawler-core/`
- ranking-source crawling belongs in `crawlernest_ranking_crawler/` (repo root)
- university admission crawling belongs in `crawlernest-admission-crawler/`
- this module should stay focused on orchestration, routing, resume, and batch control
