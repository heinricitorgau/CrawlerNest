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
    -- match method, lives in warehouse.source_university_mapping; this is the
    -- denormalised answer plus the mapping it came from, exactly as
    -- ranking_record carries canonical_university_id and source_mapping_id.
    canonical_university_id BIGINT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    source_mapping_id BIGINT NULL
        REFERENCES warehouse.source_university_mapping(source_mapping_id),
    entity_resolution_status TEXT NOT NULL DEFAULT 'unresolved',

    -- What a requirement applies to. One page can publish several:
    -- Imperial tiers IELTS 6.5 / 7.0 by programme, UCL by level. A single
    -- university-level number either picks one tier or averages them, and
    -- neither is what any applicant must meet.
    --
    --   programme            programme_name says which (faculty optional)
    --   faculty              every programme in faculty, programme_name NULL
    --   institution_minimum  the page states a floor for all programmes;
    --                        individual programmes may ask for more
    --   unspecified          one number, and the page's scope for it was not
    --                        established. Every row written before this column
    --                        existed is this. It is not a programme requirement
    --                        and must not be presented as one.
    degree_level TEXT NOT NULL DEFAULT 'unknown',
    faculty TEXT NULL,
    programme_name TEXT NULL,
    -- Normalised faculty|programme, '' when both are NULL. The natural key
    -- needs a value that does not change with case or spacing, which the
    -- printed names do. Computed by admission_programme_key() in
    -- crawlernest_admission_crawler/source_identity.py.
    programme_key TEXT NOT NULL DEFAULT '',
    requirement_scope TEXT NOT NULL DEFAULT 'unspecified',

    -- The intake a requirement is for. Entry conditions change year to year, so
    -- two intakes are two facts, not one row overwritten.
    --   page_stated        the page named the intake or academic year
    --   deadline_inferred  derived from application_deadline, not stated
    --   unknown            neither; intake_year is NULL
    intake_year INTEGER NULL,
    intake_year_basis TEXT NOT NULL DEFAULT 'unknown',

    -- Requirements. These were keys inside raw_payload; every one of them is
    -- filtered or sorted on by the recommendation view, which had to dig them
    -- out with ->> and a cast on every read.
    ielts_requirement DOUBLE PRECISION NULL,
    toefl_requirement INTEGER NULL,
    duolingo_requirement INTEGER NULL,
    gpa_requirement DOUBLE PRECISION NULL,
    application_deadline DATE NULL,

    -- Still the right home for deadline_candidates, which is one-to-many
    -- (early / final / rolling), and for anything a new source starts
    -- reporting before it earns a column.
    raw_payload JSONB NULL,

    -- When the page content was fetched, which is what a staleness disclosure
    -- has to name. extracted_at is when the numbers were pulled out of it, and a
    -- run over checked-in snapshots extracts today from HTML fetched months ago.
    --   live      fetched_at is the HTTP fetch time
    --   snapshot  read from a stored copy, fetched_at is when that copy was
    --             taken, or NULL if nobody recorded it
    --   unknown   rows written before fetch provenance was kept
    fetched_at TIMESTAMPTZ NULL,
    fetch_mode TEXT NOT NULL DEFAULT 'unknown',

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

-- Programme, intake and fetch granularity (2026-09-14). Existing rows take the
-- defaults, which say what is true of them: scope unspecified, intake unknown,
-- fetch provenance unknown. Nothing is inferred for them here -- the next
-- ingest derives what it can, and a guess in SQL would be a second
-- implementation of a rule that lives in Python.
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS source_mapping_id BIGINT
    REFERENCES warehouse.source_university_mapping(source_mapping_id);
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS faculty TEXT;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS programme_name TEXT;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS programme_key TEXT NOT NULL DEFAULT '';
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS requirement_scope TEXT NOT NULL DEFAULT 'unspecified';
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS intake_year INTEGER;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS intake_year_basis TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS fetched_at TIMESTAMPTZ;
ALTER TABLE warehouse.admission_record
    ADD COLUMN IF NOT EXISTS fetch_mode TEXT NOT NULL DEFAULT 'unknown';

-- A table created as admission_records_preview never got this default, so an
-- insert that omitted the column failed on NOT NULL instead of reading as
-- unresolved.
ALTER TABLE warehouse.admission_record
    ALTER COLUMN entity_resolution_status SET DEFAULT 'unresolved';

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
-- One row per page, degree level, programme and intake. degree_level and
-- programme_key are NOT NULL, and intake_year -- which is legitimately unknown
-- -- is covered by NULLS NOT DISTINCT (PostgreSQL 15+). Without either, NULLs
-- compare distinct, ON CONFLICT never fires, and every re-crawl appends.

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS admission_records_preview_normalized_university_name_source_key;
ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS admission_records_preview_normalized_university_name_sourc_key;

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS uq_admission_record_source_entity;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT uq_admission_record_source_entity
    UNIQUE NULLS NOT DISTINCT (source_code, source_entity_id, degree_level, programme_key, intake_year);

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_requirement_scope;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_requirement_scope CHECK (
        requirement_scope IN ('programme', 'faculty', 'institution_minimum', 'unspecified')
    );

