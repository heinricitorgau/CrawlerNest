package clawer.desk.service;

import clawer.desk.support.DeskException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Set;

/**
 * Checks that an id named in a request body belongs to the session user.
 *
 * <p>The composite foreign keys in V003 refuse a cross-user reference anyway.
 * This check runs first so the caller gets "No such sprint." rather than a
 * generic integrity error, and it answers the same for a row that does not exist
 * and a row that is someone else's.
 */
@Component
public class DeskOwnership {

    private static final Set<String> TABLES = Set.of("desk.sprint", "desk.target_entity", "desk.task");

    private final JdbcTemplate jdbc;

    public DeskOwnership(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** No-op for a null id: the field was absent or is being cleared. */
    public void require(String table, Long id, long userId, String label) {
        if (id == null) {
            return;
        }
        if (!TABLES.contains(table)) {
            throw new IllegalArgumentException("Not a desk table: " + table);
        }
        Boolean owned = jdbc.queryForObject(
                "SELECT EXISTS (SELECT 1 FROM " + table + " WHERE id = ? AND user_id = ?)", Boolean.class, id, userId);
        if (!Boolean.TRUE.equals(owned)) {
            throw DeskException.badRequest("No such " + label + ".");
        }
    }
}
