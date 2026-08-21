-- Emit the review queue as a decisions file ready to edit.
--
-- Each pending mapping becomes a comment describing the pair, then a line
-- holding the id and a `?` where the decision goes, so filling the backlog in
-- is replacing one character per entry rather than copying ids by hand.
--
--     # [THE] 0.8209  KMITL – King Mongkut's Institute of Technology (Thailand)
--     #      -> King Mongkuts Institute of Technology (KMITL)  [canonical 1254 | Thailand]
--     589118, confirmed
--
-- Only the `?` is meant to change. Use `confirmed` when the canonical named in
-- the comment is the right university, `rejected` when no canonical applies,
-- and `remapped, <id>` when a different one does -- a remap needs the id of
-- the university to move to, so `remapped` alone is refused.
--
--     PGPASSWORD=test psql -h localhost -p 5432 -U test -d clawer \
--         -At -f crawlernest/scripts/mapping_review_skeleton.sql > decisions.csv
--
-- Then edit decisions.csv, and apply it with:
--
--     ./.venv/bin/python crawlernest/scripts/apply_mapping_reviews.py decisions.csv \
--         --decided-by you@example.com          # previews
--         --decided-by you@example.com --commit # writes
--
-- Lines still lacking a decision are skipped by the tool's parser, so a
-- half-finished file applies the part that is finished.

SELECT string_agg(line, E'\n' ORDER BY confidence_score, source_code, source_entity_id)
FROM (
    SELECT
        m.confidence_score,
        rs.source_code,
        m.source_entity_id,
        -- The decision goes in the `?` slot on the id line. Nothing in the
        -- comments is meant to be edited, so the canonical id is written as
        -- `canonical 1254` rather than `id=1254,`: the latter reads like a
        -- field, and an edit anchored on it lands two lines above the slot
        -- that the parser actually reads.
        format(
            E'# [%s] %s  %s (%s)\n#      -> %s  [canonical %s | %s]\n%s, ?',
            rs.source_code,
            to_char(m.confidence_score, 'FM0.0000'),
            COALESCE(
                m.metadata #>> '{raw_row,name}',
                m.metadata ->> 'normalized_name',
                m.source_entity_id
            ),
            COALESCE(m.metadata #>> '{raw_row,location}', 'unknown'),
            cu.display_name,
            m.canonical_university_id,
            COALESCE(c.country_name, 'unknown'),
            m.source_entity_id
        ) AS line
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
) rows;
