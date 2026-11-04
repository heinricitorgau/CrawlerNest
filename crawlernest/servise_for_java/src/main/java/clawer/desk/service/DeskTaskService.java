package clawer.desk.service;

import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import clawer.desk.support.RowUpdate;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.sql.Date;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * The user's tasks (desk.task). Every statement is scoped by the session user's id.
 *
 * <p>Tasks created here are {@code created_by = 'user'}. A task the agent creates
 * goes through the chat-action path, which records the action it came from.
 */
@Service
public class DeskTaskService {

    public static final Set<String> PRIORITIES = Set.of("high", "normal", "low");
    public static final Set<String> STATUSES = Set.of("todo", "in_progress", "done", "cancelled");
    static final int MAX_TITLE = 200;
    static final int MAX_NOTES = 4000;
    static final int MAX_CATEGORY = 40;

    private static final Set<String> FIELDS =
            Set.of("title", "notes", "dueDate", "priority", "status", "category", "sprintId", "targetEntityId");
    private static final Set<String> UPDATE_FIELDS = java.util.stream.Stream.concat(FIELDS.stream(),
            java.util.stream.Stream.of("expectedRevision")).collect(java.util.stream.Collectors.toUnmodifiableSet());

    /** completed_at follows status, so the table's "done has a time" check always holds. */
    private static final String COMPLETED_AT_FOR_STATUS =
            "CASE WHEN ? = 'done' THEN COALESCE(completed_at, now()) ELSE NULL END";

    public record Task(long id, String title, String notes, LocalDate dueDate, String priority, String status,
                       String category, Long sprintId, Long targetEntityId, String createdBy,
                       long revision, Instant completedAt, Instant createdAt, Instant updatedAt) {}

    private static final String COLUMNS = """
            id, title, notes, due_date, priority, status, category, sprint_id, target_entity_id,
            created_by, revision, completed_at, created_at, updated_at
            """;

    static final RowMapper<Task> ROW = (rs, n) -> new Task(
            rs.getLong("id"), rs.getString("title"), rs.getString("notes"), localDate(rs, "due_date"),
            rs.getString("priority"), rs.getString("status"), rs.getString("category"),
            nullableLong(rs, "sprint_id"), nullableLong(rs, "target_entity_id"), rs.getString("created_by"),
            rs.getLong("revision"), instant(rs, "completed_at"), instant(rs, "created_at"), instant(rs, "updated_at"));

    private final JdbcTemplate jdbc;
    private final DeskOwnership ownership;

    public DeskTaskService(JdbcTemplate jdbc, DeskOwnership ownership) {
        this.jdbc = jdbc;
        this.ownership = ownership;
    }

    /**
     * @param status "open" (todo and in progress, the default), "done", or "all"
     */
    public List<Task> list(long userId, String status, Long sprintId) {
        StringBuilder sql = new StringBuilder("SELECT " + COLUMNS + " FROM desk.task WHERE user_id = ?");
        List<Object> params = new ArrayList<>(List.of(userId));
        switch (status == null ? "open" : status) {
            case "open" -> sql.append(" AND status IN ('todo', 'in_progress')");
            case "done" -> sql.append(" AND status = 'done'");
            case "all" -> { }
            default -> throw DeskException.badRequest("status must be one of open, done, all.");
        }
        if (sprintId != null) {
            sql.append(" AND sprint_id = ?");
            params.add(sprintId);
        }
        // Open before finished, then soonest due; undated tasks after dated ones.
        sql.append(" ORDER BY status IN ('done', 'cancelled'), due_date NULLS LAST, id");
        return jdbc.query(sql.toString(), ROW, params.toArray());
    }

    public Optional<Task> find(long userId, long id) {
        return jdbc.query("SELECT " + COLUMNS + " FROM desk.task WHERE id = ? AND user_id = ?", ROW, id, userId)
                .stream().findFirst();
    }

