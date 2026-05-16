-- CrawlerNest Minimal Identity Layer — Phase 2
-- Run once against the warehouse schema.
-- The application also applies this idempotently via AuthSchemaInitializer.

CREATE TABLE IF NOT EXISTS warehouse.app_user (
    id            BIGSERIAL    PRIMARY KEY,
    email         VARCHAR(320) UNIQUE NOT NULL,
    password_hash VARCHAR(72)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS app_user_email_idx ON warehouse.app_user (email);
