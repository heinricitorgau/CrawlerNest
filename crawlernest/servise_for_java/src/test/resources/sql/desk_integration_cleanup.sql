-- desk.* cascades from app_user.
DELETE FROM warehouse.app_user WHERE id IN (990401, 990402);
DELETE FROM warehouse.canonical_university WHERE canonical_university_id IN (990401, 990402);
