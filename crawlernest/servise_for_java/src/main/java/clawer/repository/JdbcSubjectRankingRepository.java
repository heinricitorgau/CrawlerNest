package clawer.repository;

import clawer.dto.SubjectOptionDTO;
import clawer.dto.SubjectRankingDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Repository
public class JdbcSubjectRankingRepository implements SubjectRankingRepository {
    private final JdbcTemplate jdbcTemplate;

    public JdbcSubjectRankingRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public List<SubjectOptionDTO> findSubjects() {
        return jdbcTemplate.query(
                """
                SELECT subject_key, display_name AS subject_name
                FROM warehouse.ranking_subject
                WHERE is_active = TRUE
                ORDER BY display_name ASC
                """,
                (rs, rowNum) -> new SubjectOptionDTO(rs.getString("subject_key"), rs.getString("subject_name"))
        );
    }

    @Override
    public boolean subjectExists(String subjectKey) {
        Boolean exists = jdbcTemplate.queryForObject(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM warehouse.ranking_subject
                    WHERE subject_key = ?
                      AND is_active = TRUE
                )
                """,
                Boolean.class,
                subjectKey
        );
        return Boolean.TRUE.equals(exists);
    }

    @Override
    public Optional<Integer> findLatestYear(String subjectKey, String sourceCode) {
        Integer year = jdbcTemplate.query(
                """
                SELECT MAX(ranking_year) AS latest_year
                FROM analytics.v_subject_rankings_latest
                WHERE subject_key = ?
                  AND source_code = ?
                """,
                rs -> rs.next() ? (Integer) rs.getObject("latest_year") : null,
                subjectKey,
                sourceCode
        );
        return Optional.ofNullable(year);
    }

    @Override
    public List<SubjectRankingDTO> findSubjectRankings(
            String subjectKey,
            Integer year,
            String sourceCode,
            String country,
            String search,
            int page,
            int pageSize
    ) {
        List<Object> params = new ArrayList<>();
        String where = buildWhere(subjectKey, year, sourceCode, country, search, params);
        params.add(pageSize);
        params.add(page * pageSize);
        return jdbcTemplate.query(
                """
                SELECT
                    canonical_university_id,
                    canonical_slug,
                    university_name,
                    country_code,
                    country_name,
                    source_code,
                    source_name,
                    subject_key,
                    subject_name,
                    ranking_year,
                    rank_position,
                    rank_display,
                    score,
                    score_scale,
                    source_url
                FROM analytics.v_subject_rankings_latest
                """ + where + """
                ORDER BY rank_position ASC NULLS LAST, university_name ASC, canonical_university_id ASC
                LIMIT ? OFFSET ?
                """,
                subjectRankingRowMapper(),
                params.toArray()
        );
    }

    @Override
    public long countSubjectRankings(String subjectKey, Integer year, String sourceCode, String country, String search) {
        List<Object> params = new ArrayList<>();
        String where = buildWhere(subjectKey, year, sourceCode, country, search, params);
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM analytics.v_subject_rankings_latest " + where,
                Long.class,
                params.toArray()
        );
        return count == null ? 0L : count;
    }

    @Override
    public List<SubjectRankingDTO> findUniversitySubjectRankings(Long canonicalUniversityId, Integer year, String sourceCode) {
        List<Object> params = new ArrayList<>();
        params.add(canonicalUniversityId);
        params.add(sourceCode);
        String yearClause = "";
        if (year != null) {
            yearClause = " AND ranking_year = ? ";
            params.add(year);
        }
        return jdbcTemplate.query(
                """
                SELECT
                    canonical_university_id,
                    canonical_slug,
                    university_name,
                    country_code,
                    country_name,
                    source_code,
                    source_name,
                    subject_key,
                    subject_name,
                    ranking_year,
                    rank_position,
                    rank_display,
                    score,
                    score_scale,
                    source_url
                FROM analytics.v_subject_rankings_latest
                WHERE canonical_university_id = ?
                  AND source_code = ?
                """ + yearClause + """
                ORDER BY ranking_year DESC, subject_name ASC, rank_position ASC NULLS LAST
                """,
                subjectRankingRowMapper(),
                params.toArray()
        );
    }

    private String buildWhere(
            String subjectKey,
            Integer year,
            String sourceCode,
            String country,
            String search,
            List<Object> params
    ) {
        StringBuilder where = new StringBuilder(" WHERE subject_key = ? AND source_code = ? ");
        params.add(subjectKey);
        params.add(sourceCode);
        if (year != null) {
            where.append(" AND ranking_year = ? ");
            params.add(year);
        }
        if (country != null && !country.isBlank()) {
            where.append(" AND country_name = ? ");
            params.add(country.trim());
        }
        if (search != null && !search.isBlank()) {
            where.append(" AND university_name ILIKE ? ");
            params.add("%" + search.trim() + "%");
        }
        return where.toString();
    }

    private RowMapper<SubjectRankingDTO> subjectRankingRowMapper() {
        return new RowMapper<>() {
            @Override
            public SubjectRankingDTO mapRow(ResultSet rs, int rowNum) throws SQLException {
                SubjectRankingDTO dto = new SubjectRankingDTO();
                dto.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
                dto.setCanonicalSlug(rs.getString("canonical_slug"));
                dto.setUniversityName(rs.getString("university_name"));
                dto.setCountryCode(rs.getString("country_code"));
                dto.setCountryName(rs.getString("country_name"));
                dto.setSourceCode(rs.getString("source_code"));
                dto.setSourceName(rs.getString("source_name"));
                dto.setSubjectKey(rs.getString("subject_key"));
                dto.setSubjectName(rs.getString("subject_name"));
                dto.setRankingYear((Integer) rs.getObject("ranking_year"));
                dto.setRankPosition((Integer) rs.getObject("rank_position"));
                dto.setRankDisplay(rs.getString("rank_display"));
                dto.setScore(rs.getObject("score") == null ? null : rs.getDouble("score"));
                dto.setScoreScale(rs.getObject("score_scale") == null ? null : rs.getDouble("score_scale"));
                dto.setSourceUrl(rs.getString("source_url"));
                return dto;
            }
        };
    }
}
