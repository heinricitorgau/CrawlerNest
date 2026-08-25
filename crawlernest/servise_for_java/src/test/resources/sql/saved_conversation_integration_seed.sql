-- Two users, because the ownership assertions only mean something when a second
-- account's rows exist to not be returned.
DELETE FROM warehouse.saved_conversation WHERE user_id IN (990201, 990202);
DELETE FROM warehouse.app_user WHERE id IN (990201, 990202);

INSERT INTO warehouse.app_user (id, email, password_hash)
VALUES
    (990201, 'conversation-owner@integration.test', 'not-a-real-hash'),
    (990202, 'conversation-other@integration.test', 'not-a-real-hash');
