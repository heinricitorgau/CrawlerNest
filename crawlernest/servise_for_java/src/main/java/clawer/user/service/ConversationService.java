package clawer.user.service;

import clawer.user.dto.SavedConversationDetail;
import clawer.user.dto.SavedConversationSummary;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.util.List;
import java.util.Optional;

/**
 * Stores agent chat transcripts the user chose to keep.
 *
 * <p>Writes go to warehouse.saved_conversation and nowhere else. No ranking,
 * admission, or analytics table is reachable from this class, and every
 * statement here is scoped by user_id so one account cannot read or delete
 * another's transcript.
 *
 * <p>The Python agent process holds no database connection of its own; a
 * transcript reaches this table only because the browser posted it here. That
 * is what keeps the agent out of the write path rather than merely discouraged
 * from it.
 */
@Service
public class ConversationService {

    /**
     * Longest transcript accepted in one save.
     *
     * <p>Turns arrive from the browser, so without a bound a single request
     * decides how much JSONB the database stores. The agent API caps a request
     * body at 128 KiB for the same reason; a saved transcript is allowed to be
     * larger than one exchange but not unbounded.
     */
    public static final int MAX_TURNS = 200;

    /** Serialized size ceiling for turns_json, applied to UTF-8 bytes. */
    public static final int MAX_TURNS_BYTES = 256 * 1024;

    public static final int MAX_TITLE_LENGTH = 200;
    public static final int MAX_SESSION_ID_LENGTH = 64;

    private static final String UNTITLED = "Untitled conversation";

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public ConversationService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * Stores a transcript, replacing whatever this user last saved for the same
     * session.
     *
     * <p>Upsert rather than insert because a user who keeps chatting and saves
     * again means "keep the current state of this conversation", not "keep a
     * second partial copy of it".
     *
     * @return the row id, whether it was created or updated
     */
    public long save(long userId, String sessionId, String title, JsonNode turnsJson) {
        String turns = serializeTurns(turnsJson);
        String resolvedTitle = resolveTitle(title, turnsJson);

        Long id = jdbcTemplate.queryForObject(
                """
                INSERT INTO warehouse.saved_conversation
                    (user_id, session_id, title, turns_json)
                VALUES (?, ?, ?, ?::jsonb)
                ON CONFLICT ON CONSTRAINT saved_conversation_user_session_key DO UPDATE
                SET title = EXCLUDED.title,
                    turns_json = EXCLUDED.turns_json,
                    updated_at = now()
                RETURNING id
                """,
                Long.class,
                userId, sessionId, resolvedTitle, turns);
        return id != null ? id : -1L;
    }

