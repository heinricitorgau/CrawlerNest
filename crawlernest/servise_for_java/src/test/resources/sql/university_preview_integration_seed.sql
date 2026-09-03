DELETE FROM warehouse.admission_record
WHERE canonical_university_id = 990102
   OR normalized_university_name IN ('MIT');

-- ranking_record has no normalized_university_name; canonical id is the only
-- handle on a seeded row. The seeded warehouse.ranking_source rows are left
-- alone: on a bootstrapped database they are real registry rows, not fixtures.
DELETE FROM warehouse.ranking_record
WHERE canonical_university_id IN (990102, 990103);

DELETE FROM warehouse.university_alias
WHERE canonical_university_id = 990102;

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id IN (990102, 990103);

INSERT INTO warehouse.canonical_university (
    canonical_university_id,
    canonical_slug,
    display_name,
    display_name_normalized,
    status
) VALUES
    (990102, 'massachusetts-institute-of-technology-preview', 'Massachusetts Institute of Technology', 'Massachusetts Institute Of Technology', 'active'),
    (990103, 'university-of-oxford-preview', 'University of Oxford', 'University Of Oxford', 'active')
ON CONFLICT (canonical_university_id) DO UPDATE
SET canonical_slug = EXCLUDED.canonical_slug,
    display_name = EXCLUDED.display_name,
    display_name_normalized = EXCLUDED.display_name_normalized,
    status = EXCLUDED.status,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO warehouse.university_alias (
    canonical_university_id,
    alias_text,
    alias_normalized,
    source_name,
    is_primary,
    is_abbreviation,
    metadata
) VALUES (
    990102,
    'MIT',
    'MIT',
    'manual',
    FALSE,
    TRUE,
    '{"seed_origin":"integration-test"}'::jsonb
)
ON CONFLICT DO NOTHING;

INSERT INTO warehouse.ranking_source (source_code, source_name)
VALUES ('QS', 'QS World University Rankings')
ON CONFLICT (source_code) DO NOTHING;

INSERT INTO warehouse.ranking_record (
    canonical_university_id,
    ranking_source_id,
    ranking_year,
    ranking_type,
    universe_type,
    universe_key,
    rank_position,
    source_url
)
SELECT
    seed.canonical_university_id,
    src.ranking_source_id,
    seed.ranking_year,
    'world',
    'global',
    'global',
    seed.rank_position,
    seed.source_url
FROM (
    VALUES
        (990102::BIGINT, 2026, 1, 'https://example.edu/rankings/mit'),
        (990103::BIGINT, 2026, 2, 'https://example.edu/rankings/oxford')
) AS seed (canonical_university_id, ranking_year, rank_position, source_url)
CROSS JOIN warehouse.ranking_source src
WHERE src.source_code = 'QS';

-- Oxford also appears in a non-world universe, at a *better* rank_position
-- than its world one (2). This is exactly the shape UniversityPreviewApiIntegrationTest
-- .oxfordRankingSummaryIgnoresNonWorldUniverses() exists to catch: an unscoped
-- MIN(rank_position) across both rows would report Oxford's best_rank as 1,
-- crediting it with a rank it never held in the world ranking that this
-- endpoint's field name promises. See ranking_scope.py.
INSERT INTO warehouse.ranking_record (
    canonical_university_id,
    ranking_source_id,
    ranking_year,
    ranking_type,
    universe_type,
    universe_key,
    rank_position,
    source_url
)
SELECT
    990103,
    src.ranking_source_id,
    2026,
    'region:europe',
    'region',
    'europe',
    1,
    'https://example.edu/rankings/oxford-europe'
FROM warehouse.ranking_source src
WHERE src.source_code = 'QS';

-- Two degree levels, and between them every requirement column is NULL for at
-- least one row. That is what a real crawl looks like: an undergraduate page
-- that publishes a GPA bar and no English test, and a postgraduate page that
-- does the opposite. A fixture where every column is populated would let a
-- null-handling regression reach production unnoticed.
--
-- The postgraduate row keeps ielts 7.0 / toefl 100 so that the MIN() the preview
-- endpoint reports is unchanged; the undergraduate row leaves both NULL rather
-- than undercutting them.
INSERT INTO warehouse.admission_record (
    source_entity_id,
    university_name,
    normalized_university_name,
    source_url,
    country,
    degree_level,
    ielts_requirement,
    toefl_requirement,
    duolingo_requirement,
    gpa_requirement,
    application_deadline,
    extracted_at,
    canonical_university_id,
    entity_resolution_status,
    raw_payload
) VALUES
    (
        'example.edu/admissions/mit',
        'MIT',
        'MIT',
        'https://example.edu/admissions/mit',
        'United States',
        'postgraduate',
        7.0,
        100,
        125,
        NULL,
        DATE '2026-01-15',
        '2026-04-14T18:06:49Z',
        990102,
        'resolved_alias_exact',
        '{"source":"integration-test"}'::jsonb
    ),
    (
        'example.edu/admissions/mit',
        'MIT',
        'MIT',
        'https://example.edu/admissions/mit-undergraduate',
        'United States',
        'undergraduate',
        NULL,
        NULL,
        NULL,
        3.7,
        DATE '2026-03-01',
        '2026-04-14T18:06:49Z',
        990102,
        'resolved_alias_exact',
        '{"source":"integration-test"}'::jsonb
    );

