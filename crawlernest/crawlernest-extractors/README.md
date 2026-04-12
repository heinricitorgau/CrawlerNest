# crawlernest-extractors

Fetchers, parsers, and source-specific extractors for the CrawlerNest platform.

This module is a reusable helper layer, not the top-level crawler runtime.
It should support crawler engines with fetch / parse utilities without owning ranking-vs-admission business orchestration.

## Files
- `fetcher.py`: Synchronous and asynchronous HTTP clients for QS rankings.
- `extractor.py`: HTML parsing engine for extracting scores and requirements.

## Boundary

- shared retry / rate-limit / logging / snapshot concerns belong in `crawlernest-crawler-core/`
- ranking-source execution belongs in `crawlernest-ranking-crawler/`
- university-site admission execution belongs in `crawlernest-admission-crawler/`
- this module should hold reusable fetchers and extractors that those engines can call
