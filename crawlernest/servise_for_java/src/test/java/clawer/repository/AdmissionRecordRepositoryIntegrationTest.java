package clawer.repository;

import clawer.dto.AdmissionRequirementDTO;
import clawer.dto.AdmissionRequirementsDTO;
import clawer.service.AnalyticsService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Exercises the structured admission columns against a real PostgreSQL instance.
 *
 * <p>Shares the university preview fixtures, which seed canonical university
 * 990102 with two degree levels chosen so that every requirement column is NULL
 * on at least one of them.
 */
@SpringBootTest
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/university_preview_integration_setup.sql",
                        "classpath:sql/university_preview_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = "classpath:sql/university_preview_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class AdmissionRecordRepositoryIntegrationTest {

    private static final long MIT = 990102L;
    private static final long OXFORD_WITHOUT_ADMISSIONS = 990103L;

    @Autowired
    private AdmissionRecordRepository repository;

    @Test
    void readsOneEntryPerDegreeLevel() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(MIT);

        assertTrue(admissions.isHasData());
        assertEquals(2, admissions.getDegreeLevelCount());
        assertEquals(
                List.of("postgraduate", "undergraduate"),
                admissions.getByDegreeLevel().stream().map(AdmissionRequirementDTO::getDegreeLevel).toList()
        );
    }

    @Test
    void keepsUnpublishedRequirementsNullRatherThanZero() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(MIT);

        AdmissionRequirementDTO undergraduate = admissions.getByDegreeLevel().stream()
                .filter(level -> "undergraduate".equals(level.getDegreeLevel()))
                .findFirst()
                .orElseThrow();

        // The undergraduate page publishes a GPA bar and no English test. Reading
        // those absences as 0.0 would present the easiest entry requirements in
        // the dataset.
        assertNull(undergraduate.getIeltsRequirement());
        assertNull(undergraduate.getToeflRequirement());
        assertNull(undergraduate.getDuolingoRequirement());
        assertEquals(3.7, undergraduate.getGpaRequirement());
    }

    @Test
    void summaryTakesTheLowestPublishedBarAcrossLevels() {
        AdmissionRequirementDTO summary = repository.findByCanonicalUniversityId(MIT).getSummary();

        // Only the postgraduate row publishes these, so the NULLs on the
        // undergraduate row must not win the minimum.
        assertEquals(7.0, summary.getIeltsRequirement());
        assertEquals(100, summary.getToeflRequirement());
        assertEquals(125, summary.getDuolingoRequirement());
        // Only the undergraduate row publishes a GPA.
        assertEquals(3.7, summary.getGpaRequirement());
        // Earliest of the two deadlines, not the last row read.
        assertEquals("2026-01-15", summary.getApplicationDeadline());
    }

    @Test
    void aProgrammeRowIsListedButNeverFoldedIntoUniversityLevelFigures() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(MIT);

        // The seed's programme row asks for IELTS 5.5 and TOEFL 70. A MIN() over
        // the table would have quoted those as MIT's requirements.
        AdmissionRequirementDTO postgraduate = admissions.getByDegreeLevel().stream()
                .filter(level -> "postgraduate".equals(level.getDegreeLevel()))
                .findFirst()
                .orElseThrow();
        assertEquals(7.0, postgraduate.getIeltsRequirement());
        assertEquals(100, postgraduate.getToeflRequirement());
        assertEquals("unspecified", postgraduate.getRequirementScope());
        assertEquals(7.0, admissions.getSummary().getIeltsRequirement());

        assertEquals(1, admissions.getProgrammeRequirements().size());
        AdmissionRequirementDTO programme = admissions.getProgrammeRequirements().get(0);
        assertEquals("MEng Computation", programme.getProgrammeName());
        assertEquals("School of Engineering", programme.getFaculty());
        assertEquals(5.5, programme.getIeltsRequirement());
        assertEquals(2027, programme.getIntakeYear());
        assertEquals("page_stated", programme.getIntakeYearBasis());
    }

    @Test
    void staleDataIsDisclosedWithTheExtractionDateWhenFetchDatesWereNotAllRecorded() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(MIT);

        // The programme row records a fetch; the two university-level rows do not.
        // So the caveat names the oldest extraction and says the fetch date is
        // unknown, rather than presenting the one recorded fetch as covering all.
        assertEquals(Boolean.FALSE, admissions.getFetchDatesRecorded());
        assertEquals(
                List.of(AnalyticsService.ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", "2026-04-14")),
                admissions.getCaveats()
        );
    }

    @Test
    void universityWithoutAdmissionRecordsReportsNoData() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(OXFORD_WITHOUT_ADMISSIONS);

        assertNotNull(admissions);
        assertFalse(admissions.isHasData());
        assertEquals(0, admissions.getDegreeLevelCount());
        assertTrue(admissions.getByDegreeLevel().isEmpty());
        assertNotNull(admissions.getSummary());
        // No admission row at all is itself an IELTS gap, and nothing is stale.
        assertEquals(List.of(AnalyticsService.IELTS_MISSING_CAVEAT), admissions.getCaveats());
    }

    @Test
    void nullCanonicalIdReturnsEmptyRatherThanThrowing() {
        AdmissionRequirementsDTO admissions = repository.findByCanonicalUniversityId(null);

        assertNotNull(admissions);
        assertFalse(admissions.isHasData());
    }

    @Test
    void batchSummariesSkipUniversitiesWithNoRecords() {
        Map<Long, AdmissionRequirementDTO> summaries =
                repository.findSummariesByCanonicalUniversityIds(List.of(MIT, OXFORD_WITHOUT_ADMISSIONS));

        assertEquals(1, summaries.size());
        assertTrue(summaries.containsKey(MIT));
        // Absent rather than present-with-nulls, so a caller can tell the two apart.
        assertFalse(summaries.containsKey(OXFORD_WITHOUT_ADMISSIONS));
        assertEquals(7.0, summaries.get(MIT).getIeltsRequirement());
        assertEquals("2026-01-15", summaries.get(MIT).getApplicationDeadline());
    }

    @Test
    void emptyBatchIssuesNoQuery() {
        assertTrue(repository.findSummariesByCanonicalUniversityIds(List.of()).isEmpty());
        assertTrue(repository.findSummariesByCanonicalUniversityIds(null).isEmpty());
    }
}
