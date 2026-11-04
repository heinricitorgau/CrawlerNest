-- =========================================================
-- US federal institutional data (College Scorecard, IPEDS)
-- =========================================================
--
-- Requires entity_resolution_postgresql.sql (warehouse.canonical_university).
--
-- Facts the U.S. Department of Education publishes about an institution: admission
-- rate, cost, completion, earnings, enrollment. This is NOT a ranking source. Nothing
-- reads these tables into the composite score, the coverage ratio or the confidence
-- label, which count ranking sources (crawlernest/core/dataset.py:DATASET_SOURCES).
--
-- Both tables are a copy of committed files and are never the source of truth:
--   crawlernest-kb/us_institutions/matches.json    which UNITID each university is, and why
--   crawlernest-kb/us_institutions/manifest.json   the federal files read, with their SHA-256
--   crawlernest-kb/us_institutions/records.json    the values
-- crawlernest-jobs/us_institution_loader.py writes those files and loads these
-- tables from them (`ingest`). A university with no row was not matched to a UNITID,
-- or is outside the United States -- our gap, not a statement about the institution.
--
-- Public domain: U.S. federal government works. Readers still name the source.

CREATE TABLE IF NOT EXISTS warehouse.us_institution (
    canonical_university_id BIGINT PRIMARY KEY
        REFERENCES warehouse.canonical_university(canonical_university_id) ON DELETE CASCADE,
    -- IPEDS Unit ID, which College Scorecard uses too.
    unitid INTEGER NOT NULL UNIQUE CHECK (unitid > 0),
    opeid TEXT,
    -- The name the federal files print, which may differ from the warehouse's.
    institution_name TEXT NOT NULL,
    city TEXT,
    state_code TEXT,
    website TEXT,
    wikidata_id TEXT CHECK (wikidata_id IS NULL OR wikidata_id ~ '^Q[0-9]+$'),
    -- How the UNITID was tied to the university; see the loader's docstring.
    -- No method compares names.
    match_method TEXT NOT NULL CHECK (match_method IN ('wikidata_ipeds_id', 'reviewed_override')),
    match_evidence JSONB,
    in_scorecard BOOLEAN NOT NULL,
    in_ipeds_directory BOOLEAN NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One value per university, source and metric. Every value carries the period it
-- describes and the file it came from: an admission rate is for one fall, earnings
-- are for a cohort that entered a decade earlier, and the two must not be read as
-- the same year.
--
-- status says what the source said, not what we guessed:
--   reported            the institution's figure
--   imputed             not the figure as reported: NCES estimated it for a nonresponding institution
--                       or corrected it (status_detail gives NCES's flag: "L: Imputed using the Group
--                       Median procedure", "C: Analyst corrected reported value")
--   privacy_suppressed  withheld by the source ("PS"); the figure exists but is not published
--   not_available       not in the file ("NA", blank, or no row)
--   not_applicable      the item does not apply to this institution
-- Only reported and imputed rows have a value; none of the others is zero.
CREATE TABLE IF NOT EXISTS warehouse.us_institution_metric (
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.us_institution(canonical_university_id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('COLLEGE_SCORECARD', 'IPEDS')),
    metric_key TEXT NOT NULL,
    -- The column in the federal file (ADM_RATE, NPT4_PRIV, APPLCN).
    source_field TEXT NOT NULL,
    unit TEXT NOT NULL CHECK (unit IN ('ratio', 'percent', 'usd', 'count', 'score', 'code', 'text')),
    value_number NUMERIC,
    -- A code's label, or the value of a text field.
    value_text TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('reported', 'imputed', 'privacy_suppressed', 'not_available', 'not_applicable')),
    status_detail TEXT,
    -- Verbatim from the source's documentation ("Fall 2024, reported in IPEDS DCY2024-25").
    reference_period TEXT NOT NULL,
    release TEXT NOT NULL,
    PRIMARY KEY (canonical_university_id, source, metric_key),
    CONSTRAINT us_institution_metric_value_iff_figure CHECK (
        (status IN ('reported', 'imputed')) = (value_number IS NOT NULL OR value_text IS NOT NULL)
    )
);
