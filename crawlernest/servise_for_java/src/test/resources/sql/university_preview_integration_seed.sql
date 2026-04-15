DELETE FROM warehouse.admission_records_preview
WHERE canonical_university_id = 990102
   OR normalized_university_name IN ('MIT');

DELETE FROM warehouse.ranking_records_preview
WHERE canonical_university_id IN (990102, 990103)
   OR normalized_university_name IN ('MIT', 'Oxford');

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

INSERT INTO warehouse.ranking_records_preview (
    university_name,
    normalized_university_name,
    source,
    rank,
    year,
    source_url,
    extracted_at,
    ranking_year,
    universe_type,
    universe_key,
    canonical_university_id,
    entity_resolution_status,
    source_resolution_status
) VALUES
    (
        'MIT',
        'MIT',
        'QS',
        1,
        2026,
        'https://example.edu/rankings/mit',
        '2026-04-14T10:00:00Z',
        2026,
        'global',
        'global',
        990102,
        'resolved',
        'direct_source_only'
    ),
    (
        'Oxford',
        'Oxford',
        'QS',
        2,
        2026,
        'https://example.edu/rankings/oxford',
        '2026-04-14T10:00:00Z',
        2026,
        'global',
        'global',
        990103,
        'resolved',
        'direct_source_only'
    );

INSERT INTO warehouse.admission_records_preview (
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
