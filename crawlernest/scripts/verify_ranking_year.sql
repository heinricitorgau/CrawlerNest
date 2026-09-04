-- Post-ingest verification for one ranking year.
--
-- Read-only. Answers the question a re-crawl leaves open: did every universe
-- land, did it land *this* run, and what did entity resolution do with the rows
-- it could not place cleanly.
--
--     PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer -P pager=off \
--         -v ranking_year=2026 -v source_code=QS \
--         -f crawlernest/scripts/verify_ranking_year.sql
--
-- The universe *inventory* here is what the database holds. It cannot know what
-- the crawler was asked for -- that lives in qs_universe_registry.py -- so a
-- universe that never ran shows up as an absent row, not as a failure. Run
-- verify_ranking_year.py for the registry side of that comparison.

\if :{?ranking_year}
\else
\set ranking_year 2026
\endif
\if :{?source_code}
\else
\set source_code 'QS'
\endif

\echo
\echo ==== 1. universe inventory and freshness ====
-- One row per universe actually present. run_ids should be 1: a universe
-- carrying rows from two runs means the newer run only partially overwrote the
-- older one, and the leftovers are stale.
SELECT rr.universe_type || ':' || rr.universe_key        AS universe,
       count(*)                                          AS rows,
       count(DISTINCT rr.canonical_university_id)        AS universities,
       count(DISTINCT rr.run_id)                         AS run_ids,
       min(rr.rank_position)                             AS best_rank,
       max(rr.rank_position)                             AS worst_rank,
       max(rr.updated_at)                                AS last_update
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs USING (ranking_source_id)
WHERE rs.source_code = :'source_code'
  AND rr.ranking_year = :ranking_year
GROUP BY 1
ORDER BY 1;

\echo
\echo ==== 2. rows the newest run did not touch ====
-- Empty is the pass. Anything here survived from an earlier ingest of the same
-- year and is now mixed in with fresh rows.
WITH newest AS (
    SELECT rr.universe_type, rr.universe_key, max(rr.updated_at) AS latest
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs USING (ranking_source_id)
    WHERE rs.source_code = :'source_code' AND rr.ranking_year = :ranking_year
    GROUP BY 1, 2
)
SELECT rr.universe_type || ':' || rr.universe_key AS universe,
       count(*)                                   AS stale_rows,
       max(rr.updated_at)                         AS newest_stale_row,
       n.latest                                   AS universe_latest
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs USING (ranking_source_id)
JOIN newest n ON n.universe_type = rr.universe_type AND n.universe_key = rr.universe_key
WHERE rs.source_code = :'source_code'
  AND rr.ranking_year = :ranking_year
  AND rr.updated_at < n.latest - INTERVAL '1 hour'
GROUP BY 1, n.latest
ORDER BY 2 DESC;

\echo
\echo ==== 3. column sanity ====
-- score is legitimately sparse (QS publishes none below the scored band), so it
-- is reported rather than asserted. A non-zero null_canonical or null_rank is a
-- writer bug.
SELECT count(*)                                                   AS total,
       count(*) FILTER (WHERE rr.canonical_university_id IS NULL) AS null_canonical,
       count(*) FILTER (WHERE rr.rank_position IS NULL)           AS null_rank,
       count(*) FILTER (WHERE rr.source_url IS NULL)              AS null_source_url,
       count(*) FILTER (WHERE rr.source_mapping_id IS NULL)       AS null_source_mapping,
       count(*) FILTER (WHERE rr.score IS NULL)                   AS null_score
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs USING (ranking_source_id)
WHERE rs.source_code = :'source_code' AND rr.ranking_year = :ranking_year;

