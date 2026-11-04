package clawer.desk.service;

import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import clawer.desk.support.RowUpdate;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static clawer.desk.service.DeskTaskService.instant;
import static clawer.desk.service.DeskTaskService.localDate;
import static clawer.desk.service.DeskTaskService.sqlDate;

/**
 * Sprints group tasks over a date range (desk.sprint). Deleting one keeps its
 * tasks and clears their sprint_id.
 */
@Service
public class DeskSprintService {

    private static final Set<String> FIELDS = Set.of("title", "goal", "startDate", "endDate");
    private static final Set<String> UPDATE_FIELDS = Set.of("title", "goal", "startDate", "endDate", "expectedRevision");

    public record Sprint(long id, String title, String goal, LocalDate startDate, LocalDate endDate,
                         int taskCount, int doneCount, long revision, Instant createdAt) {}

    /** A sprint with its tasks, for the desk's sprint card. */
    public record SprintDetail(Sprint sprint, List<DeskTaskService.Task> tasks) {}

    private static final String SELECT = """
            SELECT s.id, s.title, s.goal, s.start_date, s.end_date, s.revision, s.created_at,
                   count(t.id) FILTER (WHERE t.status <> 'cancelled') AS task_count,
                   count(t.id) FILTER (WHERE t.status = 'done') AS done_count
            FROM desk.sprint s
            LEFT JOIN desk.task t ON t.sprint_id = s.id AND t.user_id = s.user_id
            """;

    private static final RowMapper<Sprint> ROW = (rs, n) -> new Sprint(
            rs.getLong("id"), rs.getString("title"), rs.getString("goal"),
            localDate(rs, "start_date"), localDate(rs, "end_date"),
            rs.getInt("task_count"), rs.getInt("done_count"), rs.getLong("revision"), instant(rs, "created_at"));

    private final JdbcTemplate jdbc;
    private final DeskTaskService tasks;
    private final DeskProfileService profiles;

    public DeskSprintService(JdbcTemplate jdbc, DeskTaskService tasks, DeskProfileService profiles) {
        this.jdbc = jdbc;
        this.tasks = tasks;
        this.profiles = profiles;
    }

    public List<Sprint> list(long userId) {
        return jdbc.query(SELECT + " WHERE s.user_id = ? GROUP BY s.id ORDER BY s.start_date DESC, s.id DESC",
                ROW, userId);
    }

    public Optional<SprintDetail> detail(long userId, long id) {
        return jdbc.query(SELECT + " WHERE s.id = ? AND s.user_id = ? GROUP BY s.id", ROW, id, userId)
                .stream().findFirst()
                .map(sprint -> new SprintDetail(sprint, tasks.list(userId, "all", sprint.id())));
    }

    /**
     * The sprint covering today in the user's own time zone (UTC until they set
     * one), the latest-starting one if several overlap; empty when none does.
     */
    public Optional<SprintDetail> current(long userId) {
        LocalDate today = LocalDate.now(profiles.zoneOf(userId));
        return jdbc.query(SELECT + """
                 WHERE s.user_id = ? AND s.start_date <= ? AND s.end_date >= ?
                 GROUP BY s.id ORDER BY s.start_date DESC, s.id DESC LIMIT 1
                """, ROW, userId, sqlDate(today), sqlDate(today))
                .stream().findFirst()
                .map(sprint -> new SprintDetail(sprint, tasks.list(userId, "all", sprint.id())));
    }

    public SprintDetail create(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, FIELDS);
        String title = in.text("title", 120, true);
        String goal = in.text("goal", 500, false);
        LocalDate start = in.date("startDate", true);
        LocalDate end = in.date("endDate", true);
        if (end.isBefore(start)) {
            throw DeskException.badRequest("endDate must not be before startDate.");
        }
        Long id = jdbc.queryForObject("""
                INSERT INTO desk.sprint (user_id, title, goal, start_date, end_date)
                VALUES (?, ?, ?, ?, ?) RETURNING id
                """, Long.class, userId, title, goal, sqlDate(start), sqlDate(end));
        return detail(userId, id).orElseThrow();
    }

    /**
     * A PATCH; with {@code expectedRevision}, refused (409) unless the sprint is still at that revision.
     * The revision covers the sprint's own fields, not its tasks.
     */
    public SprintDetail update(long userId, long id, JsonNode body) {
        DeskInput in = new DeskInput(body, UPDATE_FIELDS);
        Long expectedRevision = in.revision("expectedRevision", 1);
        RowUpdate update = new RowUpdate();
        if (in.has("title")) update.set("title", in.text("title", 120, true));
        if (in.has("goal")) update.set("goal", in.text("goal", 500, false));
        if (in.has("startDate")) update.set("start_date", in.date("startDate", true));
        if (in.has("endDate")) update.set("end_date", in.date("endDate", true));
        // A one-sided date change is checked against the stored other side by the
        // table's sprint_dates_ordered constraint, which the handler turns into a 400.
        update.applyAtRevision(jdbc, "desk.sprint", id, userId, false, expectedRevision);
        return detail(userId, id).orElseThrow();
    }

    public boolean delete(long userId, long id) {
        return jdbc.update("DELETE FROM desk.sprint WHERE id = ? AND user_id = ?", id, userId) > 0;
    }
}
