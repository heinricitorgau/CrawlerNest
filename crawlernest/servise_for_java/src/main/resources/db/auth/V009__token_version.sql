-- =========================================================
-- warehouse.app_user: a token generation, so a token can be ended before it expires
-- =========================================================
--
-- A signed token carried no state the server could change, so sign-out cleared the
-- cookie and nothing else: a token copied out of a browser, or one held by someone
-- signed in before a password reset, stayed valid for its whole TTL.
--
-- Every token now carries the generation it was issued under (claim "ver"), and the
-- filter accepts it only while app_user.token_version still equals it. "Sign out
-- everywhere" and a password reset increment the column, which ends every token
-- issued before. Tokens issued before this column existed carry no claim and read
-- as generation 0, which is the default, so nobody is signed out by the migration.
--
-- Run by AuthSchemaInitializer after V008 on every start; IF NOT EXISTS makes it
-- idempotent.

ALTER TABLE warehouse.app_user ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0
    CHECK (token_version >= 0);
