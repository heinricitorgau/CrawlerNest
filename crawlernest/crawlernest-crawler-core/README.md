# crawlernest-crawler-core

Shared crawler runtime primitives for CrawlerNest.

This module is intended to stay thin enough to be treated as a separately developable shared subproject inside the main CrawlerNest workspace.

This module contains only reusable crawling capabilities:

- HTTP client wrapper
- retry logic
- rate limiting
- logging
- base crawler helpers
- snapshot/cache hooks

It must not contain ranking-specific or admission-specific business logic.

It should also not absorb recommendation, warehouse, or product-facing decision logic.

## Role In The Workspace

`crawlernest-crawler-core/` exists to give both crawler engines a stable shared runtime boundary:

- `crawlernest_ranking_crawler/` (repo root) depends on it for crawler runtime behavior
- `crawlernest-admission-crawler/` depends on it for crawler runtime behavior
- shared fixes to retry / logging / pacing should land here
- source-specific parsing or extraction should stay in the engine that owns that source

This means the module can evolve somewhat independently, but only as a reusable runtime dependency rather than a business-logic sink.

## Files

- `http_client.py`: minimal sync HTTP wrapper
- `retry.py`: retry helper
- `rate_limit.py`: request pacing helper
- `logger.py`: shared crawler logger factory
- `base.py`: thin base crawler with snapshot helpers
