package clawer.auth.config;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * The desk schema as AuthSchemaInitializer leaves it on a real PostgreSQL.
 *
 * <p>No @Sql setup: the tables under test are the ones the initializer created
 * when this context started, which is the thing being checked. On CI that is
 * an empty database, so a startup dependency on a pipeline table would fail
 * every test in the suite, not only these.
 */
@SpringBootTest
class DeskSchemaIntegrationTest {

    private static final long OWNER = 990301L;
    private static final long OTHER_USER = 990302L;

    @Autowired
    private AuthSchemaInitializer initializer;

    @Autowired
    private JdbcTemplate jdbc;

    @BeforeEach
    void seedUsers() {
        deleteUsers();
        jdbc.update("""
                INSERT INTO warehouse.app_user (id, email, password_hash) VALUES
                    (?, 'desk-owner@integration.test', 'not-a-real-hash'),
                    (?, 'desk-other@integration.test', 'not-a-real-hash')
                """, OWNER, OTHER_USER);
    }

    @AfterEach
    void deleteUsers() {
        // Every desk table cascades from app_user, so this is the whole cleanup.
        jdbc.update("DELETE FROM warehouse.app_user WHERE id IN (?, ?)", OWNER, OTHER_USER);
    }

    private long insertTarget(long userId, String name) {
        return jdbc.queryForObject(
                "INSERT INTO desk.target_entity (user_id, custom_name) VALUES (?, ?) RETURNING id",
                Long.class, userId, name);
    }

    private long insertTheme(long userId) {
        return jdbc.queryForObject("""
                INSERT INTO desk.user_theme (user_id, title, summary, evidence, model_name, prompt_version)
                VALUES (?, 'The Builder Who Teaches', 'summary', '[{"kind": "user_note", "refId": "n1"}]', 'm', 'v1')
                RETURNING id
                """, Long.class, userId);
    }

    @Test
    void createsEveryDeskTable() {
        List<String> tables = jdbc.queryForList("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'desk' ORDER BY table_name
                """, String.class);
        assertEquals(List.of("chat_action", "entity_resonance", "essay_review", "model_call", "skill_mastery", "sprint",
                "target_entity", "task", "user_profile", "user_theme"), tables);
    }

    @Test
    void runningTheInitializerAgainChangesNothing() {
        assertDoesNotThrow(initializer::createAuthTables);
    }

    @Test
    void referencesNoPipelineTable() {
        // A foreign key into the pipeline's tables would stop the API starting on
        // a database the pipeline has not bootstrapped. app_user is created by
        // the initializer itself, just before the desk script runs.
        List<String> referenced = jdbc.queryForList("""
                SELECT DISTINCT confrelid::regclass::text FROM pg_constraint
                WHERE contype = 'f' AND connamespace = 'desk'::regnamespace
                  AND confrelid::regclass::text NOT LIKE 'desk.%'
                """, String.class);
        assertEquals(List.of("warehouse.app_user"), referenced);
    }

    @Test
    void aTaskCannotPointAtAnotherUsersTarget() {
        long othersTarget = insertTarget(OTHER_USER, "Someone else's school");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO desk.task (user_id, title, target_entity_id) VALUES (?, 'x', ?)", OWNER, othersTarget));
    }

    @Test
    void resonanceCannotPairOneUsersThemeWithAnotherUsersTarget() {
        long theme = insertTheme(OWNER);
        long othersTarget = insertTarget(OTHER_USER, "Someone else's school");
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("""
                INSERT INTO desk.entity_resonance
                    (user_id, theme_id, target_entity_id, level, rationale, institution_basis, model_name, prompt_version)
                VALUES (?, ?, ?, 3, 'r', 'user_notes', 'm', 'v1')
                """, OWNER, theme, othersTarget));
    }

    @Test
    void masteryIsComputedFromTheCounts() {
        jdbc.update("""
                INSERT INTO desk.skill_mastery (user_id, subject, unit, questions_attempted, questions_correct)
                VALUES (?, 'SAT Math', 'Algebra', 50, 47), (?, 'SAT Math', 'Geometry', 0, 0)
                """, OWNER, OWNER);
        assertEquals("94.0", jdbc.queryForObject(
                "SELECT mastery_pct::text FROM desk.skill_mastery WHERE user_id = ? AND unit = 'Algebra'", String.class, OWNER));
        assertEquals(null, jdbc.queryForObject(
                "SELECT mastery_pct FROM desk.skill_mastery WHERE user_id = ? AND unit = 'Geometry'", Double.class, OWNER));
        // A writer cannot store its own percentage: the column is generated.
        assertThrows(DataAccessException.class, () -> jdbc.update("""
                INSERT INTO desk.skill_mastery (user_id, subject, unit, questions_attempted, questions_correct, mastery_pct)
                VALUES (?, 'SAT Math', 'Data', 10, 5, 99)
                """, OWNER));
    }

    @Test
    void modelOutputCannotBeStoredAsMeasured() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("""
                INSERT INTO desk.user_theme (user_id, title, summary, evidence, model_name, prompt_version, is_estimated)
                VALUES (?, 't', 's', '[{"kind": "user_note"}]', 'm', 'v1', FALSE)
                """, OWNER));
    }

    @Test
    void aThemeNeedsEvidence() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("""
                INSERT INTO desk.user_theme (user_id, title, summary, evidence, model_name, prompt_version)
                VALUES (?, 't', 's', '[]', 'm', 'v1')
                """, OWNER));
    }

    @Test
    void theModelCanOnlyCallAllowListedTools() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update("""
                INSERT INTO desk.chat_action (id, user_id, session_id, turn_index, tool_name, arguments, status, model_name)
                VALUES (gen_random_uuid(), ?, 's', 0, 'delete_account', '{}', 'proposed', 'm')
                """, OWNER));
    }

    @Test
    void anAgentTaskMustNameTheActionThatCreatedIt() {
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
                "INSERT INTO desk.task (user_id, title, created_by) VALUES (?, 'x', 'agent')", OWNER));
    }

    @Test
    void deletingTheUserRemovesTheirDeskRows() {
        String action = jdbc.queryForObject("""
                INSERT INTO desk.chat_action (id, user_id, session_id, turn_index, tool_name, arguments, status, model_name)
                VALUES (gen_random_uuid(), ?, 's', 0, 'create_action_task', '{}', 'applied', 'm') RETURNING id::text
                """, String.class, OWNER);
        jdbc.update("INSERT INTO desk.task (user_id, title, created_by, source_action_id) VALUES (?, 'agent task', 'agent', ?::uuid)",
                OWNER, action);
        insertTheme(OWNER);
        long otherTarget = insertTarget(OTHER_USER, "Kept");

        jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", OWNER);

        assertEquals(0, jdbc.queryForObject("""
                SELECT (SELECT count(*) FROM desk.task WHERE user_id = ?)
                     + (SELECT count(*) FROM desk.chat_action WHERE user_id = ?)
                     + (SELECT count(*) FROM desk.user_theme WHERE user_id = ?)
                """, Long.class, OWNER, OWNER, OWNER));
        assertEquals(1, jdbc.queryForObject(
                "SELECT count(*) FROM desk.target_entity WHERE id = ?", Long.class, otherTarget));
    }
}
