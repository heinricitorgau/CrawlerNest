-- =========================================================
-- CrawlerNest Subject Ranking Schema
-- =========================================================
-- Phase 1 scope:
-- - QS Subject Rankings only
-- - MVP subjects: computer-science, electrical-engineering
-- - Does not feed global aggregation, recommendation, compare, or agent paths
--
-- Requires:
-- - warehouse.canonical_university
-- - warehouse.ranking_source
-- - warehouse.source_university_mapping

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS warehouse.ranking_subject (
    subject_id SMALLSERIAL PRIMARY KEY,
    subject_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    subject_group TEXT,
    source_aliases JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO warehouse.ranking_subject (
    subject_key,
    display_name,
    subject_group,
    source_aliases
) VALUES
    (
        'computer-science',
        'Computer Science',
        'Engineering and Technology',
        '{"QS": ["Computer Science and Information Systems"]}'::jsonb
    ),
    (
        'electrical-engineering',
        'Electrical Engineering',
        'Engineering and Technology',
        '{"QS": ["Engineering - Electrical and Electronic"]}'::jsonb
    ),
    -- Ingested since this list was last touched, and seeded into the running
    -- warehouse by run-qs-subject rather than by this file -- so a database
    -- bootstrapped from scratch came up with two subjects while the one the
    -- tests run against had three. SubjectRankingApiIntegrationTest already
    -- asserts hasItems("business-management", ...), and passed only because it
    -- runs against that warehouse.
    (
        'business-management',
        'Business & Management',
        'Business and Economics',
        '{"QS": ["Business & Management Studies"]}'::jsonb
    )
ON CONFLICT (subject_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    subject_group = EXCLUDED.subject_group,
    source_aliases = EXCLUDED.source_aliases,
    is_active = TRUE;

CREATE TABLE IF NOT EXISTS warehouse.subject_ranking_record (
    subject_ranking_record_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_mapping_id BIGINT
        REFERENCES warehouse.source_university_mapping(source_mapping_id),
    subject_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_subject(subject_id),
    ranking_year INTEGER NOT NULL,
    rank_position INTEGER,
    rank_display TEXT,
    score NUMERIC(8,4),
    score_scale NUMERIC(8,4),
    source_entity_id TEXT,
    source_url TEXT,
    source_version TEXT,
    raw_payload JSONB,
    metadata JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id TEXT,
    CHECK (rank_position IS NULL OR rank_position > 0),
    CHECK (score IS NULL OR score >= 0),
    UNIQUE (
        canonical_university_id,
        ranking_source_id,
        subject_id,
        ranking_year
    )
);

CREATE INDEX IF NOT EXISTS idx_subject_ranking_lookup
    ON warehouse.subject_ranking_record (
        ranking_source_id,
        subject_id,
        ranking_year,
        rank_position
    );

CREATE INDEX IF NOT EXISTS idx_subject_ranking_canonical
    ON warehouse.subject_ranking_record (
        canonical_university_id,
        ranking_year
    );

CREATE INDEX IF NOT EXISTS idx_subject_ranking_subject_year
    ON warehouse.subject_ranking_record (
        subject_id,
        ranking_year,
        rank_position
    );

CREATE OR REPLACE VIEW analytics.v_subject_rankings_latest AS
SELECT
    srr.subject_ranking_record_id,
    cu.canonical_university_id,
    cu.canonical_slug,
    cu.display_name AS university_name,
    c.country_code,
    c.country_name,
    rs.source_code,
    rs.source_name,
    subj.subject_key,
    subj.display_name AS subject_name,
    srr.ranking_year,
    srr.rank_position,
    srr.rank_display,
    srr.score,
    srr.score_scale,
    srr.source_url,
    srr.metadata,
    srr.updated_at
FROM warehouse.subject_ranking_record srr
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = srr.canonical_university_id
JOIN warehouse.ranking_source rs
  ON rs.ranking_source_id = srr.ranking_source_id
JOIN warehouse.ranking_subject subj
  ON subj.subject_id = srr.subject_id
LEFT JOIN warehouse.countries c
  ON c.country_id = cu.country_id;
