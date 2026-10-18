package clawer.desk.chat;

import clawer.desk.support.DeskException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * What the user does with Tassel's actions afterwards: confirm or reject a
 * proposal, undo an applied change within {@link #UNDO_WINDOW}, or list a
 * session's actions. Every statement is scoped by the session user.
 */
@Service
public class ChatActionService {

    static final Duration UNDO_WINDOW = Duration.ofHours(24);

    private record Action(UUID id, String tool, String status, JsonNode arguments, JsonNode result, Instant createdAt) {}

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final ObjectMapper objectMapper;
    private final TasselToolExecutor executor;

    public ChatActionService(JdbcTemplate jdbc, TransactionTemplate tx, ObjectMapper objectMapper, TasselToolExecutor executor) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.objectMapper = objectMapper;
        this.executor = executor;
    }

    public List<Map<String, Object>> list(long userId, String sessionId) {
        if (sessionId == null || sessionId.isBlank() || sessionId.length() > 64) {
            throw DeskException.badRequest("sessionId is required.");
        }
        return jdbc.query("""
                SELECT id FROM desk.chat_action WHERE user_id = ? AND session_id = ? ORDER BY turn_index, created_at
                """, (rs, n) -> view(load(userId, (UUID) rs.getObject("id"))), userId, sessionId);
    }

    public Map<String, Object> confirm(long userId, UUID id) {
        Action a = load(userId, id);
        requireProposal(a);
        try {
            JsonNode result = tx.execute(status -> {
                JsonNode applied = executor.applyProposal(userId, a.arguments());
                setStatus(userId, id, "confirmed", applied);
                return applied;
            });
            return view(new Action(a.id(), a.tool(), "confirmed", a.arguments(), result, a.createdAt()));
        } catch (DeskException e) {
            setStatus(userId, id, "failed", objectMapper.createObjectNode().put("error", e.getMessage()));
            throw e;
        }
    }

    public Map<String, Object> reject(long userId, UUID id) {
        Action a = load(userId, id);
        requireProposal(a);
        setStatus(userId, id, "rejected", a.result());
        return view(load(userId, id));
    }

    /** Reverses an applied change. Rows the user has since changed by hand are left alone. */
    public Map<String, Object> undo(long userId, UUID id) {
        Action a = load(userId, id);
        if (!a.status().equals("applied")) {
            throw DeskException.conflict("Only an applied change can be undone; this one is " + a.status() + ".");
        }
        if (a.createdAt().plus(UNDO_WINDOW).isBefore(Instant.now())) {
            throw DeskException.conflict("Changes can be undone for 24 hours; this one is older.");
        }
        tx.executeWithoutResult(status -> {
            switch (a.tool()) {
                case "create_action_task" ->
                        jdbc.update("DELETE FROM desk.task WHERE source_action_id = ? AND user_id = ?", id, userId);
                case "update_target_list" ->
                        jdbc.update("DELETE FROM desk.target_entity WHERE id = ? AND user_id = ? AND created_by = 'agent'",
                                a.result().path("id").asLong(), userId);
                case "generate_narrative_themes" -> {
                    for (JsonNode themeId : a.result().path("ids")) {
                        // A theme the user has since kept is theirs now.
                        jdbc.update("DELETE FROM desk.user_theme WHERE id = ? AND user_id = ? AND status = 'suggested'",
                                themeId.asLong(), userId);
                    }
                }
                default -> throw DeskException.conflict("This change cannot be undone.");
            }
            setStatus(userId, id, "undone", a.result());
        });
        return view(load(userId, id));
    }

    private static void requireProposal(Action a) {
        if (!a.status().equals("proposed")) {
            throw DeskException.conflict("This change is " + a.status() + ", not waiting for confirmation.");
        }
    }

    private void setStatus(long userId, UUID id, String status, JsonNode result) {
        jdbc.update("UPDATE desk.chat_action SET status = ?, result = ?::jsonb, decided_at = now() WHERE id = ? AND user_id = ?",
                status, result == null ? null : result.toString(), id, userId);
    }

    private Action load(long userId, UUID id) {
        List<Action> rows = jdbc.query("""
                SELECT id, tool_name, status, arguments::text AS arguments, result::text AS result, created_at
                FROM desk.chat_action WHERE id = ? AND user_id = ?
                """, (rs, n) -> new Action((UUID) rs.getObject("id"), rs.getString("tool_name"), rs.getString("status"),
                parse(rs.getString("arguments")), parse(rs.getString("result")),
                rs.getTimestamp("created_at").toInstant()), id, userId);
        if (rows.isEmpty()) {
            throw DeskException.notFound();
        }
        return rows.get(0);
    }

    private Map<String, Object> view(Action a) {
        Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("id", a.id());
        m.put("tool", a.tool());
        m.put("status", a.status());
        m.put("arguments", a.arguments());
        m.put("result", a.result());
        m.put("createdAt", a.createdAt());
        return m;
    }

    private JsonNode parse(String json) {
        if (json == null) return null;
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            return null;
        }
    }
}
