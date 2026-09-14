-- =========================================================
-- Human review of fuzzy entity-resolution matches
-- =========================================================
--
-- A reviewer's decision deliberately does NOT live on
-- warehouse.source_university_mapping. That table is pipeline-owned and its
-- upsert overwrites match_method, confidence_score and metadata on every
-- ingest, so a decision stored there would survive exactly until the next
-- run-the-rankings -- silently, with no error.
--
-- canonical_university_id is the exception: since 2026-09-14 an active
-- mapping keeps its university and the upsert refuses to move it (see
-- multi_source/continuity.py). A remap filed here is the one thing that does.
--
-- Nor is `is_active = FALSE` a rejection: nothing in the aggregation path
-- reads that column. The credit a university gets for a source comes from
-- warehouse.ranking_record, which the pipeline writes during ingestion, so a
-- decision only takes effect if it is applied *before* those rows are built.
--
-- Ownership is therefore split down the middle:
--   * the API writes this table and no pipeline table
--   * the pipeline reads this table and never writes it
--
-- Decisions are durable input, not derived state. They are re-applied on every
-- run, which is what makes re-ingestion safe.
--
-- Reviews are keyed by source_code, not by ranking_source_id. The question a
-- reviewer answers -- is this name this university -- does not depend on
-- whether the payload was a rank or an entry requirement, so admission
-- sources share this table and this screen rather than growing a parallel
-- one. See docs/migrations/ADMISSION_SCHEMA_CONVERGENCE.md.

CREATE SCHEMA IF NOT EXISTS warehouse;

