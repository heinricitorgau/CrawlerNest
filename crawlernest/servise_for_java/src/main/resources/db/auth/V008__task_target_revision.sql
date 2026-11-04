-- =========================================================
-- desk.task, desk.target_entity, desk.sprint: a revision counter for optimistic locking
-- =========================================================
--
-- PATCH /tasks/{id}, /targets/{id} and /sprints/{id} accept expectedRevision and are
-- applied only if the row is still at that revision (409 otherwise), so a tab
-- holding a stale copy cannot overwrite a newer edit.
--
-- Unlike desk.user_profile (V007, which the one service that writes it bumps in
-- SQL), these rows also change without passing through their service:
--   * deleting a sprint or a target clears desk.task.sprint_id / target_entity_id
--     (ON DELETE SET NULL in V003);
--   * crawlernest/scripts/merge_duplicate_canonicals.py repoints
--     desk.target_entity.canonical_university_id.
-- A trigger counts those too. Do not also bump revision in service SQL: it would
-- count twice. A sprint's revision is its own row only (title, goal, dates):
-- adding, ticking or removing one of its tasks does not change it.
--
-- Rows start at 1. Run by AuthSchemaInitializer after V007 on every start; every
-- statement is idempotent. The function body is single-quoted, not dollar-quoted,
-- because ResourceDatabasePopulator splits on ';' and honours only quotes.

ALTER TABLE desk.task ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1);
ALTER TABLE desk.target_entity ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1);
ALTER TABLE desk.sprint ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1 CHECK (revision >= 1);

CREATE OR REPLACE FUNCTION desk.bump_revision() RETURNS trigger LANGUAGE plpgsql AS
'BEGIN NEW.revision := OLD.revision + 1; RETURN NEW; END';

CREATE OR REPLACE TRIGGER task_bump_revision
    BEFORE UPDATE ON desk.task FOR EACH ROW EXECUTE FUNCTION desk.bump_revision();
CREATE OR REPLACE TRIGGER target_entity_bump_revision
    BEFORE UPDATE ON desk.target_entity FOR EACH ROW EXECUTE FUNCTION desk.bump_revision();
CREATE OR REPLACE TRIGGER sprint_bump_revision
    BEFORE UPDATE ON desk.sprint FOR EACH ROW EXECUTE FUNCTION desk.bump_revision();
