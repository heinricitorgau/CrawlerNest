DELETE FROM warehouse.subject_ranking_record
WHERE ranking_year = 2099;

INSERT INTO warehouse.ranking_source (
    source_code,
    source_name,
    source_version,
    metadata
) VALUES (
    'QS',
    'QS World University Rankings',
    'subject-api-test',
    '{}'::jsonb
)
ON CONFLICT (source_code) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_version = EXCLUDED.source_version,
    is_active = TRUE;

INSERT INTO warehouse.ranking_subject (
    subject_key,
    display_name,
    subject_group,
    source_aliases
) VALUES
    (
        'computer-science',
        'Computer Science',
        'Engineering and Technology',
        '{"QS": ["Computer Science and Information Systems"]}'::jsonb
    ),
    (
        'electrical-engineering',
        'Electrical Engineering',
        'Engineering and Technology',
        '{"QS": ["Engineering - Electrical and Electronic"]}'::jsonb
    )
ON CONFLICT (subject_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    subject_group = EXCLUDED.subject_group,
    source_aliases = EXCLUDED.source_aliases,
    is_active = TRUE;

INSERT INTO warehouse.subject_ranking_record (
    canonical_university_id,
    ranking_source_id,
    subject_id,
    ranking_year,
    rank_position,
    rank_display,
    score,
    score_scale,
    source_entity_id,
    source_url,
    raw_payload,
    metadata,
    run_id
)
SELECT
    row_data.canonical_university_id,
    rs.ranking_source_id,
    subj.subject_id,
    2099,
    row_data.rank_position,
    row_data.rank_display,
    row_data.score,
    100.0,
    row_data.source_entity_id,
    row_data.source_url,
    '{}'::jsonb,
    '{"source":"subject-api-test"}'::jsonb,
    'subject-api-test'
FROM (
    VALUES
        (
            990002::BIGINT,
            'computer-science',
            1,
            '1',
            96.7::NUMERIC,
            'qs:subject:computer-science:2099:massachusetts-institute-of-technology',
            'https://example.test/qs/cs/mit'
        ),
        (
            990003::BIGINT,
            'computer-science',
            2,
            '2',
            92.2::NUMERIC,
            'qs:subject:computer-science:2099:delft-university-of-technology',
            'https://example.test/qs/cs/delft'
        ),
        (
            990028::BIGINT,
            'computer-science',
            3,
            '3',
            91.1::NUMERIC,
            'qs:subject:computer-science:2099:university-of-oxford',
            'https://example.test/qs/cs/oxford'
        ),
        (
            990002::BIGINT,
            'electrical-engineering',
            4,
            '4',
            94.8::NUMERIC,
            'qs:subject:electrical-engineering:2099:massachusetts-institute-of-technology',
            'https://example.test/qs/ee/mit'
        )
) AS row_data(
    canonical_university_id,
    subject_key,
    rank_position,
    rank_display,
    score,
    source_entity_id,
    source_url
)
JOIN warehouse.ranking_source rs
  ON rs.source_code = 'QS'
JOIN warehouse.ranking_subject subj
  ON subj.subject_key = row_data.subject_key
ON CONFLICT (
    canonical_university_id,
    ranking_source_id,
    subject_id,
    ranking_year
) DO UPDATE SET
    rank_position = EXCLUDED.rank_position,
    rank_display = EXCLUDED.rank_display,
    score = EXCLUDED.score,
    score_scale = EXCLUDED.score_scale,
    source_entity_id = EXCLUDED.source_entity_id,
    source_url = EXCLUDED.source_url,
    raw_payload = EXCLUDED.raw_payload,
    metadata = EXCLUDED.metadata,
    run_id = EXCLUDED.run_id,
    updated_at = CURRENT_TIMESTAMP;
