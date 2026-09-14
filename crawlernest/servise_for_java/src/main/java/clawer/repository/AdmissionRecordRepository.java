package clawer.repository;

import clawer.dto.AdmissionRequirementDTO;
import clawer.dto.AdmissionRequirementsDTO;
import clawer.service.AdmissionCaveats;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Date;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Reads structured entry requirements from {@code warehouse.admission_record}.
 *
 * <p>University-level figures come through {@code warehouse.v_admission_requirement_institution}
 * and {@code _summary}, never from a {@code MIN()} over the table. That aggregate
 * was harmless with one row per page and wrong the moment a source writes
 * programme rows or a second intake: it would quote the least demanding
 * programme, or last year's bar, as the university's. The views hold the rule
 * once for every language; programme rows are read separately and listed as
 * what they are.
 *
 * <p>The older {@code warehouse.admission_requirements} table carries one row per
 * university with every requirement column NULL, so anything joined to it
 * reports "no data" for every university; and {@code raw_payload} on
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
     * All published requirements for one canonical university: one
     * university-level entry per degree level, the programme-specific
     * requirements, the flattened cross-level summary, and their caveats.
     *
     * @return an empty result carrying {@code CAVEAT_IELTS_MISSING} when the
     *         university has no admission record, so callers need no null branch
     */
    public AdmissionRequirementsDTO findByCanonicalUniversityId(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return withoutData();
        }

        List<AdmissionRequirementDTO> levels = jdbcTemplate.query(
                """
                SELECT
                    degree_level,
                    ielts_requirement,
                    toefl_requirement,
                    duolingo_requirement,
                    gpa_requirement,
                    application_deadline,
                    source_url,
                    requirement_scope,
                    intake_year,
                    intake_year_basis,
                    values_differ
                FROM warehouse.v_admission_requirement_institution
                WHERE canonical_university_id = ?
                  AND institution_row_count > 0
                ORDER BY degree_level ASC
                """,
                (rs, rowNum) -> {
                    AdmissionRequirementDTO dto = requirementValues(rs);
                    dto.setDegreeLevel(rs.getString("degree_level"));
                    dto.setSourceUrl(rs.getString("source_url"));
                    dto.setRequirementScope(rs.getString("requirement_scope"));
                    dto.setIntakeYear(nullableInteger(rs.getObject("intake_year")));
                    dto.setIntakeYearBasis(rs.getString("intake_year_basis"));
                    dto.setValuesDiffer(rs.getBoolean("values_differ"));
                    return dto;
                },
                canonicalUniversityId
        );

        List<AdmissionRequirementDTO> programmes = jdbcTemplate.query(
                """
                SELECT
                    degree_level,
                    faculty,
                    programme_name,
                    requirement_scope,
                    intake_year,
                    intake_year_basis,
                    ielts_requirement,
                    toefl_requirement,
                    duolingo_requirement,
                    gpa_requirement,
                    application_deadline,
                    source_url
                FROM warehouse.admission_record
                WHERE canonical_university_id = ?
                  AND requirement_scope IN ('programme', 'faculty')
                ORDER BY degree_level ASC, faculty ASC NULLS FIRST, programme_name ASC NULLS FIRST,
                         intake_year DESC NULLS LAST
                """,
                (rs, rowNum) -> {
                    AdmissionRequirementDTO dto = requirementValues(rs);
                    dto.setDegreeLevel(rs.getString("degree_level"));
                    dto.setFaculty(rs.getString("faculty"));
                    dto.setProgrammeName(rs.getString("programme_name"));
                    dto.setRequirementScope(rs.getString("requirement_scope"));
                    dto.setIntakeYear(nullableInteger(rs.getObject("intake_year")));
                    dto.setIntakeYearBasis(rs.getString("intake_year_basis"));
                    dto.setSourceUrl(rs.getString("source_url"));
                    return dto;
                },
                canonicalUniversityId
        );

        Optional<AdmissionSummaryRow> summaryRow = findSummaryRow(canonicalUniversityId);
        if (levels.isEmpty() && programmes.isEmpty()) {
            return withoutData();
        }

        AdmissionRequirementsDTO dto = new AdmissionRequirementsDTO();
        dto.setHasData(true);
        dto.setDegreeLevelCount(levels.size());
        dto.setByDegreeLevel(levels);
        dto.setProgrammeRequirements(programmes);
        dto.setSummary(summarise(levels));
        dto.setCaveats(AdmissionCaveats.forSummary(summaryRow));
        summaryRow.ifPresent(row -> {
            dto.setFetchDatesRecorded(row.fetchDatesRecorded());
            dto.setOldestFetchedOn(row.oldestFetchedOn() == null ? null : row.oldestFetchedOn().toString());
            dto.setOldestExtractedOn(row.oldestExtractedOn() == null ? null : row.oldestExtractedOn().toString());
        });
        return dto;
    }

    /**
     * The summary-view row for one university, or empty when it has no admission
     * row at all -- which {@link AdmissionCaveats#forSummary} reads as an IELTS gap.
     */
    public Optional<AdmissionSummaryRow> findSummaryRow(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return Optional.empty();
        }
        return jdbcTemplate.query(
                SUMMARY_SELECT + " WHERE canonical_university_id = ?",
                (rs, rowNum) -> summaryRow(rs),
                canonicalUniversityId
        ).stream().findFirst();
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
                SUMMARY_SELECT + " WHERE canonical_university_id IN (%s)".formatted(placeholders),
                rs -> {
                    while (rs.next()) {
                        AdmissionSummaryRow row = summaryRow(rs);
                        AdmissionRequirementDTO dto = new AdmissionRequirementDTO();
                        // Deliberately no degreeLevel: this row spans every level
                        // the university publishes, so naming one would be a lie.
                        dto.setIeltsRequirement(row.ieltsRequirement());
                        dto.setToeflRequirement(row.toeflRequirement());
                        dto.setDuolingoRequirement(row.duolingoRequirement());
                        dto.setGpaRequirement(row.gpaRequirement());
                        dto.setApplicationDeadline(row.applicationDeadline());
                        summaries.put(rs.getLong("canonical_university_id"), dto);
                    }
                    return null;
                },
                canonicalUniversityIds.toArray()
        );

        return summaries;
    }

    private static final String SUMMARY_SELECT = """
            SELECT
                canonical_university_id,
                ielts_requirement,
                toefl_requirement,
                duolingo_requirement,
                gpa_requirement,
                application_deadline,
                degree_level_count,
                programme_row_count,
                values_differ,
                ielts_missing,
                fetch_dates_recorded,
                oldest_fetched_on,
                oldest_extracted_on
            FROM warehouse.v_admission_requirement_summary
            """;

    private static AdmissionSummaryRow summaryRow(ResultSet rs) throws SQLException {
        return new AdmissionSummaryRow(
                nullableDouble(rs.getObject("ielts_requirement")),
                nullableInteger(rs.getObject("toefl_requirement")),
                nullableInteger(rs.getObject("duolingo_requirement")),
                nullableDouble(rs.getObject("gpa_requirement")),
                isoDate(rs.getObject("application_deadline")),
                rs.getInt("degree_level_count"),
                rs.getInt("programme_row_count"),
                rs.getBoolean("values_differ"),
                rs.getBoolean("ielts_missing"),
                rs.getBoolean("fetch_dates_recorded"),
                rs.getObject("oldest_fetched_on", LocalDate.class),
                rs.getObject("oldest_extracted_on", LocalDate.class)
        );
    }

    private static AdmissionRequirementDTO requirementValues(ResultSet rs) throws SQLException {
        AdmissionRequirementDTO dto = new AdmissionRequirementDTO();
        dto.setIeltsRequirement(nullableDouble(rs.getObject("ielts_requirement")));
        dto.setToeflRequirement(nullableInteger(rs.getObject("toefl_requirement")));
        dto.setDuolingoRequirement(nullableInteger(rs.getObject("duolingo_requirement")));
        dto.setGpaRequirement(nullableDouble(rs.getObject("gpa_requirement")));
        dto.setApplicationDeadline(isoDate(rs.getObject("application_deadline")));
        return dto;
    }

    private static AdmissionRequirementsDTO withoutData() {
        AdmissionRequirementsDTO dto = AdmissionRequirementsDTO.empty();
        dto.setCaveats(AdmissionCaveats.forSummary(Optional.empty()));
        return dto;
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
