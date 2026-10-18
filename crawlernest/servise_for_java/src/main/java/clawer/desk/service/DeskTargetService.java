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
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

import static clawer.desk.service.DeskTaskService.instant;
import static clawer.desk.service.DeskTaskService.localDate;
import static clawer.desk.service.DeskTaskService.nullableLong;
import static clawer.desk.service.DeskTaskService.sqlDate;

/**
 * The user's list of schools and programmes (desk.target_entity).
 *
 * <p>A target either names a warehouse university (canonicalUniversityId) or
 * carries a free-text name. The university is set when the target is created and
 * not changed afterwards; picking a different school is a different target.
 *
 * <p>There is deliberately no admission-probability field. See
 * docs/architecture/DESK_SCHEMA_AND_API.md, decision 3.
 */
@Service
public class DeskTargetService {

    public static final Set<String> STAGES = Set.of("researching", "shortlisted", "applying", "submitted",
            "admitted", "waitlisted", "rejected", "enrolled", "withdrawn");
    public static final Set<String> ROUNDS = Set.of("ED", "ED2", "EA", "REA", "RD", "rolling");
    public static final Set<String> BANDS = Set.of("reach", "target", "safety");

    private static final Set<String> CREATE_FIELDS = Set.of("canonicalUniversityId", "customName", "programmeName",
            "stage", "applicationRound", "userBand", "deadline", "notes");
    private static final Set<String> UPDATE_FIELDS = Set.of("customName", "programmeName",
            "stage", "applicationRound", "userBand", "deadline", "notes");

    /**
     * {@code name} is the warehouse display name when the target links one, else
     * the user's own. {@code universityStatus} is the linked record's status: a
     * "merged" value means the record was folded into another and the merge script
     * has not repointed this row yet, which the UI should show rather than hide.
     */
    public record Target(long id, String name, Long canonicalUniversityId, String canonicalSlug,
                         String universityStatus, String customName, String programmeName, String stage,
                         String applicationRound, String userBand, LocalDate deadline, String notes,
                         String createdBy, Instant createdAt, Instant updatedAt) {}

    private static final String SELECT = """
            SELECT t.id, t.canonical_university_id, t.custom_name, t.programme_name, t.stage,
                   t.application_round, t.user_band, t.deadline, t.notes, t.created_by, t.created_at, t.updated_at,
                   cu.display_name, cu.canonical_slug, cu.status AS university_status
            FROM desk.target_entity t
            LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
            """;

    private static final RowMapper<Target> ROW = (rs, n) -> {
        String displayName = rs.getString("display_name");
        String customName = rs.getString("custom_name");
        return new Target(
                rs.getLong("id"), displayName != null ? displayName : customName,
                nullableLong(rs, "canonical_university_id"), rs.getString("canonical_slug"),
                rs.getString("university_status"), customName, rs.getString("programme_name"),
                rs.getString("stage"), rs.getString("application_round"), rs.getString("user_band"),
                localDate(rs, "deadline"), rs.getString("notes"), rs.getString("created_by"),
                instant(rs, "created_at"), instant(rs, "updated_at"));
    };

    private final JdbcTemplate jdbc;

    public DeskTargetService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<Target> list(long userId, String stage) {
        if (stage != null && !STAGES.contains(stage)) {
            throw DeskException.badRequest("stage must be one of " + String.join(", ", STAGES.stream().sorted().toList()) + ".");
        }
        String filter = stage == null ? "" : " AND t.stage = ?";
        Object[] params = stage == null ? new Object[]{userId} : new Object[]{userId, stage};
        // Soonest deadline first; targets with no deadline after, by name.
        return jdbc.query(SELECT + " WHERE t.user_id = ?" + filter
                + " ORDER BY t.deadline NULLS LAST, coalesce(cu.display_name, t.custom_name), t.id", ROW, params);
    }

    public Optional<Target> find(long userId, long id) {
        return jdbc.query(SELECT + " WHERE t.id = ? AND t.user_id = ?", ROW, id, userId).stream().findFirst();
    }

    public Target create(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, CREATE_FIELDS);
        Long canonicalId = in.id("canonicalUniversityId", false);
        String customName = in.text("customName", 200, false);
        if (canonicalId == null && customName == null) {
            throw DeskException.badRequest("Give canonicalUniversityId or customName.");
        }
        if (canonicalId != null) {
            requireActiveUniversity(canonicalId);
        }
        String programme = in.text("programmeName", 200, false);
        String stage = in.oneOf("stage", STAGES, false);
        String round = in.oneOf("applicationRound", ROUNDS, false);
        String band = in.oneOf("userBand", BANDS, false);
        LocalDate deadline = in.date("deadline", false);
        String notes = in.text("notes", 4000, false);

