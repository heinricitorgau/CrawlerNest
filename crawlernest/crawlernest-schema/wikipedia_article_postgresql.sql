-- =========================================================
-- Wikipedia article text for a university
-- =========================================================
--
-- Requires entity_resolution_postgresql.sql (warehouse.canonical_university).
--
-- One row per university: the English Wikipedia article matched to it, as
-- sections of plain text, with the revision it was read at. The university page
-- shows it as an introduction.
--
-- This is Wikipedia's text, not warehouse data. It is licensed CC BY-SA 4.0, so
-- every reader of this table must show page_url (or the revision) and the
-- licence beside the text. Nothing computes from it: an article may quote a rank
-- from an edition the warehouse does not hold, or hold differently, and those
-- figures are Wikipedia's.
--
-- The table is a copy of committed files and is never the source of truth:
--   crawlernest-kb/wikipedia/en/matches.json          which article, and why
--   crawlernest-kb/wikipedia/en/articles/*.jsonl.gz   the text
-- crawlernest-jobs/wikipedia_profile_loader.py writes those files and loads this
-- table from them (`ingest`). A university with no row has no matched article --
-- our gap, not a statement that Wikipedia has none.
--
-- match_method is how the article was tied to the university; see the loader's
-- docstring. No method compares names loosely.

CREATE TABLE IF NOT EXISTS warehouse.university_wikipedia_article (
    canonical_university_id BIGINT PRIMARY KEY
        REFERENCES warehouse.canonical_university(canonical_university_id) ON DELETE CASCADE,
    language_code TEXT NOT NULL DEFAULT 'en',
    wikidata_id TEXT NOT NULL CHECK (wikidata_id ~ '^Q[0-9]+$'),
    page_id BIGINT NOT NULL,
    page_title TEXT NOT NULL,
    page_url TEXT NOT NULL,
    revision_id BIGINT NOT NULL,
    revision_timestamp TIMESTAMPTZ,
    match_method TEXT NOT NULL
        CHECK (match_method IN ('wikidata_source_id', 'exact_title', 'label_search', 'reviewed_override')),
    match_evidence JSONB,
    -- [{"level": 1, "heading": null, "text": "..."}, {"level": 2, "heading": "History", "text": "..."}]
    -- The first section is the lead: level 1, no heading.
    sections JSONB NOT NULL CHECK (jsonb_typeof(sections) = 'array'),
    char_count INTEGER NOT NULL,
    license TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_university_wikipedia_article_wikidata
    ON warehouse.university_wikipedia_article(wikidata_id);
