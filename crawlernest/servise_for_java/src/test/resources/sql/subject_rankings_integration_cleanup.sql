DELETE FROM warehouse.subject_ranking_record
WHERE ranking_year = 2099
   OR source_entity_id LIKE 'qs:subject:%:2099:%';

DELETE FROM warehouse.ranking_subject
WHERE subject_key IN ('computer-science', 'electrical-engineering')
  AND NOT EXISTS (
      SELECT 1
      FROM warehouse.subject_ranking_record srr
      WHERE srr.subject_id = warehouse.ranking_subject.subject_id
  );
