-- =========================================================
-- desk.model_call: one row per call this API made to the model
-- =========================================================
--
-- The per-user model budget counted in process memory, so a restart gave every user a
-- fresh day and two API instances each allowed the whole day. The day's budget is now
-- counted from this table, which survives restarts and is shared by every instance.
-- The minute's budget stays in memory: it guards bursts, and a restart costing at most
-- one minute's allowance is acceptable.
--
-- A row is written for every request sent to the provider, with what it answered:
--   ok             -- a 2xx reply. prompt_tokens / completion_tokens are the provider's
--                     own "usage" figures when it sent them, NULL when it did not (never 0
--                     standing in for unknown).
--   provider_error -- a non-2xx reply. Counted: the provider did the work of answering.
--   unreachable    -- no reply (connection refused, timeout). Not counted against the
--                     user: an outage should not spend their day.
-- A call made with no signed-in user (none exist today) is stored with user_id NULL.
--
-- The essay, chat messages and replies are never stored here: only that a call happened,
-- which endpoint asked for it, and its size. user_id cascades like the rest of desk.*,
-- and release dumps exclude desk.* (scripts/release_snapshot.py).
--
-- Run by AuthSchemaInitializer after V009 on every start; IF NOT EXISTS makes it idempotent.

CREATE TABLE IF NOT EXISTS desk.model_call (
    id                BIGSERIAL    PRIMARY KEY,
    user_id           BIGINT       REFERENCES warehouse.app_user(id) ON DELETE CASCADE,
    endpoint          VARCHAR(120) NOT NULL,
    model_name        VARCHAR(200),
    outcome           VARCHAR(20)  NOT NULL CHECK (outcome IN ('ok', 'provider_error', 'unreachable')),
    prompt_tokens     INTEGER      CHECK (prompt_tokens >= 0),
    completion_tokens INTEGER      CHECK (completion_tokens >= 0),
    called_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT model_call_tokens_only_when_answered
        CHECK (outcome = 'ok' OR (prompt_tokens IS NULL AND completion_tokens IS NULL))
);

CREATE INDEX IF NOT EXISTS model_call_user_time_idx ON desk.model_call (user_id, called_at);
