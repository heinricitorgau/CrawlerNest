-- =========================================================
-- CrawlerNest Admission Records Schema (PostgreSQL)
-- =========================================================
-- Requires entity_resolution_postgresql.sql (canonical_university)
--        and mapping_review_postgresql.sql (entity_source)
--
-- Loaded BEFORE recommendation_postgresql.sql: that file's view reads this
-- table, and it drops and recreates the view from its own text, so the rename
-- below has to land first.
--
-- The table was warehouse.admission_records_preview. It is the warehouse fact
-- table for admission requirements, not a preview of one, and the fields that
-- are actually queried are columns here rather than keys inside raw_payload.
-- See docs/migrations/ADMISSION_SCHEMA_CONVERGENCE.md.

CREATE SCHEMA IF NOT EXISTS warehouse;

-- ---------------------------------------------------------
-- Rename. No-op once it has run.
-- ---------------------------------------------------------
--
-- If BOTH names somehow exist, this raises 42P07 -- a duplicate-table error,
-- which both schema appliers swallow, so the migration would report success
-- while leaving every row in the old table and every reader pointed at the
-- empty new one. bootstrap_postgres.py and pipeline/utils/schema.py check for
-- that state first and refuse; applying this file by hand with psql does not
-- get that check, so look before you run it.
ALTER TABLE IF EXISTS warehouse.admission_records_preview
    RENAME TO admission_record;

ALTER INDEX IF EXISTS warehouse.admission_records_preview_pkey
    RENAME TO admission_record_pkey;

ALTER INDEX IF EXISTS warehouse.idx_admission_records_preview_source
    RENAME TO idx_admission_record_source;

ALTER INDEX IF EXISTS warehouse.idx_admission_records_preview_canonical
    RENAME TO idx_admission_record_canonical;

