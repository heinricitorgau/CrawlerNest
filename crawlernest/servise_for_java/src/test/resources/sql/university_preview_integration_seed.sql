DELETE FROM warehouse.admission_record
WHERE canonical_university_id = 990102
   OR normalized_university_name IN ('MIT');

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

-- warehouse.ranking_source is shared with the real database on a developer machine,
-- so the source row is inserted idempotently and referenced by code rather than by a
-- hardcoded id (ranking_source_id is a SMALLSERIAL and differs between databases).
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
) VALUES
    (
        990102,
        (SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = 'QS'),
        2026,
        'world',
        'global',
        'global',
        1,
        'https://example.edu/rankings/mit'
    ),
    (
        990103,
        (SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = 'QS'),
        2026,
        'world',
        'global',
        'global',
        2,
        'https://example.edu/rankings/oxford'
    );

INSERT INTO warehouse.admission_record (
    source_entity_id,
    university_name,
    normalized_university_name,
    source_url,
    country,
    ielts_requirement,
    toefl_requirement,
    extracted_at,
    canonical_university_id,
    entity_resolution_status,
    raw_payload
) VALUES (
    'example.edu/admissions/mit',
    'MIT',
    'MIT',
    'https://example.edu/admissions/mit',
    'United States',
    7.0,
    100,
    '2026-04-14T18:06:49Z',
    990102,
    'resolved_alias_exact',
    '{"source":"integration-test"}'::jsonb
);

