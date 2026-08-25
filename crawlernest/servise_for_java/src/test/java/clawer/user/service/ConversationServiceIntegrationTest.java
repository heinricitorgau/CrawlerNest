package clawer.user.service;

import clawer.user.dto.SavedConversationDetail;
import clawer.user.dto.SavedConversationSummary;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Exercises the conversation write path against a real PostgreSQL instance.
 *
 * <p>Two things only a real database can settle: that the upsert really is keyed
 * on (user_id, session_id), and that the ownership filters exclude another
 * account's rows rather than merely intending to.
 */
@SpringBootTest
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/saved_conversation_integration_setup.sql",
                        "classpath:sql/saved_conversation_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = "classpath:sql/saved_conversation_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class ConversationServiceIntegrationTest {

    private static final long OWNER = 990201L;
    private static final long OTHER_USER = 990202L;

    @Autowired
    private ConversationService service;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private final ObjectMapper objectMapper = new ObjectMapper();

    private JsonNode turns(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private JsonNode twoTurns() {
        return turns("""
                [
                  {"role": "user", "content": "How is the aggregated rank computed?"},
                  {"role": "assistant", "content": "It combines the sources that published a rank."}
                ]
                """);
    }

    @Test
    void savesAndReadsBackTheTranscript() {
        long id = service.save(OWNER, "session-1", "Ranking questions", twoTurns());

        SavedConversationDetail detail =
                service.findDetailByIdAndUserId(id, OWNER).orElseThrow();

        assertEquals("session-1", detail.getSessionId());
        assertEquals("Ranking questions", detail.getTitle());
        assertEquals(2, ((JsonNode) detail.getTurnsJson()).size());
        assertEquals(
                "How is the aggregated rank computed?",
                ((JsonNode) detail.getTurnsJson()).get(0).get("content").asText());
    }

    @Test
    void savingTheSameSessionAgainUpdatesTheRowRatherThanAddingOne() {
        long first = service.save(OWNER, "session-1", "First title", twoTurns());

        JsonNode longer = turns("""
                [
                  {"role": "user", "content": "How is the aggregated rank computed?"},
                  {"role": "assistant", "content": "It combines the sources that published a rank."},
                  {"role": "user", "content": "And which sources are those?"}
                ]
                """);
        long second = service.save(OWNER, "session-1", "Second title", longer);

        // Same row: a user who keeps chatting and saves again wants the current
        // state of the conversation, not a second partial copy of it.
        assertEquals(first, second);
        assertEquals(1, service.findSummariesByUserId(OWNER).size());

        SavedConversationDetail detail = service.findDetailByIdAndUserId(first, OWNER).orElseThrow();
        assertEquals("Second title", detail.getTitle());
        assertEquals(3, ((JsonNode) detail.getTurnsJson()).size());
    }

    @Test
    void updatingATranscriptMovesUpdatedAtButNotCreatedAt() {
        long id = service.save(OWNER, "session-1", "First", twoTurns());
        SavedConversationDetail before = service.findDetailByIdAndUserId(id, OWNER).orElseThrow();

        service.save(OWNER, "session-1", "Second", twoTurns());
        SavedConversationDetail after = service.findDetailByIdAndUserId(id, OWNER).orElseThrow();

        assertEquals(before.getCreatedAt(), after.getCreatedAt());
        assertNotEquals(before.getUpdatedAt(), after.getUpdatedAt());
    }

    @Test
    void twoUsersCanHoldTheSameSessionIdWithoutColliding() {
        long mine = service.save(OWNER, "shared-session-id", "Mine", twoTurns());
        long theirs = service.save(OTHER_USER, "shared-session-id", "Theirs", twoTurns());

        // The unique key is (user_id, session_id), so a session id the browser
        // happened to reuse across accounts must not overwrite anyone.
        assertNotEquals(mine, theirs);
        assertEquals(1, service.findSummariesByUserId(OWNER).size());
        assertEquals(1, service.findSummariesByUserId(OTHER_USER).size());
    }

    @Test
    void listReturnsOnlyTheCallersConversations() {
        service.save(OWNER, "mine-1", "Mine one", twoTurns());
        service.save(OWNER, "mine-2", "Mine two", twoTurns());
        service.save(OTHER_USER, "theirs-1", "Theirs", twoTurns());

        List<SavedConversationSummary> mine = service.findSummariesByUserId(OWNER);

        assertEquals(2, mine.size());
        assertTrue(mine.stream().noneMatch(s -> "Theirs".equals(s.getTitle())));
    }

    @Test
    void listIsOrderedByMostRecentActivity() {
        long older = service.save(OWNER, "older", "Older", twoTurns());
        service.save(OWNER, "newer", "Newer", twoTurns());
        // Touching the older conversation should float it back to the top.
        service.save(OWNER, "older", "Older, continued", twoTurns());

        List<SavedConversationSummary> summaries = service.findSummariesByUserId(OWNER);

        assertEquals(older, summaries.get(0).getId());
        assertEquals("Older, continued", summaries.get(0).getTitle());
    }

    @Test
    void summaryCarriesTurnCountAndTheOpeningUserMessage() {
        service.save(OWNER, "session-1", "Ranking questions", twoTurns());

        SavedConversationSummary summary = service.findSummariesByUserId(OWNER).get(0);

        assertEquals(2, summary.getTurnCount());
        assertEquals("How is the aggregated rank computed?", summary.getPreview());
    }

    @Test
    void aTranscriptWithNoUserTurnHasNoPreviewRatherThanFailing() {
        service.save(OWNER, "session-1", "Assistant only",
                turns("[{\"role\": \"assistant\", \"content\": \"Nobody asked me anything.\"}]"));

        SavedConversationSummary summary = service.findSummariesByUserId(OWNER).get(0);

        assertEquals(1, summary.getTurnCount());
        assertNull(summary.getPreview());
    }

    @Test
    void anotherUsersConversationIsNotReadable() {
        long theirs = service.save(OTHER_USER, "theirs-1", "Theirs", twoTurns());

        Optional<SavedConversationDetail> asOwner = service.findDetailByIdAndUserId(theirs, OWNER);

        assertTrue(asOwner.isEmpty());
    }

    @Test
    void anotherUsersConversationIsNotDeletable() {
        long theirs = service.save(OTHER_USER, "theirs-1", "Theirs", twoTurns());

        assertFalse(service.deleteByIdAndUserId(theirs, OWNER));
        // Still there for its actual owner.
        assertTrue(service.findDetailByIdAndUserId(theirs, OTHER_USER).isPresent());
    }

    @Test
    void deleteRemovesTheCallersOwnConversation() {
        long id = service.save(OWNER, "session-1", "Mine", twoTurns());

        assertTrue(service.deleteByIdAndUserId(id, OWNER));
        assertTrue(service.findDetailByIdAndUserId(id, OWNER).isEmpty());
    }

    // ─── Title derivation ─────────────────────────────────────────────────────

    @Test
    void blankTitleIsDerivedFromTheFirstUserTurn() {
        long id = service.save(OWNER, "session-1", "  ", twoTurns());

        assertEquals(
                "How is the aggregated rank computed?",
                service.findDetailByIdAndUserId(id, OWNER).orElseThrow().getTitle());
    }

    @Test
    void derivedTitleCollapsesWhitespaceSoItStaysOneLine() {
        long id = service.save(OWNER, "session-1", null,
                turns("[{\"role\": \"user\", \"content\": \"line one\\n\\nline two\"}]"));

        assertEquals("line one line two",
                service.findDetailByIdAndUserId(id, OWNER).orElseThrow().getTitle());
    }

    @Test
    void aTranscriptWithNoUserTurnFallsBackToAPlaceholderTitle() {
        long id = service.save(OWNER, "session-1", null,
                turns("[{\"role\": \"assistant\", \"content\": \"Nobody asked me anything.\"}]"));

        assertEquals("Untitled conversation",
                service.findDetailByIdAndUserId(id, OWNER).orElseThrow().getTitle());
    }

    @Test
    void anOverlongTitleIsTruncatedToFitTheColumn() {
        String longTitle = "t".repeat(ConversationService.MAX_TITLE_LENGTH + 50);

        long id = service.save(OWNER, "session-1", longTitle, twoTurns());

        // Without this the insert would fail on the VARCHAR(200) bound instead.
        assertEquals(ConversationService.MAX_TITLE_LENGTH,
                service.findDetailByIdAndUserId(id, OWNER).orElseThrow().getTitle().length());
    }

    // ─── Size ceiling ─────────────────────────────────────────────────────────

    @Test
    void anOversizedTranscriptIsRejectedBeforeItReachesTheDatabase() {
        String big = "x".repeat(ConversationService.MAX_TURNS_BYTES + 1);
        JsonNode oversized = turns(
                "[{\"role\": \"user\", \"content\": \"" + big + "\"}]");

        assertThrows(IllegalArgumentException.class,
                () -> service.save(OWNER, "session-1", "Too big", oversized));

        Integer rows = jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.saved_conversation WHERE user_id = ?",
                Integer.class, OWNER);
        assertEquals(0, rows);
    }

    // ─── Isolation from the pipeline ──────────────────────────────────────────

    @Test
    void savingAConversationTouchesNoPipelineTable() {
        Integer rankingBefore = jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.ranking_record", Integer.class);
        Integer canonicalBefore = jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.canonical_university", Integer.class);
        Integer admissionBefore = jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.admission_record", Integer.class);

        service.save(OWNER, "session-1", "Ranking questions", twoTurns());

        // The read-only contract is the reason this path exists in Java at all;
        // asserting it here means a future edit that reaches for a fact table
        // fails a test rather than a review.
        assertEquals(rankingBefore, jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.ranking_record", Integer.class));
        assertEquals(canonicalBefore, jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.canonical_university", Integer.class));
        assertEquals(admissionBefore, jdbcTemplate.queryForObject(
                "SELECT COUNT(*)::INTEGER FROM warehouse.admission_record", Integer.class));
    }
}