-- ---------------------------------------------------------
-- Target shape, for a database created from scratch
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.admission_record (
    id BIGSERIAL PRIMARY KEY,

    -- Identity. source_entity_id is derived from the URL and deliberately
    -- carries no university name: warehouse.mapping_review keys a durable
    -- human decision on this pair, and a key the resolver can change is a key
    -- the decision silently stops applying to.
    source_code TEXT NOT NULL DEFAULT 'university_site'
        REFERENCES warehouse.entity_source(source_code),
    source_entity_id TEXT NOT NULL,
    source_url TEXT NOT NULL,

    -- What the source said, kept verbatim for review and audit.
    university_name TEXT NOT NULL,
    normalized_university_name TEXT NOT NULL,
    country TEXT NULL,

    -- Entity resolution outcome. The mapping itself, with its confidence and
    -- match method, lives in warehouse.source_mapping; this is the denormalised
    -- answer, mirroring how ranking_record carries canonical_university_id.
    canonical_university_id BIGINT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    entity_resolution_status TEXT NOT NULL DEFAULT 'unresolved',

    -- Requirements. These were keys inside raw_payload; every one of them is
    -- filtered or sorted on by the recommendation view, which had to dig them
    -- out with ->> and a cast on every read.
    degree_level TEXT NOT NULL DEFAULT 'unknown',
    ielts_requirement DOUBLE PRECISION NULL,
    toefl_requirement INTEGER NULL,
    duolingo_requirement INTEGER NULL,
    gpa_requirement DOUBLE PRECISION NULL,
    application_deadline DATE NULL,

    -- Still the right home for deadline_candidates, which is one-to-many
    -- (early / final / rolling), and for anything a new source starts
    -- reporting before it earns a column.
    raw_payload JSONB NULL,

    extracted_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- Migration, for a database that already had the old shape
-- ---------------------------------------------------------

ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS source_code TEXT NOT NULL DEFAULT 'university_site';
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS source_entity_id TEXT;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS degree_level TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS duolingo_requirement INTEGER;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS gpa_requirement DOUBLE PRECISION;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS application_deadline DATE;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

-- Lift the values out of raw_payload. Each cast is guarded by a pattern rather
-- than wrapped in NULLIF: a single unparseable value would otherwise abort the
-- whole bootstrap, and losing one deadline is better than losing the schema.
UPDATE warehouse.admission_record
SET application_deadline = (raw_payload ->> 'deadline')::date
WHERE application_deadline IS NULL
  AND raw_payload ->> 'deadline' ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';

UPDATE warehouse.admission_record
SET gpa_requirement = (raw_payload ->> 'gpa_requirement')::double precision
WHERE gpa_requirement IS NULL
  AND raw_payload ->> 'gpa_requirement' ~ '^[0-9]+(\.[0-9]+)?$';

UPDATE warehouse.admission_record
SET duolingo_requirement = (raw_payload ->> 'duolingo_requirement')::integer
WHERE duolingo_requirement IS NULL
  AND raw_payload ->> 'duolingo_requirement' ~ '^[0-9]+$';

UPDATE warehouse.admission_record
SET degree_level = raw_payload ->> 'degree_level'
WHERE degree_level = 'unknown'
  AND raw_payload ->> 'degree_level' IN ('undergraduate', 'postgraduate', 'doctoral');

-- Mirrors admission_source_entity_id() in
-- crawlernest_admission_crawler/source_identity.py. The two must agree.
UPDATE warehouse.admission_record
SET source_entity_id = RTRIM(
        REGEXP_REPLACE(
            REGEXP_REPLACE(LOWER(TRIM(source_url)), '^https?://', ''),
            '[?#].*$',
            ''
        ),
        '/'
    )
WHERE source_entity_id IS NULL;

ALTER TABLE warehouse.admission_record
    ALTER COLUMN source_entity_id SET NOT NULL;

-- ---------------------------------------------------------
-- Keys and constraints
-- ---------------------------------------------------------
--
-- The natural key moves off (normalized_university_name, source_url). The
-- first half of that pair was the value entity resolution decides, so the key
-- changed whenever the resolver changed its mind, and every write became an
-- insert of a near-duplicate.
--
-- degree_level is NOT NULL because it is part of this key and PostgreSQL
-- treats NULLs as distinct: a nullable column here would make ON CONFLICT
-- never fire, and every re-crawl would append a new row.

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS admission_records_preview_normalized_university_name_source_key;
ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS admission_records_preview_normalized_university_name_sourc_key;

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS uq_admission_record_source_entity;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT uq_admission_record_source_entity
    UNIQUE (source_code, source_entity_id, degree_level);

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS fk_admission_record_entity_source;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT fk_admission_record_entity_source
    FOREIGN KEY (source_code) REFERENCES warehouse.entity_source(source_code);

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_degree_level;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_degree_level CHECK (
        degree_level IN ('undergraduate', 'postgraduate', 'doctoral', 'unknown')
    );

-- Bounds copied from _validate_extracted_fields in
-- crawlernest/crawlernest-admission-crawler/crawlers/university_site.py, so
-- the constraint cannot reject a value the crawler already accepted.
ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_ranges;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_ranges CHECK (
        (ielts_requirement IS NULL OR ielts_requirement BETWEEN 0 AND 9)
    AND (toefl_requirement IS NULL OR toefl_requirement BETWEEN 0 AND 120)
    AND (duolingo_requirement IS NULL OR duolingo_requirement BETWEEN 10 AND 160)
    AND (gpa_requirement IS NULL OR gpa_requirement BETWEEN 0 AND 4.0)
    );

CREATE INDEX IF NOT EXISTS idx_admission_record_source
    ON warehouse.admission_record(source_code, source_entity_id);

CREATE INDEX IF NOT EXISTS idx_admission_record_canonical
    ON warehouse.admission_record(canonical_university_id);

CREATE INDEX IF NOT EXISTS idx_admission_record_resolution_status
    ON warehouse.admission_record(entity_resolution_status);
