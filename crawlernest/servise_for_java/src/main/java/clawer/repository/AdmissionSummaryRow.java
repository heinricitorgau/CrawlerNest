package clawer.repository;

import java.time.LocalDate;

/**
 * One row of {@code warehouse.v_admission_requirement_summary}: a university's
 * university-level requirements (lowest bar across degree levels), what they
 * leave out, and the staleness columns a caveat is rendered from.
 *
 * <p>The rule that produces it -- institution-scope rows only, newest stated
 * intake -- lives in that view, in crawlernest-schema/admission_postgresql.sql,
 * so Java, Python and the recommendation view cannot apply different ones.
 */
public record AdmissionSummaryRow(
        Double ieltsRequirement,
        Integer toeflRequirement,
        Integer duolingoRequirement,
        Double gpaRequirement,
        String applicationDeadline,
        int degreeLevelCount,
        int programmeRowCount,
        boolean valuesDiffer,
        boolean ieltsMissing,
        boolean fetchDatesRecorded,
        LocalDate oldestFetchedOn,
        LocalDate oldestExtractedOn
) {
}
