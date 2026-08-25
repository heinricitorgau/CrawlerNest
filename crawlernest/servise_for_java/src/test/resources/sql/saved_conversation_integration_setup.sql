-- Mirrors the tables AuthSchemaInitializer creates at application startup.
-- CREATE TABLE IF NOT EXISTS means these are no-ops against a bootstrapped
-- database, so the test runs on the real tables; the definitions only
-- materialize on a bare one.
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.app_user (
    id            BIGSERIAL    PRIMARY KEY,
    email         VARCHAR(320) UNIQUE NOT NULL,
    password_hash VARCHAR(72)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS warehouse.saved_conversation (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     BIGINT       NOT NULL REFERENCES warehouse.app_user(id),
    session_id  VARCHAR(64)  NOT NULL,
    title       VARCHAR(200) NOT NULL,
    turns_json  JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT saved_conversation_user_session_key UNIQUE (user_id, session_id)
);
