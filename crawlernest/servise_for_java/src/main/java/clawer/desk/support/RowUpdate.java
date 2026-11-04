package clawer.desk.support;

import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.Date;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * Builds {@code UPDATE ... SET} for a PATCH from the fields the caller sent.
 *
 * <p>Column names and SQL fragments come only from service code, never from the
 * request; request values always go in as bind parameters.
 */
public final class RowUpdate {

    private final List<String> assignments = new ArrayList<>();
    private final List<Object> params = new ArrayList<>();

    public RowUpdate set(String column, Object value) {
        return setExpression(column, "?", value);
    }

    /** {@code column = expression}, where each {@code ?} in the expression binds {@code value}. */
    public RowUpdate setExpression(String column, String expression, Object value) {
        assignments.add(column + " = " + expression);
        long binds = expression.chars().filter(c -> c == '?').count();
        for (int i = 0; i < binds; i++) {
            params.add(value instanceof LocalDate date ? Date.valueOf(date) : value);
        }
        return this;
    }

    public boolean isEmpty() {
        return assignments.isEmpty();
    }

    /**
     * Applies the update to one row the user owns, only if it is still at {@code expectedRevision}
     * (when given). The table must have a {@code revision} column that a trigger increments.
     *
     * @throws DeskException 404 when the user has no such row, 409 when it is at another revision
     */
    public void applyAtRevision(JdbcTemplate jdbc, String table, long id, long userId, boolean touchUpdatedAt,
                                Long expectedRevision) {
        if (expectedRevision == null) {
            if (!apply(jdbc, table, id, userId, touchUpdatedAt)) {
                throw DeskException.notFound();
            }
            return;
        }
        if (isEmpty()) {
            throw DeskException.badRequest("Nothing to update.");
        }
        List<String> sets = new ArrayList<>(assignments);
        if (touchUpdatedAt) {
            sets.add("updated_at = now()");
        }
        List<Object> all = new ArrayList<>(params);
        all.add(id);
        all.add(userId);
        all.add(expectedRevision);
        String sql = "UPDATE " + table + " SET " + String.join(", ", sets)
                + " WHERE id = ? AND user_id = ? AND revision = ?";
        if (jdbc.update(sql, all.toArray()) > 0) {
            return;
        }
        List<Long> current = jdbc.queryForList("SELECT revision FROM " + table + " WHERE id = ? AND user_id = ?",
                Long.class, id, userId);
        if (current.isEmpty()) {
            throw DeskException.notFound();
        }
        throw DeskException.conflict("This is at revision " + current.get(0) + ", not " + expectedRevision
                + ": it was changed elsewhere. Reload it and apply your change again.");
    }

    /**
     * Applies the update to one row the user owns.
     *
     * @return false when no such row exists for this user
     */
    public boolean apply(JdbcTemplate jdbc, String table, long id, long userId, boolean touchUpdatedAt) {
        if (isEmpty()) {
            throw DeskException.badRequest("Nothing to update.");
        }
        List<String> sets = new ArrayList<>(assignments);
        if (touchUpdatedAt) {
            sets.add("updated_at = now()");
        }
        List<Object> all = new ArrayList<>(params);
        all.add(id);
        all.add(userId);
        String sql = "UPDATE " + table + " SET " + String.join(", ", sets) + " WHERE id = ? AND user_id = ?";
        return jdbc.update(sql, all.toArray()) > 0;
    }
}
