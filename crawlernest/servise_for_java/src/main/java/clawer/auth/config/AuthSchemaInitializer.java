package clawer.auth.config;

import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Objects;

@Component
public class AuthSchemaInitializer {

    /**
     * The scripts after app_user, in order: the desk schema (docs/architecture/DESK_SCHEMA_AND_API.md)
     * the password reset tokens (V006) and the profile revision (V007) and the task/target/sprint revisions (V008) and the token generation (V009). Read
     * from the files, not mirrored here. Each must be safe to run on every start.
     */
    static final List<String> SCRIPTS = List.of(
            "db/auth/V003__create_desk_schema.sql",
            "db/auth/V004__tassel_tool_allow_list.sql",
            "db/auth/V005__essay_word_limit.sql",
            "db/auth/V006__password_reset_token.sql",
            "db/auth/V007__user_profile_revision.sql",
            "db/auth/V008__task_target_revision.sql",
            "db/auth/V009__token_version.sql");

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
        // Agent chat transcripts the user chose to keep. Mirrors
        // db/auth/V002__create_saved_conversation.sql; that file is documentation
        // (no Flyway in this project) and this is what actually runs.
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS warehouse.saved_conversation (
                    id          BIGSERIAL    PRIMARY KEY,
                    user_id     BIGINT       NOT NULL REFERENCES warehouse.app_user(id),
                    session_id  VARCHAR(64)  NOT NULL,
                    title       VARCHAR(200) NOT NULL,
                    turns_json  JSONB        NOT NULL,
                    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
                    CONSTRAINT saved_conversation_user_session_key UNIQUE (user_id, session_id)
                )
                """);
        jdbcTemplate.execute("""
                CREATE INDEX IF NOT EXISTS saved_conversation_user_updated_idx
                    ON warehouse.saved_conversation (user_id, updated_at DESC)
                """);
        createDeskTables();
    }

    /** Needs warehouse.app_user, so it runs after the statements above. Idempotent. */
    void createDeskTables() {
        ResourceDatabasePopulator populator = new ResourceDatabasePopulator();
        SCRIPTS.forEach(script -> populator.addScript(new ClassPathResource(script)));
        populator.execute(Objects.requireNonNull(jdbcTemplate.getDataSource()));
    }
}
