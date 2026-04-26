-- =========================================
-- CrawlerNest Legacy → Analytics Bridge
-- Purpose:
--   Convert warehouse.rankings (legacy)
--   into analytics-ready pipeline data
-- =========================================

-- =========================
-- 1. Seed ranking_source
-- =========================
INSERT INTO warehouse.ranking_source (
  source_code,
  source_name,
  source_version,
  metadata
)
VALUES (
  'QS',
  'QS World University Rankings',
  '2026',
  '{"seeded_from":"warehouse.rankings"}'::jsonb
)
ON CONFLICT (source_code) DO NOTHING;


-- =========================
-- 2. Seed canonical_university
-- =========================
INSERT INTO warehouse.canonical_university (
  canonical_slug,
  display_name,
  display_name_normalized,
  country_id,
  city_name,
  website_url,
  metadata
)
SELECT
  u.school_slug,
  u.display_name,
  lower(trim(u.display_name)),
  u.country_id,
  u.city_name,
  u.website_url,
  jsonb_build_object(
    'seeded_from', 'warehouse.universities',
    'source_university_id', u.university_id
  )
FROM warehouse.universities u
ON CONFLICT (canonical_slug) DO NOTHING;


-- =========================
-- 3. Bridge rankings → ranking_record
-- =========================
INSERT INTO warehouse.ranking_record (
  canonical_university_id,
  ranking_source_id,
  ranking_year,
  ranking_type,
  universe_type,
  universe_key,
  rank_position,
  score,
  score_scale,
  source_version,
  source_url,
  metadata,
  run_id
)
SELECT
  cu.canonical_university_id,
  rs.ranking_source_id,
  r.ranking_year,
  r.ranking_type,
  'global',
  'global',
  r.rank_start,
  r.score,
  100,
  r.ranking_year::text,
  r.source_url,
  jsonb_build_object(
    'seeded_from', 'warehouse.rankings',
    'legacy_ranking_id', r.ranking_id,
    'legacy_university_id', r.university_id,
    'rank_end', r.rank_end,
    'metrics_json', r.metrics_json
  ),
  'legacy_bridge_2026'
FROM warehouse.rankings r
JOIN warehouse.universities u
  ON u.university_id = r.university_id
JOIN warehouse.canonical_university cu
  ON cu.canonical_slug = u.school_slug
JOIN warehouse.ranking_source rs
  ON rs.source_code = r.ranking_source
WHERE r.ranking_year = 2026
ON CONFLICT (
  canonical_university_id,
  ranking_source_id,
  ranking_year,
  ranking_type,
  universe_type,
  universe_key
)
DO UPDATE SET
  rank_position = EXCLUDED.rank_position,
  score = EXCLUDED.score,
  updated_at = CURRENT_TIMESTAMP;


-- =========================
-- 4. Create aggregation run
-- =========================
WITH new_run AS (
  INSERT INTO analytics.aggregation_runs (
    run_label,
    ranking_year,
    universe_type,
    universe_key,
    aggregation_method_version,
    status,
    started_at,
    finished_at,
    input_record_count,
    output_record_count,
    config_json,
    notes
  )
  SELECT
    'legacy_bridge_2026_qs',
    2026,
    'global',
    'global',
    'legacy_single_source_v1',
    'finished',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP,
    COUNT(*),
    COUNT(*),
    '{"source":"QS","method":"single_source_passthrough"}'::jsonb,
    'Auto bridge from warehouse.rankings'
  FROM warehouse.ranking_record
  WHERE ranking_year = 2026
  RETURNING aggregation_run_id
)

-- =========================
-- 5. Populate aggregated_rankings
-- =========================
INSERT INTO analytics.aggregated_rankings (
  aggregation_run_id,
  canonical_university_id,
  ranking_year,
  universe_type,
  universe_key,
  display_rank,
  composite_score,
  coverage_ratio,
  source_ranks_json,
  source_normalized_scores_json,
  source_weights_used_json,
  aggregation_method_version
)
SELECT
  nr.aggregation_run_id,
  rr.canonical_university_id,
  rr.ranking_year,
  rr.universe_type,
  rr.universe_key,
  rr.rank_position,
  rr.score,
  1.0,
  jsonb_build_object('QS', rr.rank_position),
  jsonb_build_object('QS', rr.score),
  '{"QS":1.0}'::jsonb,
  'legacy_single_source_v1'
FROM warehouse.ranking_record rr
CROSS JOIN new_run nr
WHERE rr.ranking_year = 2026
ON CONFLICT (
  canonical_university_id,
  ranking_year,
  universe_type,
  universe_key,
  aggregation_method_version
)
DO UPDATE SET
  display_rank = EXCLUDED.display_rank,
  composite_score = EXCLUDED.composite_score,
  updated_at = CURRENT_TIMESTAMP;