-- Fuzzy entity-resolution matches still awaiting a decision.
--
-- Live rows only: a rejected pair is retired via is_active on the next ingest,
-- and a decided pair is excluded by the LEFT JOIN, so re-running this after a
-- batch shows only what is left.
--
-- Lowest confidence first, because those are both the likeliest to be wrong and
-- the quickest to judge.
--
--     PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer \
--         -f crawlernest/scripts/mapping_review_queue.sql
--
-- For a CSV, add -A -F',' --pset=footer=off, or wrap the SELECT in \copy.

SELECT
    m.ranking_source_id,
    rs.source_code,
    m.source_entity_id,
    COALESCE(
        m.metadata #>> '{raw_row,name}',
        m.metadata ->> 'normalized_name',
        m.source_entity_id
    )                                                   AS source_name,
    m.metadata #>> '{raw_row,location}'                 AS source_country,
    m.canonical_university_id,
    cu.display_name                                     AS canonical_name,
    c.country_name                                      AS canonical_country,
    m.match_method,
    m.confidence_score,
    (m.metadata ->> 'token_overlap')::double precision  AS token_overlap,
    (m.metadata ->> 'candidate_count_hint')::int        AS candidates_considered
FROM warehouse.source_university_mapping m
JOIN warehouse.ranking_source rs
    ON rs.ranking_source_id = m.ranking_source_id
JOIN warehouse.canonical_university cu
    ON cu.canonical_university_id = m.canonical_university_id
LEFT JOIN warehouse.countries c
    ON c.country_id = cu.country_id
LEFT JOIN warehouse.mapping_review r
    ON r.ranking_source_id = m.ranking_source_id
   AND r.source_entity_id = m.source_entity_id
WHERE m.is_active
  AND m.match_method IN ('fuzzy', 'fuzzy_review')
  AND r.mapping_review_id IS NULL
ORDER BY m.confidence_score ASC, rs.source_code, m.source_entity_id;
