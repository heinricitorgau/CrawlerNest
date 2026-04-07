-- =========================================================
-- University recommendation feature generation queries
-- =========================================================

-- 1. Semantic Similarity Search (Vector Match)
-- Find Top 5 universities similar to "Massachusetts Institute of Technology (MIT)"
-- based on their pre-calculated name/description embeddings.
WITH target_embedding AS (
    SELECT embedding 
    FROM warehouse.universities 
    WHERE school_slug = 'massachusetts-institute-of-technology'
)
SELECT 
    u.display_name,
    u.school_slug,
    u.embedding <=> (SELECT embedding FROM target_embedding) AS distance -- Cosine distance
FROM warehouse.universities u
WHERE u.school_slug != 'massachusetts-institute-of-technology'
ORDER BY distance ASC
LIMIT 5;

-- 2. Weighted Feature Extraction (JSONB)
-- Extract specific metrics needed for a multi-weighted recommendation score.
-- We normalize the "Academic Reputation" and "International Students" score.
SELECT 
    u.display_name,
    c.country_name,
    r.ranking_year,
    (r.metrics_json->>'Academic Reputation')::float AS academic_score,
    (r.metrics_json->>'International Students')::float AS international_diversity_score,
    r.score AS total_ranking_score
FROM warehouse.universities u
JOIN warehouse.countries c ON u.country_id = c.country_id
JOIN warehouse.rankings r ON u.university_id = r.university_id
WHERE r.ranking_source = 'QS' AND r.ranking_year = 2025
  AND (r.metrics_json->>'Academic Reputation') IS NOT NULL
ORDER BY academic_score DESC;

-- 3. Hard Constraint Filtering (Admission Requirements)
-- Recommend universities that fit a student's profile: IELTS >= 7.0 and GPA >= 3.5.
SELECT 
    u.display_name,
    ar.ielts_min,
    ar.gpa_min,
    r.rank_start AS global_rank
FROM warehouse.universities u
JOIN warehouse.admission_requirements ar ON u.university_id = ar.university_id
JOIN warehouse.rankings r ON u.university_id = r.university_id
WHERE ar.ielts_min <= 7.0 
  AND ar.gpa_min <= 3.5
  AND r.ranking_year = 2025
ORDER BY r.rank_start ASC;

-- 4. Cross-Ranking Aggregation (Composite Feature)
-- Average ranking across QS and THE (if available) for a more robust feature vector.
SELECT 
    u.display_name,
    AVG(r.score) AS aggregated_score,
    MIN(r.rank_start) AS best_rank
FROM warehouse.universities u
JOIN warehouse.rankings r ON u.university_id = r.university_id
GROUP BY u.university_id, u.display_name
HAVING COUNT(DISTINCT r.ranking_source) >= 2; -- Ensure school is ranked by at least 2 sources

-- 5. Full-Text Search within Raw Content
-- Find universities mentioning "Quantum Computing" in their raw scraped text.
SELECT 
    u.display_name,
    s.source_url
FROM warehouse.universities u
JOIN warehouse.rankings r ON u.university_id = r.university_id
JOIN staging.raw_source_records s ON r.raw_id = s.raw_id
WHERE to_tsvector('english', s.raw_text) @@ to_tsquery('english', 'Quantum & Computing');
