package clawer.user.service;

import clawer.user.dto.SavedUniversityResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.util.List;

@Service
public class SavedUniversityService {

    private final JdbcTemplate jdbcTemplate;

    public SavedUniversityService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void save(long userId, long canonicalUniversityId) {
        jdbcTemplate.update("""
                INSERT INTO warehouse.saved_university (user_id, canonical_university_id)
                VALUES (?, ?)
                ON CONFLICT (user_id, canonical_university_id) DO NOTHING
                """,
                userId, canonicalUniversityId);
    }

    public void delete(long userId, long canonicalUniversityId) {
        jdbcTemplate.update(
                "DELETE FROM warehouse.saved_university WHERE user_id = ? AND canonical_university_id = ?",
                userId, canonicalUniversityId);
    }

    public List<SavedUniversityResponse> findByUserId(long userId) {
        return jdbcTemplate.query("""
                SELECT su.canonical_university_id,
                       cu.display_name   AS university_name,
                       cu.canonical_slug AS slug,
                       c.country_name    AS country,
                       su.created_at     AS saved_at
                FROM warehouse.saved_university su
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = su.canonical_university_id
                LEFT JOIN warehouse.countries c
                  ON c.country_id = cu.country_id
                WHERE su.user_id = ?
                ORDER BY su.created_at DESC
                """,
                (rs, rowNum) -> {
                    SavedUniversityResponse r = new SavedUniversityResponse();
                    r.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
                    r.setUniversityName(rs.getString("university_name"));
                    r.setSlug(rs.getString("slug"));
                    r.setCountry(rs.getString("country"));
                    Timestamp ts = rs.getTimestamp("saved_at");
                    r.setSavedAt(ts != null ? ts.toInstant() : null);
                    return r;
                },
                userId);
    }
}
