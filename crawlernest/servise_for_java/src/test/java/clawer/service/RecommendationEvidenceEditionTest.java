package clawer.service;

import clawer.repository.AdmissionRecordRepository;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * The explain evidence reads the edition the page shows.
 *
 * <p>It used to read {@code defaultRankingYear()} unconditionally, so a page showing
 * 2025 recommendations opened explanations built from the 2026 ranking row -- and the
 * agent, handed those, would describe a different edition than the table beside it.
 */
class RecommendationEvidenceEditionTest {

    private static final long UNIVERSITY = 42L;

    @Test
    void theRequestedEditionIsTheOneRead() {
        RecordingJdbc jdbc = new RecordingJdbc();
        Map<String, Object> evidence = service(jdbc).getEvidence(UNIVERSITY, null, null, null, null, 2025);

        assertEquals(List.of(2025), jdbc.rankingYearsQueried);
        assertEquals(2025, evidence.get("ranking_year_requested"));
        assertEquals(2025, ((Map<?, ?>) evidence.get("ranking_evidence")).get("ranking_year"));
    }

    @Test
    void noEditionReadsTheDefaultAsBefore() {
        RecordingJdbc jdbc = new RecordingJdbc();
        service(jdbc).getEvidence(UNIVERSITY, null, null, null, null);

        assertEquals(List.of(DatasetScope.DEFAULT_RANKING_YEAR), jdbc.rankingYearsQueried);
    }

    @Test
    void anEditionTheReleaseDoesNotHoldIsRefusedNotSubstituted() {
        RecordingJdbc jdbc = new RecordingJdbc();
        IllegalArgumentException refused = assertThrows(IllegalArgumentException.class,
                () -> service(jdbc).getEvidence(UNIVERSITY, null, null, null, null, 1999));

        assertTrue(refused.getMessage().contains("1999"), refused.getMessage());
        assertTrue(jdbc.rankingYearsQueried.isEmpty(), "nothing is read for an edition that is not held");
    }

    private static RecommendationEvidenceService service(JdbcTemplate jdbc) {
        AdmissionRecordRepository admissions = mock(AdmissionRecordRepository.class);
        when(admissions.findSummaryRow(anyLong())).thenReturn(Optional.empty());
        return new RecommendationEvidenceService(jdbc, DatasetScope.standard(), admissions);
    }

    /** Answers the identity and ranking lookups, recording the edition each ranking read names. */
    private static final class RecordingJdbc extends JdbcTemplate {
        final List<Integer> rankingYearsQueried = new ArrayList<>();

        @Override
        public List<Map<String, Object>> queryForList(String sql, Object... args) {
            Map<String, Object> row = new LinkedHashMap<>();
            if (sql.contains("analytics.aggregated_rankings")) {
                int year = ((Number) args[1]).intValue();
                rankingYearsQueried.add(year);
                row.put("display_rank", 7);
                row.put("ranking_year", year);
                row.put("composite_score", 88.0);
                row.put("coverage_ratio", 1.0);
                row.put("aggregation_method_version", "test");
                row.put("source_ranks_json", "{\"QS\": 7, \"THE\": 9, \"ARWU\": 11}");
                return List.of(row);
            }
            row.put("canonical_university_id", UNIVERSITY);
            row.put("display_name", "Test University");
            row.put("canonical_slug", "test-university");
            row.put("country_name", "Nowhere");
            row.put("country_code", "NW");
            return List.of(row);
        }
    }
}