        if (canonicalId != null) {
            Boolean exists = jdbc.queryForObject("""
                    SELECT EXISTS (SELECT 1 FROM desk.target_entity
                                   WHERE user_id = ? AND canonical_university_id = ? AND programme_key = ?)
                    """, Boolean.class, userId, canonicalId, programmeKey(programme));
            if (Boolean.TRUE.equals(exists)) {
                throw DeskException.conflict("That university and programme is already on your list.");
            }
        }
        return insert(userId, canonicalId, customName, programme, stage, round, band, deadline, notes, "user");
    }

    /**
     * A school Tassel added (update_target_list, action "add"). The caller has
     * already resolved the name: a warehouse id only for an exact, unique match,
     * otherwise the user's own wording as customName.
     */
    public Target createForAgent(long userId, Long canonicalId, String customName, String programme, String stage,
                                 String round, String band, LocalDate deadline) {
        if (canonicalId != null) {
            requireActiveUniversity(canonicalId);
            Boolean exists = jdbc.queryForObject("""
                    SELECT EXISTS (SELECT 1 FROM desk.target_entity
                                   WHERE user_id = ? AND canonical_university_id = ? AND programme_key = ?)
                    """, Boolean.class, userId, canonicalId, programmeKey(programme));
            if (Boolean.TRUE.equals(exists)) {
                throw DeskException.conflict("That school and programme is already on the list.");
            }
        } else {
            Boolean exists = jdbc.queryForObject("""
                    SELECT EXISTS (SELECT 1 FROM desk.target_entity
                                   WHERE user_id = ? AND canonical_university_id IS NULL
                                     AND lower(custom_name) = lower(?) AND programme_key = ?)
                    """, Boolean.class, userId, customName, programmeKey(programme));
            if (Boolean.TRUE.equals(exists)) {
                throw DeskException.conflict("That school and programme is already on the list.");
            }
        }
        return insert(userId, canonicalId, customName, programme, stage, round, band, deadline, null, "agent");
    }

    private Target insert(long userId, Long canonicalId, String customName, String programme, String stage, String round,
                          String band, LocalDate deadline, String notes, String createdBy) {
        Long id = jdbc.queryForObject("""
                INSERT INTO desk.target_entity
                    (user_id, canonical_university_id, custom_name, programme_name, programme_key, stage,
                     application_round, user_band, deadline, notes, created_by)
                VALUES (?, ?, ?, ?, ?, coalesce(?, 'researching'), ?, ?, ?, ?, ?)
                RETURNING id
                """, Long.class, userId, canonicalId, customName, programme, programmeKey(programme), stage,
                round, band, sqlDate(deadline), notes, createdBy);
        return find(userId, id).orElseThrow();
    }

    public Target update(long userId, long id, JsonNode body) {
        DeskInput in = new DeskInput(body, UPDATE_FIELDS);
        RowUpdate update = new RowUpdate();
        if (in.has("customName")) update.set("custom_name", in.text("customName", 200, false));
        if (in.has("programmeName")) {
            String programme = in.text("programmeName", 200, false);
            update.set("programme_name", programme);
            update.set("programme_key", programmeKey(programme));
        }
        if (in.has("stage")) update.set("stage", in.oneOf("stage", STAGES, true));
        if (in.has("applicationRound")) update.set("application_round", in.oneOf("applicationRound", ROUNDS, false));
        if (in.has("userBand")) update.set("user_band", in.oneOf("userBand", BANDS, false));
        if (in.has("deadline")) update.set("deadline", in.date("deadline", false));
        if (in.has("notes")) update.set("notes", in.text("notes", 4000, false));
        // Clearing customName on a target with no university trips target_entity_named,
        // and a programme rename onto an existing pair trips the unique index; the
        // handler turns both into a 400 / 409.
        if (!update.apply(jdbc, "desk.target_entity", id, userId, true)) {
            throw DeskException.notFound();
        }
        return find(userId, id).orElseThrow();
    }

    /** Tasks and essay reviews pointing at it keep their rows; their link is cleared. */
    public boolean delete(long userId, long id) {
        return jdbc.update("DELETE FROM desk.target_entity WHERE id = ? AND user_id = ?", id, userId) > 0;
    }

    /** The unique key's form of a programme name: case- and spacing-insensitive, '' for none. */
    static String programmeKey(String programme) {
        return programme == null ? "" : programme.trim().replaceAll("\\s+", " ").toLowerCase(Locale.ROOT);
    }

    /**
     * There is no foreign key to canonical_university (V003 header), so this is
     * the check. A merged record is refused: it would put the target on a
     * university that is no longer listed.
     */
    private void requireActiveUniversity(long canonicalId) {
        List<String> status = jdbc.queryForList(
                "SELECT status FROM warehouse.canonical_university WHERE canonical_university_id = ?",
                String.class, canonicalId);
        if (status.isEmpty()) {
            throw DeskException.badRequest("No such university.");
        }
        if (!"active".equals(status.get(0))) {
            throw DeskException.badRequest("That university record is " + status.get(0) + "; search for it again.");
        }
    }
}
