-- Minimal legacy warehouse rows for the analytics-bridge smoke test in CI.
--
-- The bridge reads warehouse.rankings joined to warehouse.universities and does
-- everything downstream itself: it seeds ranking_source and canonical_university,
-- fills warehouse.ranking_record, and writes analytics.aggregated_rankings. So the
-- only thing CI has to supply is these two tables, and none of it needs network
-- access -- which is what makes the smoke runnable there at all.
--
-- Six universities, not the full 1,503: enough for the rerun-idempotency and
-- non-empty assertions the smoke makes, and small enough to read when it fails.
-- One row carries a rank band (601-610) because the tail of the QS table is
-- published that way and the bridge has to handle rank_start/rank_end.

INSERT INTO warehouse.universities (school_slug, display_name, canonical_name, city_name)
VALUES
    ('ci-mit',      'Massachusetts Institute of Technology (MIT)', 'Massachusetts Institute of Technology', 'Cambridge'),
    ('ci-imperial', 'Imperial College London',                     'Imperial College London',              'London'),
    ('ci-oxford',   'University of Oxford',                        'University of Oxford',                 'Oxford'),
    ('ci-ntu',      'National Taiwan University (NTU)',            'National Taiwan University',           'Taipei City'),
    ('ci-ncku',     'National Cheng Kung University (NCKU)',       'National Cheng Kung University',       'Tainan City'),
    ('ci-example',  'CrawlerNest Example Institute',               'CrawlerNest Example Institute',        'Hsinchu')
ON CONFLICT (school_slug) DO NOTHING;

INSERT INTO warehouse.rankings (
    university_id, ranking_source, ranking_type, ranking_year, rank_start, rank_end, score, metrics_json
)
SELECT
    u.university_id,
    'QS',
    'world',
    2026,
    v.rank_start,
    v.rank_end,
    v.score,
    v.metrics
FROM (
    VALUES
        ('ci-mit',      1,   1,   100.0, '{"Academic Reputation": "100", "Overall Score": "100"}'::jsonb),
        ('ci-imperial', 2,   2,   98.5,  '{"Academic Reputation": "98.5", "Overall Score": "98.5"}'::jsonb),
        ('ci-oxford',   5,   5,   96.9,  '{"Academic Reputation": "100", "Overall Score": "96.9"}'::jsonb),
        ('ci-ntu',      68,  68,  67.4,  '{"Academic Reputation": "77.9", "Overall Score": "67.4"}'::jsonb),
        ('ci-ncku',     220, 220, 42.9,  '{"Academic Reputation": "40.6", "Overall Score": "42.9"}'::jsonb),
        -- QS publishes the tail as a band and withholds the overall score.
        ('ci-example',  601, 610, NULL,  '{"Academic Reputation": "12.4", "Overall Score": "n/a"}'::jsonb)
) AS v(school_slug, rank_start, rank_end, score, metrics)
JOIN warehouse.universities u ON u.school_slug = v.school_slug
WHERE NOT EXISTS (
    SELECT 1 FROM warehouse.rankings r
    WHERE r.university_id = u.university_id
      AND r.ranking_source = 'QS'
      AND r.ranking_year = 2026
      AND r.ranking_type = 'world'
);