\echo
\echo ==== 4. source entities: resolved vs dropped ====
-- Every row the crawler produced either became a ranking_record or was written
-- to missing_entity_log, so the two together reconstruct the source list and
-- pct_resolved says how much of each universe survived entity resolution.
--
-- missing_entity_log is append-only and carries no batch id, only created_at:
-- ingest the same universe twice and its misses are logged twice, which halves
-- pct_resolved without anything having changed.
--
-- The cut therefore comes from ranking_record, and needs no time window at all.
-- MultiSourceRankingPipeline.ingest_records upserts the ranking records first
-- and calls log_missing_entities afterwards, so a miss belonging to the newest
-- ingest is one logged *at or after* that universe's newest row was written.
-- Everything older belongs to an earlier ingest.
--
-- An ingest that resolved everything logs nothing, and that reads correctly
-- here as zero. A log-anchored "newest miss" would instead reach back to the
-- previous ingest and report its misses as current -- wrong, and wrong in the
-- flattering direction, which is the worse way to be wrong.
WITH loaded AS (
    SELECT rr.ranking_type, count(*) AS n, max(rr.updated_at) AS ingested_at
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs USING (ranking_source_id)
    WHERE rs.source_code = :'source_code' AND rr.ranking_year = :ranking_year
    GROUP BY 1
), missed AS (
    SELECT m.ranking_type, count(*) AS n
    FROM analytics.missing_entity_log m
    JOIN loaded l ON l.ranking_type = m.ranking_type
    WHERE m.source_code = :'source_code'
      AND m.ranking_year = :ranking_year
      AND m.created_at >= l.ingested_at
    GROUP BY 1
)
SELECT coalesce(l.ranking_type, m.ranking_type) AS universe,
       coalesce(l.n, 0)                         AS loaded,
       coalesce(m.n, 0)                         AS unresolved,
       round(100.0 * coalesce(l.n, 0)
             / nullif(coalesce(l.n, 0) + coalesce(m.n, 0), 0), 1) AS pct_resolved
FROM loaded l
FULL JOIN missed m ON l.ranking_type = m.ranking_type
ORDER BY pct_resolved ASC NULLS FIRST;

\echo
\echo ==== 5. canonical collisions (silent row loss) ====
-- uq_ranking_record_universe is unique on
-- (canonical, source, year, ranking_type, universe), so when two source
-- entities resolve to one canonical university only one of them can hold a row
-- in any universe they share. The other is overwritten without an error.
SELECT cu.display_name                                                AS canonical,
       count(*)                                                       AS source_entities,
       round(min(m.confidence_score), 4)                              AS lowest_confidence,
       string_agg(m.source_entity_id, ' | ' ORDER BY m.source_entity_id) AS entities
FROM warehouse.source_university_mapping m
JOIN warehouse.ranking_source rs USING (ranking_source_id)
JOIN warehouse.canonical_university cu USING (canonical_university_id)
WHERE rs.source_code = :'source_code' AND m.is_active
GROUP BY cu.canonical_university_id, cu.display_name
HAVING count(*) > 1
ORDER BY 2 DESC, 1
LIMIT 25;

\echo
\echo ==== 5b. collision totals ====
WITH d AS (
    SELECT m.canonical_university_id, count(*) AS c
    FROM warehouse.source_university_mapping m
    JOIN warehouse.ranking_source rs USING (ranking_source_id)
    WHERE rs.source_code = :'source_code' AND m.is_active
    GROUP BY 1 HAVING count(*) > 1
)
SELECT count(*)          AS canonicals_with_collisions,
       sum(c)            AS source_entities_involved,
       sum(c) - count(*) AS entities_that_cannot_hold_a_row
FROM d;

\echo
\echo ==== 6. entity-resolution review queue ====
-- Same population as mapping_review_queue.sql, counted rather than listed. The
-- fuzzy_review band still resolves to a canonical id (resolver.py: resolved_id
-- is set at >= fuzzy_review, the method is only downgraded at < fuzzy_accept),
-- so these rows are already credited in ranking_record while they wait for a
-- decision.
SELECT coalesce(m.source_code, 'ALL')  AS source_code,
       coalesce(m.match_method, 'all') AS match_method,
       count(*)                        AS pending
FROM warehouse.v_entity_mapping m
LEFT JOIN warehouse.mapping_review r
       ON r.source_code = m.source_code AND r.source_entity_id = m.source_entity_id
