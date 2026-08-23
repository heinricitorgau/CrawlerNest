DELETE FROM warehouse.admission_record
WHERE canonical_university_id = 990102
   OR normalized_university_name IN ('MIT');

DELETE FROM warehouse.ranking_record
WHERE canonical_university_id IN (990102, 990103);

DELETE FROM warehouse.university_alias
WHERE canonical_university_id = 990102;

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id IN (990102, 990103);
