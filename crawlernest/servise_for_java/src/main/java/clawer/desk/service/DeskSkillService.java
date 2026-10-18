package clawer.desk.service;

import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Set;

import static clawer.desk.service.DeskTaskService.instant;

/**
 * Skill mastery (desk.skill_mastery): counts of questions attempted and answered
 * correctly per unit. The percentage is the database's generated column; no
 * endpoint accepts one.
 *
 * <p>Results are added, not replaced: posting "10 attempted, 8 correct" twice
 * leaves 20 and 16. A unit's counts come from one source; a result from another
 * source is refused rather than blended into a figure that would mean neither.
 */
@Service
public class DeskSkillService {

    public static final Set<String> SOURCES = Set.of("practice", "mock_test", "self_reported");
    static final int MAX_QUESTIONS_PER_RESULT = 1000;

    private static final Set<String> FIELDS = Set.of("subject", "unit", "attempted", "correct", "source");

    /** {@code masteryPct} is null until a question has been attempted. */
    public record Skill(long id, String subject, String unit, int questionsAttempted, int questionsCorrect,
                        BigDecimal masteryPct, String source, Instant lastPracticedAt) {}

    private static final String COLUMNS =
            "id, subject, unit, questions_attempted, questions_correct, mastery_pct, source, last_practiced_at";

    private static final RowMapper<Skill> ROW = (rs, n) -> new Skill(
            rs.getLong("id"), rs.getString("subject"), rs.getString("unit"),
            rs.getInt("questions_attempted"), rs.getInt("questions_correct"),
            rs.getBigDecimal("mastery_pct"), rs.getString("source"), instant(rs, "last_practiced_at"));

    private final JdbcTemplate jdbc;

    public DeskSkillService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Skill> list(long userId, String subject) {
        if (subject == null) {
            return jdbc.query("SELECT " + COLUMNS + " FROM desk.skill_mastery WHERE user_id = ? ORDER BY subject, unit",
                    ROW, userId);
        }
        return jdbc.query("SELECT " + COLUMNS + " FROM desk.skill_mastery WHERE user_id = ? AND subject = ? ORDER BY unit",
                ROW, userId, subject);
    }

    public Skill recordResult(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, FIELDS);
        String subject = in.text("subject", 60, true);
        String unit = in.text("unit", 80, true);
        int attempted = in.integer("attempted", 1, MAX_QUESTIONS_PER_RESULT, true);
        int correct = in.integer("correct", 0, MAX_QUESTIONS_PER_RESULT, true);
        String source = in.oneOf("source", SOURCES, false);
        if (correct > attempted) {
            throw DeskException.badRequest("correct must not exceed attempted.");
        }
        String resolvedSource = source == null ? "practice" : source;

        List<Skill> row = jdbc.query("""
                INSERT INTO desk.skill_mastery
                    (user_id, subject, unit, questions_attempted, questions_correct, source, last_practiced_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                ON CONFLICT ON CONSTRAINT skill_mastery_unit_key DO UPDATE
                SET questions_attempted = skill_mastery.questions_attempted + EXCLUDED.questions_attempted,
                    questions_correct = skill_mastery.questions_correct + EXCLUDED.questions_correct,
                    last_practiced_at = now(),
                    updated_at = now()
                WHERE skill_mastery.source = EXCLUDED.source
                RETURNING """ + " " + COLUMNS,
                ROW, userId, subject, unit, attempted, correct, resolvedSource);
        if (row.isEmpty()) {
            throw DeskException.conflict("This unit's counts come from another source; record "
                    + resolvedSource + " results under a separate unit.");
        }
        return row.get(0);
    }

    public boolean delete(long userId, long id) {
        return jdbc.update("DELETE FROM desk.skill_mastery WHERE id = ? AND user_id = ?", id, userId) > 0;
    }
}
