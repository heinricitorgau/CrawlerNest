package clawer.repository;

import clawer.dto.AdmissionRequirementDTO;
import clawer.dto.AdmissionRequirementsDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Date;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Reads structured entry requirements from {@code warehouse.admission_record}.
 *
 * <p>This is the only read path for admission requirements that uses the typed
 * columns. The older {@code warehouse.admission_requirements} table carries one
 * row per university with every requirement column NULL, so anything joined to
 * it reports "no data" for every university; and {@code raw_payload} on
 * admission_record is the crawler's unparsed capture, not a query surface.
 *
 * <p>Read-only by construction: no method here mutates.
 */
@Repository
public class AdmissionRecordRepository {

    private final JdbcTemplate jdbcTemplate;

    public AdmissionRecordRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * All published requirements for one canonical university, one entry per
     * degree level, plus the flattened cross-level summary.
     *
     * @return {@link AdmissionRequirementsDTO#empty()} when the university has no
     *         admission record, so callers need no null branch
     */
    public AdmissionRequirementsDTO findByCanonicalUniversityId(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return AdmissionRequirementsDTO.empty();
        }

        // One row per degree level. A university can be crawled from several
        // source pages for the same level, so the aggregate collapses those to
        // the lowest published bar and the earliest deadline rather than letting
        // an arbitrary row win.
        List<AdmissionRequirementDTO> levels = jdbcTemplate.query(
                """
                SELECT
                    degree_level,
                    MIN(ielts_requirement) AS ielts_requirement,
                    MIN(toefl_requirement) AS toefl_requirement,
                    MIN(duolingo_requirement) AS duolingo_requirement,
                    MIN(gpa_requirement) AS gpa_requirement,
                    MIN(application_deadline) AS application_deadline,
                    MIN(source_url) AS source_url
                FROM warehouse.admission_record
                WHERE canonical_university_id = ?
                GROUP BY degree_level
                ORDER BY degree_level ASC
                """,
                (rs, rowNum) -> {
                    AdmissionRequirementDTO dto = new AdmissionRequirementDTO();
                    dto.setDegreeLevel(rs.getString("degree_level"));
                    dto.setIeltsRequirement(nullableDouble(rs.getObject("ielts_requirement")));
                    dto.setToeflRequirement(nullableInteger(rs.getObject("toefl_requirement")));
                    dto.setDuolingoRequirement(nullableInteger(rs.getObject("duolingo_requirement")));
                    dto.setGpaRequirement(nullableDouble(rs.getObject("gpa_requirement")));
                    dto.setApplicationDeadline(isoDate(rs.getObject("application_deadline")));
                    dto.setSourceUrl(rs.getString("source_url"));
                    return dto;
                },
                canonicalUniversityId
        );

        if (levels.isEmpty()) {
            return AdmissionRequirementsDTO.empty();
        }

        AdmissionRequirementsDTO dto = new AdmissionRequirementsDTO();
        dto.setHasData(true);
        dto.setDegreeLevelCount(levels.size());
        dto.setByDegreeLevel(levels);
        dto.setSummary(summarise(levels));
        return dto;
    }

    /**
     * Cross-level summaries for a batch of universities, for list endpoints that
     * would otherwise issue one query per card.
     *
     * @return map keyed by canonical university id; ids with no admission record
     *         are absent rather than mapped to an empty value
     */
    public Map<Long, AdmissionRequirementDTO> findSummariesByCanonicalUniversityIds(List<Long> canonicalUniversityIds) {
        if (canonicalUniversityIds == null || canonicalUniversityIds.isEmpty()) {
            return Map.of();
        }

        String placeholders = String.join(",", Collections.nCopies(canonicalUniversityIds.size(), "?"));
        Map<Long, AdmissionRequirementDTO> summaries = new LinkedHashMap<>();

        jdbcTemplate.query(
                """
                SELECT
                    canonical_university_id,
                    MIN(ielts_requirement) AS ielts_requirement,
                    MIN(toefl_requirement) AS toefl_requirement,
                    MIN(duolingo_requirement) AS duolingo_requirement,
                    MIN(gpa_requirement) AS gpa_requirement,
                    MIN(application_deadline) AS application_deadline
                FROM warehouse.admission_record
                WHERE canonical_university_id IN (%s)
                GROUP BY canonical_university_id
                """.formatted(placeholders),
                rs -> {
                    while (rs.next()) {
                        AdmissionRequirementDTO dto = new AdmissionRequirementDTO();
                        // Deliberately no degreeLevel: this row spans every level
                        // the university publishes, so naming one would be a lie.
                        dto.setIeltsRequirement(nullableDouble(rs.getObject("ielts_requirement")));
                        dto.setToeflRequirement(nullableInteger(rs.getObject("toefl_requirement")));
                        dto.setDuolingoRequirement(nullableInteger(rs.getObject("duolingo_requirement")));
                        dto.setGpaRequirement(nullableDouble(rs.getObject("gpa_requirement")));
                        dto.setApplicationDeadline(isoDate(rs.getObject("application_deadline")));
                        summaries.put(rs.getLong("canonical_university_id"), dto);
                    }
                    return null;
                },
                canonicalUniversityIds.toArray()
        );

        return summaries;
    }

    private static AdmissionRequirementDTO summarise(List<AdmissionRequirementDTO> levels) {
        AdmissionRequirementDTO summary = new AdmissionRequirementDTO();
        for (AdmissionRequirementDTO level : levels) {
            summary.setIeltsRequirement(minDouble(summary.getIeltsRequirement(), level.getIeltsRequirement()));
            summary.setToeflRequirement(minInteger(summary.getToeflRequirement(), level.getToeflRequirement()));
            summary.setDuolingoRequirement(minInteger(summary.getDuolingoRequirement(), level.getDuolingoRequirement()));
            summary.setGpaRequirement(minDouble(summary.getGpaRequirement(), level.getGpaRequirement()));
            summary.setApplicationDeadline(minIsoDate(summary.getApplicationDeadline(), level.getApplicationDeadline()));
            if (summary.getSourceUrl() == null) {
                summary.setSourceUrl(level.getSourceUrl());
            }
        }
        return summary;
    }

    private static Double minDouble(Double current, Double candidate) {
        if (candidate == null) {
            return current;
        }
        if (current == null) {
            return candidate;
        }
        return Math.min(current, candidate);
    }

    private static Integer minInteger(Integer current, Integer candidate) {
        if (candidate == null) {
            return current;
        }
        if (current == null) {
            return candidate;
        }
        return Math.min(current, candidate);
    }

    /** ISO-8601 dates sort lexicographically, so a string compare is a date compare. */
    private static String minIsoDate(String current, String candidate) {
        if (candidate == null) {
            return current;
        }
        if (current == null) {
            return candidate;
        }
        return current.compareTo(candidate) <= 0 ? current : candidate;
    }

    private static Double nullableDouble(Object value) {
        return value == null ? null : ((Number) value).doubleValue();
    }

    private static Integer nullableInteger(Object value) {
        return value == null ? null : ((Number) value).intValue();
    }

    private static String isoDate(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Date sqlDate) {
            return sqlDate.toLocalDate().toString();
        }
        return value.toString();
    }
}
