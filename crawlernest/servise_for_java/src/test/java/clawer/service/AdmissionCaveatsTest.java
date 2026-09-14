package clawer.service;

import clawer.repository.AdmissionSummaryRow;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The admission caveat rule, on the same cases test_caveat_contract.py and
 * admissionCaveats.test.ts hold Python and TypeScript to.
 */
class AdmissionCaveatsTest {

    private static AdmissionSummaryRow row(boolean ieltsMissing, boolean fetchDatesRecorded, LocalDate fetched, LocalDate extracted) {
        return new AdmissionSummaryRow(
                ieltsMissing ? null : 6.5, 90, null, null, null,
                1, 0, false, ieltsMissing, fetchDatesRecorded, fetched, extracted);
    }

    @Test
    void aRecordedFetchDateIsNamedAsTheFetchDate() {
        assertEquals(
                AnalyticsService.ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", "2026-03-01"),
                AnalyticsService.admissionStaleCaveat(true, LocalDate.of(2026, 3, 1), LocalDate.of(2026, 8, 22))
        );
    }

    @Test
    void anUnrecordedFetchIsNeverPassedOffAsTheExtractionDate() {
        String caveat = AnalyticsService.admissionStaleCaveat(false, LocalDate.of(2026, 3, 1), LocalDate.of(2026, 8, 22));
        assertEquals(AnalyticsService.ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", "2026-08-22"), caveat);
        assertTrue(caveat.contains("fetch date was not recorded"));
        assertFalse(caveat.contains("fetched on"));
    }

    @Test
    void noAdmissionDataMeansNoStalenessClaim() {
        assertNull(AnalyticsService.admissionStaleCaveat(true, null, null));
    }

    @Test
    void noSummaryRowIsAnIeltsGapAndNothingElse() {
        assertEquals(List.of(AnalyticsService.IELTS_MISSING_CAVEAT), AdmissionCaveats.forSummary(Optional.empty()));
    }

    @Test
    void aMissingIeltsFigureComesFirstThenStaleness() {
        List<String> caveats = AdmissionCaveats.forSummary(
                Optional.of(row(true, false, null, LocalDate.of(2026, 8, 22))));
        assertEquals(2, caveats.size());
        assertEquals(AnalyticsService.IELTS_MISSING_CAVEAT, caveats.get(0));
        assertTrue(caveats.get(1).contains("extracted on 2026-08-22"));
    }

    @Test
    void aUniversityWithIeltsCarriesOnlyTheStalenessCaveat() {
        assertEquals(
                List.of(AnalyticsService.ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", "2026-03-01")),
                AdmissionCaveats.forSummary(Optional.of(row(false, true, LocalDate.of(2026, 3, 1), LocalDate.of(2026, 8, 22))))
        );
    }
}
