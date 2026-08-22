DELETE FROM warehouse.admission_record
WHERE canonical_university_id = 990102
   OR normalized_university_name IN ('MIT');

DELETE FROM warehouse.ranking_records_preview
WHERE canonical_university_id IN (990102, 990103)
   OR normalized_university_name IN ('MIT', 'Oxford');

DELETE FROM warehouse.university_alias
WHERE canonical_university_id = 990102;

DELETE FROM warehouse.canonical_university
WHERE canonical_university_id IN (990102, 990103);