WHERE m.is_active
  AND m.match_method IN ('fuzzy', 'fuzzy_review')
  AND r.mapping_review_id IS NULL
GROUP BY ROLLUP (m.source_code, m.match_method)
ORDER BY 1 NULLS LAST, 2 NULLS LAST;

\echo
\echo ==== 6b. pending reviews by the ingest that first saw them ====
-- What this re-crawl added to the backlog, as opposed to what was already in it.
SELECT date(m.first_seen_at) AS first_seen,
       m.match_method,
       count(*)              AS pending
FROM warehouse.source_university_mapping m
JOIN warehouse.ranking_source rs USING (ranking_source_id)
LEFT JOIN warehouse.mapping_review r
       ON r.source_code = rs.source_code AND r.source_entity_id = m.source_entity_id
WHERE rs.source_code = :'source_code'
  AND m.is_active
  AND m.match_method IN ('fuzzy', 'fuzzy_review')
  AND r.mapping_review_id IS NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

\echo
\echo ==== 7. warehouse vs analytics parity ====
-- Per universe: rows in the warehouse against rows in the latest aggregation
-- run that carry a rank for this source. They should match.
WITH wh AS (
    SELECT rr.universe_type, rr.universe_key, count(*) AS n
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs USING (ranking_source_id)
    WHERE rs.source_code = :'source_code' AND rr.ranking_year = :ranking_year
    GROUP BY 1, 2
), an AS (
    SELECT universe_type, universe_key,
           count(*) FILTER (WHERE source_ranks_json ->> :'source_code' IS NOT NULL) AS n_source,
           count(*) AS n_all
    FROM analytics.v_aggregated_rankings_latest
    WHERE ranking_year = :ranking_year
    GROUP BY 1, 2
)
SELECT coalesce(wh.universe_type, an.universe_type) || ':'
     || coalesce(wh.universe_key, an.universe_key)  AS universe,
       coalesce(wh.n, 0)                            AS warehouse_rows,
       coalesce(an.n_source, 0)                     AS analytics_rows_with_source,
       coalesce(an.n_all, 0)                        AS analytics_rows_total,
       coalesce(wh.n, 0) - coalesce(an.n_source, 0) AS drift
FROM wh
FULL JOIN an ON an.universe_type = wh.universe_type AND an.universe_key = wh.universe_key
ORDER BY abs(coalesce(wh.n, 0) - coalesce(an.n_source, 0)) DESC, 1;

\echo
\echo ==== 7b. superseded aggregation runs still holding rows ====
-- v_aggregated_rankings_latest hides these; anything reading
-- analytics.aggregated_rankings directly double-counts them.
WITH latest AS (
    SELECT ranking_year, universe_type, universe_key, max(aggregation_run_id) AS keep
    FROM analytics.aggregated_rankings
    GROUP BY 1, 2, 3
)
SELECT ar.ranking_year,
       ar.universe_type || ':' || ar.universe_key AS universe,
       ar.aggregation_run_id                      AS superseded_run,
       r.run_label,
       count(*)                                   AS orphan_rows
FROM analytics.aggregated_rankings ar
JOIN latest l ON l.ranking_year = ar.ranking_year
             AND l.universe_type = ar.universe_type
             AND l.universe_key = ar.universe_key
LEFT JOIN analytics.aggregation_runs r ON r.aggregation_run_id = ar.aggregation_run_id
WHERE ar.aggregation_run_id <> l.keep
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 5 DESC;

\echo
\echo ==== 8. repeated rank positions ====
-- QS publishes ties, so a small count is expected. A rank repeated many times
-- over is more likely one canonical university collecting several source rows.
SELECT rr.universe_type || ':' || rr.universe_key AS universe,
       rr.rank_position,
       count(*)                                   AS rows
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs USING (ranking_source_id)
WHERE rs.source_code = :'source_code' AND rr.ranking_year = :ranking_year
GROUP BY 1, 2
HAVING count(*) > 1
ORDER BY 3 DESC, 1, 2
LIMIT 20;
