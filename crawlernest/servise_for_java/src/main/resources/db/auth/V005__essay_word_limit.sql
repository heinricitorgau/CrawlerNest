-- =========================================================
-- desk.essay_review: the word limit the essay is written to
-- =========================================================
--
-- Application essays have a limit (650 for the Common App personal statement,
-- 250 or 550 for many supplements). The review shows word_count against it.
-- It is the user's statement of the prompt's limit, not something CrawlerNest
-- looks up: limits change by year and by school.
--
-- Run by AuthSchemaInitializer after V004 on every start; IF NOT EXISTS makes it
-- idempotent.

ALTER TABLE desk.essay_review ADD COLUMN IF NOT EXISTS word_limit INTEGER
    CHECK (word_limit BETWEEN 1 AND 5000);