    public List<SavedConversationSummary> findSummariesByUserId(long userId) {
        return jdbcTemplate.query("""
                SELECT
                    id,
                    session_id,
                    title,
                    created_at,
                    updated_at,
                    -- turns_json is validated as an array on write, but it is a
                    -- JSONB column: one row of another shape would otherwise make
                    -- jsonb_array_length throw and take the whole list with it.
                    CASE WHEN jsonb_typeof(turns_json) = 'array'
                         THEN jsonb_array_length(turns_json)
                         ELSE 0
                    END AS turn_count,
                    (
                        SELECT left(turn->>'content', 200)
                        FROM jsonb_array_elements(
                                 CASE WHEN jsonb_typeof(turns_json) = 'array'
                                      THEN turns_json
                                      ELSE '[]'::jsonb
                             END
                             ) AS turn
                        WHERE turn->>'role' = 'user'
                          AND NULLIF(TRIM(turn->>'content'), '') IS NOT NULL
                        LIMIT 1
                    ) AS preview
                FROM warehouse.saved_conversation
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (rs, rowNum) -> {
                    SavedConversationSummary s = new SavedConversationSummary();
                    s.setId(rs.getLong("id"));
                    s.setSessionId(rs.getString("session_id"));
                    s.setTitle(rs.getString("title"));
                    s.setTurnCount(rs.getInt("turn_count"));
                    s.setPreview(rs.getString("preview"));
                    s.setCreatedAt(toInstant(rs.getTimestamp("created_at")));
                    s.setUpdatedAt(toInstant(rs.getTimestamp("updated_at")));
                    return s;
                },
                userId);
    }

    public Optional<SavedConversationDetail> findDetailByIdAndUserId(long id, long userId) {
        List<SavedConversationDetail> results = jdbcTemplate.query("""
                SELECT id, session_id, title, turns_json, created_at, updated_at
                FROM warehouse.saved_conversation
                WHERE id = ? AND user_id = ?
                """,
                (rs, rowNum) -> {
                    SavedConversationDetail d = new SavedConversationDetail();
                    d.setId(rs.getLong("id"));
                    d.setSessionId(rs.getString("session_id"));
                    d.setTitle(rs.getString("title"));
                    d.setTurnsJson(parseJson(rs.getString("turns_json")));
                    d.setCreatedAt(toInstant(rs.getTimestamp("created_at")));
                    d.setUpdatedAt(toInstant(rs.getTimestamp("updated_at")));
                    return d;
                },
                id, userId);
        return results.isEmpty() ? Optional.empty() : Optional.of(results.get(0));
    }

    public boolean deleteByIdAndUserId(long id, long userId) {
        int rows = jdbcTemplate.update(
                "DELETE FROM warehouse.saved_conversation WHERE id = ? AND user_id = ?",
                id, userId);
        return rows > 0;
    }

    /**
     * Rejects a turn list that is the wrong shape or too large, and returns the
     * reason so the caller can answer 400 with it.
     *
     * @return null when the turns are acceptable
     */
    public static String validateTurns(JsonNode turnsJson) {
        if (turnsJson == null || turnsJson.isNull()) {
            return "Turns are required.";
        }
        if (!turnsJson.isArray()) {
            return "Turns must be an array.";
        }
        if (turnsJson.isEmpty()) {
            return "Turns must not be empty.";
        }
        if (turnsJson.size() > MAX_TURNS) {
            return "Conversation is too long. Limit is " + MAX_TURNS + " turns.";
        }
        for (JsonNode turn : turnsJson) {
            if (!turn.isObject()) {
                return "Each turn must be an object.";
            }
            JsonNode role = turn.get("role");
            if (role == null || !role.isTextual() || role.asText().isBlank()) {
                return "Each turn needs a role.";
            }
            JsonNode content = turn.get("content");
            if (content == null || !content.isTextual()) {
                return "Each turn needs string content.";
            }
        }
        return null;
    }

    private String serializeTurns(JsonNode turnsJson) {
        String turns;
        try {
            turns = objectMapper.writeValueAsString(turnsJson);
        } catch (Exception e) {
            throw new IllegalArgumentException("Turns could not be serialized", e);
        }
        int bytes = turns.getBytes(StandardCharsets.UTF_8).length;
        if (bytes > MAX_TURNS_BYTES) {
            throw new IllegalArgumentException(
                    "Conversation is too large. Limit is " + MAX_TURNS_BYTES + " bytes.");
        }
        return turns;
    }

    /**
     * Uses the supplied title, or names the transcript after its opening
     * question when the caller left it blank.
     */
    private String resolveTitle(String title, JsonNode turnsJson) {
        if (title != null && !title.isBlank()) {
            return truncate(title.trim(), MAX_TITLE_LENGTH);
        }
        if (turnsJson != null && turnsJson.isArray()) {
            for (JsonNode turn : turnsJson) {
                if (!turn.isObject()) {
                    continue;
                }
                JsonNode role = turn.get("role");
                JsonNode content = turn.get("content");
                if (role != null && "user".equals(role.asText())
                        && content != null && content.isTextual()
                        && !content.asText().isBlank()) {
                    // Collapse whitespace so a pasted multi-line prompt does not
                    // become a title with newlines in it.
                    String derived = content.asText().trim().replaceAll("\\s+", " ");
                    return truncate(derived, 80);
                }
            }
        }
        return UNTITLED;
    }

    private static String truncate(String value, int max) {
        return value.length() <= max ? value : value.substring(0, max);
    }

    private static java.time.Instant toInstant(Timestamp ts) {
        return ts != null ? ts.toInstant() : null;
    }

    private Object parseJson(String json) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            return json;
        }
    }
}
