-- =========================================================
-- Human review of fuzzy entity-resolution matches
-- =========================================================
--
-- A reviewer's decision deliberately does NOT live on
-- warehouse.source_university_mapping. That table is pipeline-owned and its
-- upsert overwrites canonical_university_id, match_method, confidence_score
-- and metadata on every ingest, so a decision stored there would survive
-- exactly until the next run-the-rankings -- silently, with no error.
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

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.mapping_review (
    mapping_review_id BIGSERIAL PRIMARY KEY,

    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_entity_id TEXT NOT NULL,

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
    CONSTRAINT uq_mapping_review_entity
        UNIQUE (ranking_source_id, source_entity_id),

    -- A rejection points at nothing; anything else must name a target.
    CONSTRAINT ck_mapping_review_target CHECK (
        (decision = 'rejected' AND decided_canonical_university_id IS NULL)
        OR (decision <> 'rejected' AND decided_canonical_university_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_mapping_review_source
    ON warehouse.mapping_review(ranking_source_id, source_entity_id);

CREATE INDEX IF NOT EXISTS idx_mapping_review_decided_at
    ON warehouse.mapping_review(decided_at DESC);
