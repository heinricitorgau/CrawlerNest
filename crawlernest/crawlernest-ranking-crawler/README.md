# crawlernest-ranking-crawler

Ranking-specific crawler engine for CrawlerNest.

This module is responsible for:

- crawling ranking sources such as QS, THE, and ARWU
- handling ranking universes such as global, region, and subject
- extracting structured ranking rows
- preparing normalized ranking-ready records for downstream pipeline stages

It should depend on `crawlernest-crawler-core/`, but it must not depend on the admission crawler engine.

## Files

- `engine.py`: ranking engine entrypoint
- `models.py`: `RankingRecord`
- `sources/qs.py`: example QS crawler stub
- `sources/the.py`: THE crawler placeholder
- `sources/arwu.py`: ARWU crawler placeholder
- `extractors/ranking_rows.py`: lightweight row-to-model conversion helper
