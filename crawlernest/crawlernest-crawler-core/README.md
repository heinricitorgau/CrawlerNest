# crawlernest-crawler-core

Shared crawler runtime primitives for CrawlerNest.

This module contains only reusable crawling capabilities:

- HTTP client wrapper
- retry logic
- rate limiting
- logging
- base crawler helpers
- snapshot/cache hooks

It must not contain ranking-specific or admission-specific business logic.

## Files

- `http_client.py`: minimal sync HTTP wrapper
- `retry.py`: retry helper
- `rate_limit.py`: request pacing helper
- `logger.py`: shared crawler logger factory
- `base.py`: thin base crawler with snapshot helpers
