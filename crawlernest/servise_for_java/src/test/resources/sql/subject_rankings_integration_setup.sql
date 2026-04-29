CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS warehouse.ranking_source (
    ranking_source_id SMALLSERIAL PRIMARY KEY,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_version TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS warehouse.source_university_mapping (
    source_mapping_id BIGSERIAL PRIMARY KEY,
    ranking_source_id SMALLINT NOT NULL
        REFERENCES warehouse.ranking_source(ranking_source_id),
    source_entity_id TEXT NOT NULL,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    match_method TEXT NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE (ranking_source_id, source_entity_id)
);

CREATE TABLE IF NOT EXISTS warehouse.ranking_subject (
    subject_id SMALLSERIAL PRIMARY KEY,
    subject_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    subject_group TEXT,
    source_aliases JSONB,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
    UNIQUE (
        canonical_university_id,
        ranking_source_id,
        subject_id,
        ranking_year
    )
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
