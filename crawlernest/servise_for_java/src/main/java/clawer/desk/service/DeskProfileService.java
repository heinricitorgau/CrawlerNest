package clawer.desk.service;

import clawer.desk.support.DeskException;
import clawer.desk.support.DeskInput;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.DateTimeException;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Set;

import static clawer.desk.service.DeskTaskService.instant;

/**
 * The desk profile (desk.user_profile), one row per user, created on first save.
 *
 * <p>Scores are what the user typed in and are returned under a
 * {@code selfReported} key so no caller can mistake them for verified ones.
 */
@Service
public class DeskProfileService {

    static final int MAX_PREFERENCES_BYTES = 8 * 1024;

    private static final Set<String> FIELDS = Set.of("displayName", "graduationYear", "timezone", "locale",
            "selfReported", "preferences");
    private static final Set<String> SCORE_FIELDS = Set.of("gpa", "gpaScale", "ielts", "toefl", "sat");

    public record SelfReported(BigDecimal gpa, BigDecimal gpaScale, BigDecimal ielts, Integer toefl, Integer sat) {}

    public record Profile(String displayName, Integer graduationYear, String timezone, String locale,
                          SelfReported selfReported, JsonNode preferences, Instant updatedAt) {}

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper;

    public DeskProfileService(JdbcTemplate jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    /** The stored profile, or the defaults when the user has never saved one. Never writes. */
    public Profile get(long userId) {
        List<Profile> rows = jdbc.query("""
                SELECT display_name, graduation_year, timezone, locale, self_reported_gpa, gpa_scale,
                       self_reported_ielts, self_reported_toefl, self_reported_sat, preferences::text, updated_at
                FROM desk.user_profile WHERE user_id = ?
                """, (rs, n) -> new Profile(
                        rs.getString("display_name"), (Integer) rs.getObject("graduation_year", Integer.class),
                        rs.getString("timezone"), rs.getString("locale"),
                        new SelfReported(rs.getBigDecimal("self_reported_gpa"), rs.getBigDecimal("gpa_scale"),
                                rs.getBigDecimal("self_reported_ielts"),
                                rs.getObject("self_reported_toefl", Integer.class),
                                rs.getObject("self_reported_sat", Integer.class)),
                        parse(rs.getString("preferences")), instant(rs, "updated_at")),
                userId);
        if (rows.isEmpty()) {
            return new Profile(null, null, "UTC", "en", new SelfReported(null, null, null, null, null),
                    objectMapper.createObjectNode(), null);
        }
        return rows.get(0);
    }

    /** The user's zone for "today"; UTC when unset or unreadable. */
    public ZoneId zoneOf(long userId) {
        List<String> zone = jdbc.queryForList("SELECT timezone FROM desk.user_profile WHERE user_id = ?",
                String.class, userId);
        try {
            return zone.isEmpty() ? ZoneOffset.UTC : ZoneId.of(zone.get(0));
        } catch (DateTimeException e) {
            return ZoneOffset.UTC;
        }
    }

    /** Replaces the whole profile: a field left out is cleared or reset to its default. */
    public Profile put(long userId, JsonNode body) {
        DeskInput in = new DeskInput(body, FIELDS);
        String displayName = in.text("displayName", 100, false);
        Integer graduationYear = in.integer("graduationYear", 2000, 2100, false);
        String timezone = in.text("timezone", 64, false);
        if (timezone != null) {
            try {
                ZoneId.of(timezone);
            } catch (DateTimeException e) {
                throw DeskException.badRequest("timezone must be an IANA zone such as Asia/Taipei.");
            }
        }
        String locale = in.text("locale", 16, false);

        DeskInput scores = in.node("selfReported") == null
                ? new DeskInput(objectMapper.createObjectNode(), SCORE_FIELDS)
                : new DeskInput(in.node("selfReported"), SCORE_FIELDS);
        BigDecimal gpaScale = scores.decimal("gpaScale", new BigDecimal("0.01"), new BigDecimal("100"));
        BigDecimal gpa = scores.decimal("gpa", BigDecimal.ZERO, new BigDecimal("100"));
        if (gpa != null && gpaScale == null) {
            throw DeskException.badRequest("selfReported.gpa needs selfReported.gpaScale.");
        }
        if (gpa != null && gpa.compareTo(gpaScale) > 0) {
            throw DeskException.badRequest("selfReported.gpa must not exceed selfReported.gpaScale.");
        }
        BigDecimal ielts = scores.decimal("ielts", BigDecimal.ZERO, new BigDecimal("9"));
        if (ielts != null && ielts.remainder(new BigDecimal("0.5")).signum() != 0) {
            throw DeskException.badRequest("selfReported.ielts must be a multiple of 0.5.");
        }
        Integer toefl = scores.integer("toefl", 0, 120, false);
        Integer sat = scores.integer("sat", 400, 1600, false);

        JsonNode preferences = in.node("preferences");
        if (preferences != null && !preferences.isObject()) {
            throw DeskException.badRequest("preferences must be an object.");
        }
        String preferencesJson = preferences == null ? "{}" : preferences.toString();
        if (preferencesJson.getBytes(StandardCharsets.UTF_8).length > MAX_PREFERENCES_BYTES) {
            throw DeskException.badRequest("preferences must be " + MAX_PREFERENCES_BYTES + " bytes or fewer.");
        }

        jdbc.update("""
                INSERT INTO desk.user_profile
                    (user_id, display_name, graduation_year, timezone, locale, self_reported_gpa, gpa_scale,
                     self_reported_ielts, self_reported_toefl, self_reported_sat, preferences)
                VALUES (?, ?, ?, coalesce(?, 'UTC'), coalesce(?, 'en'), ?, ?, ?, ?, ?, ?::jsonb)
                ON CONFLICT (user_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    graduation_year = EXCLUDED.graduation_year,
                    timezone = EXCLUDED.timezone,
                    locale = EXCLUDED.locale,
                    self_reported_gpa = EXCLUDED.self_reported_gpa,
                    gpa_scale = EXCLUDED.gpa_scale,
                    self_reported_ielts = EXCLUDED.self_reported_ielts,
                    self_reported_toefl = EXCLUDED.self_reported_toefl,
                    self_reported_sat = EXCLUDED.self_reported_sat,
                    preferences = EXCLUDED.preferences,
                    updated_at = now()
                """, userId, displayName, graduationYear, timezone, locale, gpa, gpaScale, ielts, toefl, sat,
                preferencesJson);
        return get(userId);
    }

    private JsonNode parse(String json) {
        try {
            return objectMapper.readTree(json == null ? "{}" : json);
        } catch (Exception e) {
            return objectMapper.createObjectNode();
        }
    }
}
