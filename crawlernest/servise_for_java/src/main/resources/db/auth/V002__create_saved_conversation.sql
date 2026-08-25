-- CrawlerNest Agent Conversation Storage
-- Run once against the warehouse schema.
-- The application also applies this idempotently via AuthSchemaInitializer.
--
-- Scope: this table holds a transcript the user chose to keep. It is written
-- only by ConversationService, only for the session-authenticated user, and it
-- is read by nothing in the ranking or analytics pipeline. No pipeline table is
-- touched from this path.
--
-- The Python agent process has no database connection at all; transcripts reach
-- this table only by the browser POSTing them to the Spring Boot API, which is
-- what keeps the agent out of the write path entirely.

CREATE TABLE IF NOT EXISTS warehouse.saved_conversation (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES warehouse.app_user(id),
    session_id  VARCHAR(64)  NOT NULL,
    title       VARCHAR(200) NOT NULL,
    turns_json  JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    -- One row per session per user, so re-saving a chat the user has continued
    -- updates that transcript instead of leaving a trail of partial copies.
    -- The user_id in the key means two users can hold the same session_id
    -- without colliding.
    CONSTRAINT saved_conversation_user_session_key UNIQUE (user_id, session_id)
);

-- The list endpoint is always "this user's conversations, newest activity first".
CREATE INDEX IF NOT EXISTS saved_conversation_user_updated_idx
    ON warehouse.saved_conversation (user_id, updated_at DESC);
