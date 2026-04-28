-- =========================================================
-- CrawlerNest Rule-Based Recommendation Schema
-- =========================================================
-- Depends on:
-- - warehouse.canonical_university
-- - warehouse.universities
-- - warehouse.admission_requirements
-- - analytics.v_aggregated_rankings_latest

CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS warehouse.canonical_university_link (
    canonical_university_link_id BIGSERIAL PRIMARY KEY,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    university_id INTEGER NOT NULL
        REFERENCES warehouse.universities(university_id),
    link_method TEXT NOT NULL DEFAULT 'manual',
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
    is_primary BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (university_id),
    UNIQUE (canonical_university_id, university_id)
);

CREATE TABLE IF NOT EXISTS analytics.recommendation_runs (
    recommendation_run_id BIGSERIAL PRIMARY KEY,
    run_label TEXT,
    recommendation_method_version TEXT NOT NULL,
    ranking_year INTEGER,
    preferred_ranking_source TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    input_candidate_count INTEGER NOT NULL DEFAULT 0,
    output_result_count INTEGER NOT NULL DEFAULT 0,
    query_json JSONB,
    config_json JSONB,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS analytics.recommendation_results (
    recommendation_result_id BIGSERIAL PRIMARY KEY,
    recommendation_run_id BIGINT NOT NULL
        REFERENCES analytics.recommendation_runs(recommendation_run_id),
    result_position INTEGER NOT NULL,
    canonical_university_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    university_name TEXT NOT NULL,
    country TEXT,
    aggregated_rank INTEGER,
    ielts_min NUMERIC(4,2),
    matching_score NUMERIC(10,4) NOT NULL,
    explanation TEXT NOT NULL,
    score_breakdown_json JSONB NOT NULL,
    aggregation_method_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (recommendation_run_id, result_position)
);

CREATE TABLE IF NOT EXISTS warehouse.admission_records_preview (
    id BIGSERIAL PRIMARY KEY,
    university_name TEXT NOT NULL,
    normalized_university_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    country TEXT NULL,
    ielts_requirement DOUBLE PRECISION NULL,
    toefl_requirement INTEGER NULL,
    extracted_at TIMESTAMPTZ NOT NULL,
    canonical_university_id BIGINT NULL,
    entity_resolution_status TEXT NOT NULL,
    raw_payload JSONB NULL,
    UNIQUE (normalized_university_name, source_url)
);

DROP VIEW IF EXISTS analytics.v_recommendation_candidates_latest;

CREATE VIEW analytics.v_recommendation_candidates_latest AS
WITH admission_summary AS (
    SELECT
        cul.canonical_university_id,
        MIN(ar.gpa_min) FILTER (WHERE ar.gpa_min IS NOT NULL) AS gpa_min,
        MIN(ar.ielts_min) FILTER (WHERE ar.ielts_min IS NOT NULL) AS ielts_min,
        MIN(ar.toefl_min) FILTER (WHERE ar.toefl_min IS NOT NULL) AS toefl_min,
        COUNT(*) FILTER (WHERE ar.ielts_min IS NOT NULL) AS ielts_observation_count,
        COUNT(*) AS admission_record_count,
        (
            ARRAY_AGG(ar.application_deadline_text ORDER BY ar.requirement_id DESC)
            FILTER (WHERE ar.application_deadline_text IS NOT NULL AND ar.application_deadline_text <> '')
        )[1] AS application_deadline_text
    FROM warehouse.canonical_university_link cul
    JOIN warehouse.admission_requirements ar
      ON ar.university_id = cul.university_id
    GROUP BY cul.canonical_university_id
),
admission_preview_summary AS (
    SELECT
        canonical_university_id,
        (
            ARRAY_AGG(raw_payload ORDER BY id DESC)
            FILTER (WHERE raw_payload IS NOT NULL)
        )[1] AS latest_raw_payload
    FROM warehouse.admission_records_preview
    WHERE canonical_university_id IS NOT NULL
    GROUP BY canonical_university_id
),
source_rank_summary AS (
    SELECT
        rr.canonical_university_id,
        rr.ranking_year,
        jsonb_object_agg(rs.source_code, rr.rank_position ORDER BY rs.source_code)
            FILTER (WHERE rr.rank_position IS NOT NULL) AS source_ranks_json,
        jsonb_object_agg(rs.source_code, rr.score ORDER BY rs.source_code)
            FILTER (WHERE rr.score IS NOT NULL) AS source_scores_json
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs
      ON rs.ranking_source_id = rr.ranking_source_id
    WHERE rr.ranking_type = 'world'
      AND rr.universe_type = 'global'
      AND rr.universe_key = 'global'
    GROUP BY rr.canonical_university_id, rr.ranking_year
)
SELECT
    ar.canonical_university_id,
    cu.display_name AS university_name,
    c.country_name AS country,
    ar.ranking_year,
    ar.display_rank AS aggregated_rank,
    ar.composite_score,
    ar.coverage_ratio,
    ar.aggregation_method_version,
    COALESCE(srs.source_ranks_json, '{}'::jsonb) AS source_ranks_json,
    COALESCE(srs.source_scores_json, '{}'::jsonb) AS source_scores_json,
    ads.gpa_min,
    ads.ielts_min,
    ads.toefl_min,
    NULLIF(COALESCE(aps.latest_raw_payload->>'duolingo_requirement', aps.latest_raw_payload->>'duolingo'), '')::numeric AS duolingo_min,
    COALESCE(aps.latest_raw_payload->>'deadline', ads.application_deadline_text) AS application_deadline_text,
    COALESCE(aps.latest_raw_payload->'deadline_candidates', '[]'::jsonb) AS deadline_candidates_json,
    COALESCE(ads.ielts_observation_count, 0) AS ielts_observation_count,
    COALESCE(ads.admission_record_count, 0) AS admission_record_count
FROM analytics.v_aggregated_rankings_latest ar
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = ar.canonical_university_id
LEFT JOIN warehouse.countries c
  ON c.country_id = cu.country_id
LEFT JOIN admission_summary ads
  ON ads.canonical_university_id = ar.canonical_university_id
LEFT JOIN admission_preview_summary aps
  ON aps.canonical_university_id = ar.canonical_university_id
LEFT JOIN source_rank_summary srs
  ON srs.canonical_university_id = ar.canonical_university_id
 AND srs.ranking_year = ar.ranking_year
WHERE ar.universe_type = 'global'
  AND ar.universe_key = 'global';

CREATE INDEX IF NOT EXISTS idx_canonical_university_link_canonical
    ON warehouse.canonical_university_link(canonical_university_id);

CREATE INDEX IF NOT EXISTS idx_canonical_university_link_university
    ON warehouse.canonical_university_link(university_id);

CREATE INDEX IF NOT EXISTS idx_recommendation_runs_method_year
    ON analytics.recommendation_runs(recommendation_method_version, ranking_year, started_at);

CREATE INDEX IF NOT EXISTS idx_recommendation_results_run_position
    ON analytics.recommendation_results(recommendation_run_id, result_position);

CREATE INDEX IF NOT EXISTS idx_recommendation_results_canonical
    ON analytics.recommendation_results(canonical_university_id, matching_score DESC);
