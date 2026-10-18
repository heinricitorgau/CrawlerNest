-- Two users, so every ownership assertion has another account's rows to not return.
-- Two universities: one active, one merged into it.
DELETE FROM warehouse.app_user WHERE id IN (990401, 990402);
DELETE FROM warehouse.canonical_university WHERE canonical_university_id IN (990401, 990402, 990403);

INSERT INTO warehouse.app_user (id, email, password_hash) VALUES
    (990401, 'desk-api-owner@integration.test', 'not-a-real-hash'),
    (990402, 'desk-api-other@integration.test', 'not-a-real-hash');

INSERT INTO warehouse.canonical_university
    (canonical_university_id, canonical_slug, display_name, display_name_normalized, status) VALUES
    (990401, 'desk-test-active-university', 'Desk Test University', 'desk test university', 'active'),
    (990402, 'desk-test-merged-university', 'Desk Test Univ (old record)', 'desk test univ old record', 'merged'),
    (990403, 'desk-test-acronym-institute', 'Desk Test Institute of Technology (DTIT)', 'desk test institute technology', 'active');
