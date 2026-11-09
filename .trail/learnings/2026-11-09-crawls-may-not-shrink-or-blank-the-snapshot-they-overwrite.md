---
title: Crawls may not shrink or blank the snapshot they overwrite
author: Heinricitorgau
date: 2026-11-09
branch: main
id: l-5b3e91c7
scope: repo
status: active
src: agent
touches:
  - crawlernest/crawlernest-jobs/snapshot_guard.py
  - crawlernest/crawlernest-jobs/the_crawler.py
  - crawlernest/crawlernest-jobs/arwu_crawler.py
  - crawlernest/run_pipeline.py
---

## Decided
THE, ARWU and QS universe crawls compare their rows with the snapshot on disk before writing, and refuse when the row count drops more than 5% or a row that had a name, rank or country now has it empty. Rows are matched by `id` (THE, ARWU) or `detail_url` (QS). `CRAWLERNEST_ALLOW_SNAPSHOT_REGRESSION=1` writes anyway. A refused QS run records `failure_classification: snapshot_regression` in run_status.json and leaves all three snapshot files alone.

## Tried and ruled out
- Per-source fixes only (ARWU's TruncatedTableError): it catches the payload reading as nothing, not a payload that reads as fewer rows, and THE had no check at all.
- Comparing blank-field totals: QS global already has 3 blank countries at HEAD, so totals hide which row changed. The check is per row.

## Watch out
- The 2026-11-08 QS global crawl returned China University of Mining and Technology with country "" and still reported live_ok. Those files were restored, not committed. If QS keeps returning it blank, every QS global crawl is refused until someone looks; that is intended.
- A `--limit` run into the committed QS directory is refused too. Write to another output dir.
- Only the file being replaced is compared, so first crawls and fresh output dirs always pass.

In the code: crawlernest/crawlernest-jobs/snapshot_guard.py (check_snapshot_regression, find_regressions); tests in crawlernest/crawlernest-tests/test_snapshot_guard.py.
