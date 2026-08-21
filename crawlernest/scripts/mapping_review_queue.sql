-- Fuzzy entity-resolution matches still awaiting a decision.
--
-- Live rows only: a rejected pair is retired via is_active on the next ingest,
-- and a decided pair is excluded by the LEFT JOIN, so re-running this after a
-- batch shows only what is left.
--
-- Lowest confidence first, because those are both the likeliest to be wrong and
-- the quickest to judge.
--
--     PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer -P pager=off \
--         -f crawlernest/scripts/mapping_review_queue.sql
--
-- To open it in a spreadsheet, ask psql for CSV. Both result sets land in the
-- file, the queue first and the counts after it:
--
--     PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer --csv \
--         -f crawlernest/scripts/mapping_review_queue.sql > reports/review_queue.csv
--
-- To fill the backlog in rather than read it, mapping_review_skeleton.sql
-- writes the same queue as a decisions file for apply_mapping_reviews.py.

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


-- How much is left, per source and method, with subtotals. Worth having
-- separately from the listing: after a batch the useful question is how many
-- remain, and counting rows by eye stops working somewhere around twenty.
SELECT
    COALESCE(rs.source_code, 'ALL')      AS source_code,
    COALESCE(m.match_method, 'all')      AS match_method,
    count(*)                             AS pending
FROM warehouse.source_university_mapping m
JOIN warehouse.ranking_source rs
    ON rs.ranking_source_id = m.ranking_source_id
LEFT JOIN warehouse.mapping_review r
    ON r.ranking_source_id = m.ranking_source_id
   AND r.source_entity_id = m.source_entity_id
WHERE m.is_active
  AND m.match_method IN ('fuzzy', 'fuzzy_review')
  AND r.mapping_review_id IS NULL
GROUP BY ROLLUP (rs.source_code, m.match_method)
ORDER BY rs.source_code NULLS LAST, m.match_method NULLS LAST;
