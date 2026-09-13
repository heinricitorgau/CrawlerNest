-- Runs before rankings_integration_cleanup.sql: lineage rows reference the fixture
-- universities that script deletes.
DELETE FROM warehouse.institution_lineage
WHERE predecessor_canonical_id BETWEEN 990001 AND 990030
   OR successor_canonical_id BETWEEN 990001 AND 990030;