    public Task create(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, FIELDS);
        String title = in.text("title", MAX_TITLE, true);
        String notes = in.text("notes", MAX_NOTES, false);
        LocalDate dueDate = in.date("dueDate", false);
        String priority = in.oneOf("priority", PRIORITIES, false);
        String status = in.oneOf("status", STATUSES, false);
        String category = in.text("category", MAX_CATEGORY, false);
        Long sprintId = in.id("sprintId", false);
        Long targetEntityId = in.id("targetEntityId", false);
        ownership.require("desk.sprint", sprintId, userId, "sprint");
        ownership.require("desk.target_entity", targetEntityId, userId, "target");

        return insert(userId, title, notes, dueDate, priority, status, category, sprintId, targetEntityId, null);
    }

    /**
     * A task Tassel created (create_action_task). The caller has validated the
     * arguments with the same limits as {@link #create}; the row records the chat
     * action it came from, which is what lets "undo" find it.
     */
    public Task createForAgent(long userId, String title, LocalDate dueDate, String priority, String category,
                               Long targetEntityId, java.util.UUID actionId) {
        ownership.require("desk.target_entity", targetEntityId, userId, "target");
        return insert(userId, title, null, dueDate, priority, null, category, null, targetEntityId, actionId);
    }

    private Task insert(long userId, String title, String notes, LocalDate dueDate, String priority, String status,
                        String category, Long sprintId, Long targetEntityId, java.util.UUID actionId) {
        String resolvedStatus = status == null ? "todo" : status;
        Long id = jdbc.queryForObject("""
                INSERT INTO desk.task
                    (user_id, title, notes, due_date, priority, status, category, sprint_id, target_entity_id,
                     created_by, source_action_id, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'done' THEN now() END)
                RETURNING id
                """, Long.class,
                userId, title, notes, sqlDate(dueDate), priority == null ? "normal" : priority, resolvedStatus,
                category, sprintId, targetEntityId, actionId == null ? "user" : "agent", actionId, resolvedStatus);
        return find(userId, id).orElseThrow();
    }

    /** A PATCH; with {@code expectedRevision}, refused (409) unless the task is still at that revision. */
    public Task update(long userId, long id, JsonNode body) {
        DeskInput in = new DeskInput(body, UPDATE_FIELDS);
        Long expectedRevision = in.revision("expectedRevision", 1);
        RowUpdate update = new RowUpdate();
        if (in.has("title")) update.set("title", in.text("title", MAX_TITLE, true));
        if (in.has("notes")) update.set("notes", in.text("notes", MAX_NOTES, false));
        if (in.has("dueDate")) update.set("due_date", in.date("dueDate", false));
        if (in.has("priority")) update.set("priority", in.oneOf("priority", PRIORITIES, true));
        if (in.has("status")) {
            String status = in.oneOf("status", STATUSES, true);
            update.set("status", status);
            update.setExpression("completed_at", COMPLETED_AT_FOR_STATUS, status);
        }
        if (in.has("category")) update.set("category", in.text("category", MAX_CATEGORY, false));
        if (in.has("sprintId")) {
            Long sprintId = in.id("sprintId", false);
            ownership.require("desk.sprint", sprintId, userId, "sprint");
            update.set("sprint_id", sprintId);
        }
        if (in.has("targetEntityId")) {
            Long targetEntityId = in.id("targetEntityId", false);
            ownership.require("desk.target_entity", targetEntityId, userId, "target");
            update.set("target_entity_id", targetEntityId);
        }
        update.applyAtRevision(jdbc, "desk.task", id, userId, true, expectedRevision);
        return find(userId, id).orElseThrow();
    }

    public boolean delete(long userId, long id) {
        return jdbc.update("DELETE FROM desk.task WHERE id = ? AND user_id = ?", id, userId) > 0;
    }

    // ─── Row helpers, shared within the package ──────────────────────────────

    static LocalDate localDate(ResultSet rs, String column) throws SQLException {
        Date date = rs.getDate(column);
        return date == null ? null : date.toLocalDate();
    }

    static Instant instant(ResultSet rs, String column) throws SQLException {
        Timestamp ts = rs.getTimestamp(column);
        return ts == null ? null : ts.toInstant();
    }

    static Long nullableLong(ResultSet rs, String column) throws SQLException {
        long value = rs.getLong(column);
        return rs.wasNull() ? null : value;
    }

    static Date sqlDate(LocalDate date) {
        return date == null ? null : Date.valueOf(date);
    }
}
