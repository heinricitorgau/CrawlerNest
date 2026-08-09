package clawer.auth.config;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class AuthSchemaInitializer {

    private final JdbcTemplate jdbcTemplate;

    public AuthSchemaInitializer(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void createAuthTables() {
        jdbcTemplate.execute("CREATE SCHEMA IF NOT EXISTS warehouse");
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS warehouse.app_user (
                    id            BIGSERIAL    PRIMARY KEY,
                    email         VARCHAR(320) UNIQUE NOT NULL,
                    password_hash VARCHAR(72)  NOT NULL,
                    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
                    last_login_at TIMESTAMPTZ,
                    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS warehouse.saved_university (
                    id                      BIGSERIAL   PRIMARY KEY,
                    user_id                 BIGINT      NOT NULL REFERENCES warehouse.app_user(id),
                    canonical_university_id BIGINT      NOT NULL,
                    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
                    UNIQUE (user_id, canonical_university_id)
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS warehouse.saved_recommendation (
                    id           BIGSERIAL    PRIMARY KEY,
                    user_id      BIGINT       NOT NULL REFERENCES warehouse.app_user(id),
                    title        VARCHAR(255) NOT NULL,
                    request_json JSONB        NOT NULL,
                    result_json  JSONB        NOT NULL,
                    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
                )
                """);
    }
}
