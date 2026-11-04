-- =========================================================
-- desk.user_profile: a revision counter for optimistic locking
-- =========================================================
--
-- PUT /profile replaces the whole row, so two tabs that read the profile and
-- both save it lose the first tab's edit without either noticing. Each write
-- now increments revision; a PUT that sends expectedRevision is applied only if
-- the row is still at that revision, and is refused with 409 otherwise.
--
-- 0 means "never saved": GET returns revision 0 when there is no row, and the
-- first save turns it into 1. Existing rows start at 1 -- they have been saved.
--
-- Run by AuthSchemaInitializer after V006 on every start; IF NOT EXISTS makes it
-- idempotent, and the DEFAULT fills existing rows only when the column is added.

ALTER TABLE desk.user_profile ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1
    CHECK (revision >= 1);