-- ---------------------------------------------------------
-- Sources that can be entity-resolved and reviewed
-- ---------------------------------------------------------
--
-- warehouse.ranking_source is the registry of *ranking* sources and stays
-- that. This is the wider set: anything that names universities and therefore
-- has to be matched to a canonical one. Registering a new source is an INSERT
-- here, not a schema change, which is the reason this is a table rather than
-- a CHECK constraint on source_code.
--
-- Kept in step with warehouse.ranking_source by
-- MultiSourceRankingRepository.upsert_ranking_sources, which mirrors every
-- code it registers into this table. Without that the FK below would reject
-- the first review filed against a newly added ranking source.
CREATE TABLE IF NOT EXISTS warehouse.entity_source (
    source_code  TEXT PRIMARY KEY,
    source_kind  TEXT NOT NULL,          -- ranking / admission
    display_name TEXT NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    metadata     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO warehouse.entity_source (source_code, source_kind, display_name)
SELECT rs.source_code, 'ranking', rs.source_name
FROM warehouse.ranking_source rs
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO warehouse.entity_source (source_code, source_kind, display_name)
VALUES ('university_site', 'admission', 'University admission pages')
ON CONFLICT (source_code) DO NOTHING;

-- Every mapping names a registered source. Added here rather than in
-- multi_source_postgresql.sql, which runs before this registry exists.
ALTER TABLE warehouse.source_university_mapping
    DROP CONSTRAINT IF EXISTS fk_source_university_mapping_entity_source;
ALTER TABLE warehouse.source_university_mapping
    ADD CONSTRAINT fk_source_university_mapping_entity_source
    FOREIGN KEY (source_code) REFERENCES warehouse.entity_source(source_code);

-- ---------------------------------------------------------
-- Standing decisions
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS warehouse.mapping_review (
    mapping_review_id BIGSERIAL PRIMARY KEY,

    source_code TEXT NOT NULL
        REFERENCES warehouse.entity_source(source_code),
    source_entity_id TEXT NOT NULL,

    -- Superseded by source_code. Kept nullable for one release so the change
    -- can be reverted without touching data; drop it in the next round.
    ranking_source_id SMALLINT
        REFERENCES warehouse.ranking_source(ranking_source_id),

    -- What the reviewer was actually looking at, copied verbatim. The mapping
    -- row's own metadata is rewritten by the next ingest, so without this the
    -- decision would be left with no recoverable evidence behind it.
    reviewed_source_name TEXT NOT NULL,
    reviewed_canonical_university_id BIGINT
        REFERENCES warehouse.canonical_university(canonical_university_id),
    reviewed_match_method TEXT NOT NULL,
    reviewed_confidence_score NUMERIC(6,4),

    -- confirmed : the resolver was right, keep its target
    -- remapped  : the resolver was wrong, use decided_canonical_university_id
    -- rejected  : no canonical university applies; drop the source credit
    decision TEXT NOT NULL
        CHECK (decision IN ('confirmed', 'rejected', 'remapped')),
    decided_canonical_university_id BIGINT
        REFERENCES warehouse.canonical_university(canonical_university_id),

    decided_by TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT,

    -- One standing decision per source entity; re-deciding replaces it.
    CONSTRAINT uq_mapping_review_source_entity
        UNIQUE (source_code, source_entity_id),

    -- A rejection points at nothing; anything else must name a target.
    CONSTRAINT ck_mapping_review_target CHECK (
        (decision = 'rejected' AND decided_canonical_university_id IS NULL)
        OR (decision <> 'rejected' AND decided_canonical_university_id IS NOT NULL)
    )
);

-- ---------------------------------------------------------
-- Migration: ranking_source_id -> source_code
-- ---------------------------------------------------------
-- No-ops on a database created from the definition above. On an existing one
-- these carry the decisions across without rewriting them.

ALTER TABLE warehouse.mapping_review
    ADD COLUMN IF NOT EXISTS source_code TEXT;

UPDATE warehouse.mapping_review r
SET source_code = rs.source_code
FROM warehouse.ranking_source rs
WHERE rs.ranking_source_id = r.ranking_source_id
  AND r.source_code IS NULL;

ALTER TABLE warehouse.mapping_review
    ALTER COLUMN source_code SET NOT NULL;

ALTER TABLE warehouse.mapping_review
    ALTER COLUMN ranking_source_id DROP NOT NULL;

ALTER TABLE warehouse.mapping_review
    DROP CONSTRAINT IF EXISTS uq_mapping_review_entity;

ALTER TABLE warehouse.mapping_review
    DROP CONSTRAINT IF EXISTS uq_mapping_review_source_entity;

ALTER TABLE warehouse.mapping_review
    ADD CONSTRAINT uq_mapping_review_source_entity
    UNIQUE (source_code, source_entity_id);

ALTER TABLE warehouse.mapping_review
    DROP CONSTRAINT IF EXISTS fk_mapping_review_entity_source;

ALTER TABLE warehouse.mapping_review
    ADD CONSTRAINT fk_mapping_review_entity_source
    FOREIGN KEY (source_code) REFERENCES warehouse.entity_source(source_code);

DROP INDEX IF EXISTS warehouse.idx_mapping_review_source;

CREATE INDEX IF NOT EXISTS idx_mapping_review_source
    ON warehouse.mapping_review(source_code, source_entity_id);

CREATE INDEX IF NOT EXISTS idx_mapping_review_decided_at
    ON warehouse.mapping_review(decided_at DESC);

-- ---------------------------------------------------------
-- One place to read resolved mappings from
-- ---------------------------------------------------------
--
-- The review queue is not derived from mapping_review. It is derived from the
-- mappings the resolver produced, filtered to the fuzzy methods.
--
-- Every source now writes warehouse.source_university_mapping, keyed by
-- source_code (admission pages moved there from warehouse.source_mapping on
-- 2026-09-14; see docs/migrations/ADMISSION_SCHEMA_CONVERGENCE.md, phase 7).
-- The legacy table is still unioned in, but only for an entity the unified
-- table does not hold, so a migrated mapping is never offered for review twice
-- and a stale legacy row cannot contradict the live one.
--
-- metadata is passed through untouched. The review screen reads
-- token_overlap, country_mismatch, suspicious_merge and candidate_count_hint
-- from it -- all written by EntityResolver -- plus raw_row.name and
-- raw_row.location, which each source's own writer has to supply.
CREATE OR REPLACE VIEW warehouse.v_entity_mapping AS
SELECT
    m.source_code,
    m.source_entity_id,
    m.canonical_university_id,
    m.match_method,
    m.confidence_score,
    m.is_active,
    m.metadata
FROM warehouse.source_university_mapping m
UNION ALL
SELECT
    sm.source_name AS source_code,
    sm.source_entity_id,
    sm.canonical_university_id,
    sm.match_method,
    sm.confidence_score,
    sm.is_active,
    sm.metadata
FROM warehouse.source_mapping sm
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.source_university_mapping u
    WHERE u.source_code = sm.source_name
      AND u.source_entity_id = sm.source_entity_id
);
