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
