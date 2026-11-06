---
title: An ARWU crawl that only read the rendered top 30 fails instead of writing the file
author: Heinricitorgau
date: 2026-11-06
branch: main
cost: { minutes: 8, tokens: 61969 }
id: l-d1ae99cb
scope: repo
status: active
src: agent
touches:
  - crawlernest/crawlernest-jobs/arwu_crawler.py
  - crawlernest/crawlernest-tests/test_arwu_crawler.py
---

## Decided
When the ARWU crawler cannot read the full ranking from the page's Nuxt payload, it now raises and writes nothing. It used to fall back to the rendered HTML table and write that. The rendered table is always the top 30, never a whole edition, so the fallback silently replaced a 1,000-row edition with 30 rows (the 2026-11-03 crawl).

The payload patterns also now skip any extra fields between univCode and score, because the site will keep adding fields there.

## Tried and ruled out
- Keeping the "degrade to the smaller table" fallback: it only protects against the payload being smaller than the rendered table, while the real failure is the payload reading as nothing.

## Watch out
- The cause was ShanghaiRanking adding an `outdated` field (value 0 on all 3,000 entries) between univCode and score. Both the literal-object and the assigned forms broke at once.
- The truncated file was written but never ingested: the database still held 961 ARWU 2026 ranks (aggregation run 59). Check the database before assuming a bad crawl reached it.
- A correct re-crawl after the fix gave exactly the committed 1,000 rows, so restoring the file from git was the same as re-crawling.

In the code: crawlernest/crawlernest-jobs/arwu_crawler.py (_LITERAL_EXTRA, _ASSIGNED_EXTRA, TruncatedTableError in crawl_arwu_rankings); tests in crawlernest/crawlernest-tests/test_arwu_crawler.py (TestPayloadToleratesAddedFields, TestRenderedTableIsNeverWritten).