-- The scope has to match the names that say what it covers. A programme row
-- with no programme, or an institution-wide row carrying one, is a row whose
-- number cannot be attributed.
ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_scope_shape;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_scope_shape CHECK (
        (requirement_scope = 'programme' AND programme_name IS NOT NULL)
     OR (requirement_scope = 'faculty' AND faculty IS NOT NULL AND programme_name IS NULL)
     OR (requirement_scope IN ('institution_minimum', 'unspecified')
         AND faculty IS NULL AND programme_name IS NULL)
    );

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_programme_names;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_programme_names CHECK (
        (faculty IS NULL OR btrim(faculty) <> '')
    AND (programme_name IS NULL OR btrim(programme_name) <> '')
    AND ((programme_key = '') = (faculty IS NULL AND programme_name IS NULL))
    );

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_intake;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_intake CHECK (
        intake_year_basis IN ('page_stated', 'deadline_inferred', 'unknown')
    AND ((intake_year IS NULL) = (intake_year_basis = 'unknown'))
    AND (intake_year IS NULL OR intake_year BETWEEN 2000 AND 2100)
    );

ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_fetch;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_fetch CHECK (
        fetch_mode IN ('live', 'snapshot', 'unknown')
    AND (fetch_mode <> 'live' OR fetched_at IS NOT NULL)
    );

-- Provenance without a university is a contradiction.
ALTER TABLE warehouse.admission_record
    DROP CONSTRAINT IF EXISTS ck_admission_record_mapping_needs_canonical;
ALTER TABLE warehouse.admission_record
    ADD CONSTRAINT ck_admission_record_mapping_needs_canonical CHECK (
        source_mapping_id IS NULL OR canonical_university_id IS NOT NULL
    );

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

CREATE INDEX IF NOT EXISTS idx_admission_record_canonical_programme
    ON warehouse.admission_record(canonical_university_id, degree_level, intake_year, requirement_scope);

-- ---------------------------------------------------------
-- Admission mappings move to warehouse.source_university_mapping
-- ---------------------------------------------------------
--
-- Admission entity resolution used to write warehouse.source_mapping. It now
-- writes the unified table under source_code, like every ranking source. The
-- existing mappings are copied across once -- including inactive (rejected)
-- ones, so a withdrawn match stays withdrawn -- with what the unified table
-- has no column for kept in metadata.
--
-- ON CONFLICT DO NOTHING: once the resolver has written a mapping in the new
-- table, that row is the live one and a re-run must not overwrite it with the
-- legacy copy.
INSERT INTO warehouse.source_university_mapping (
    source_code,
    ranking_source_id,
    source_entity_id,
    canonical_university_id,
    match_method,
    confidence_score,
    is_active,
    first_seen_at,
    last_seen_at,
    metadata
)
SELECT
    sm.source_name,
    NULL,
    sm.source_entity_id,
    sm.canonical_university_id,
    sm.match_method,
    sm.confidence_score,
    sm.is_active,
    sm.first_seen_at,
    sm.last_seen_at,
    COALESCE(sm.metadata, '{}'::jsonb) || jsonb_build_object(
        'migrated_from', 'warehouse.source_mapping',
        'legacy_mapping_id', sm.mapping_id,
        'legacy_review_status', sm.review_status,
        'legacy_threshold_used', sm.threshold_used,
        'legacy_matched_alias_id', sm.matched_alias_id
    )
FROM warehouse.source_mapping sm
JOIN warehouse.entity_source es
    ON es.source_code = sm.source_name
   AND es.source_kind = 'admission'
ON CONFLICT (source_code, source_entity_id) DO NOTHING;

-- Retire the legacy copies, so the only live assertion about an admission
-- page's university is the unified row. Left active, a later remap in the new
-- table would sit beside a legacy row still claiming the old match.
UPDATE warehouse.source_mapping sm
SET is_active = FALSE,
    metadata = COALESCE(sm.metadata, '{}'::jsonb)
        || jsonb_build_object('superseded_by', 'warehouse.source_university_mapping'),
    last_seen_at = CURRENT_TIMESTAMP
FROM warehouse.entity_source es
WHERE es.source_code = sm.source_name
  AND es.source_kind = 'admission'
  AND sm.is_active
  AND EXISTS (
      SELECT 1
      FROM warehouse.source_university_mapping u
      WHERE u.source_code = sm.source_name
        AND u.source_entity_id = sm.source_entity_id
  );

-- Link existing rows to the mapping that resolved them, where the mapping still
-- names the same university. Where it does not, NULL is the honest answer.
UPDATE warehouse.admission_record ar
SET source_mapping_id = m.source_mapping_id
FROM warehouse.source_university_mapping m
WHERE ar.source_mapping_id IS NULL
  AND m.source_code = ar.source_code
  AND m.source_entity_id = ar.source_entity_id
  AND m.canonical_university_id = ar.canonical_university_id
  AND m.is_active;
