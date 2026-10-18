-- =========================================================
-- warehouse.password_reset_token: one-time "forgot password" links
-- =========================================================
--
-- Only the SHA-256 of the token is stored. The token itself exists in the link
-- that was delivered and nowhere else, so a copy of this table cannot be used to
-- reset anyone's password.
--
-- A token is good once, for crawlernest.password-reset.ttl (30 minutes by
-- default). Requesting a new one, or using one, ends every other open token for
-- that user. Run by AuthSchemaInitializer on every start; idempotent.

CREATE TABLE IF NOT EXISTS warehouse.password_reset_token (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    token_hash  CHAR(64)    NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    CONSTRAINT password_reset_token_expires_after_created CHECK (expires_at > created_at)
);

-- The per-account limit counts a user's recent requests.
CREATE INDEX IF NOT EXISTS password_reset_token_user_created_idx
    ON warehouse.password_reset_token (user_id, created_at DESC);
