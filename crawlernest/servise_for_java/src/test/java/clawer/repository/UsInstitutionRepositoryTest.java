package clawer.repository;

import clawer.dto.UsInstitutionDTO;
import clawer.service.AnalyticsService;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** Which caveats a set of US federal values carries. Mirrors us_federal_caveats in crawlernest/core/caveats.py. */
class UsInstitutionRepositoryTest {

    private static UsInstitutionDTO.Metric metric(String key, String status) {
        BigDecimal value = "reported".equals(status) || "imputed".equals(status) ? BigDecimal.ONE : null;
        return new UsInstitutionDTO.Metric("COLLEGE_SCORECARD", key, "F", "usd", value, null, status, null, "p", "r");
    }

    @Test
    void theSourceAndPeriodCaveatsAreAlwaysCarried() {
        assertEquals(List.of(AnalyticsService.US_FEDERAL_SOURCE_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT),
                UsInstitutionRepository.caveatsFor(List.of(metric("admission_rate", "reported"))));
    }

    @Test
    void theAidCaveatComesOnlyWithAnEarningsOrDebtFigureThatIsShown() {
        assertEquals(3, UsInstitutionRepository.caveatsFor(List.of(metric("median_earnings_10yr", "reported"))).size());
        // A withheld earnings figure shows no earnings, so the aid caveat would describe nothing on the page.
        assertEquals(List.of(AnalyticsService.US_FEDERAL_SOURCE_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT,
                        AnalyticsService.US_FEDERAL_SUPPRESSED_CAVEAT),
                UsInstitutionRepository.caveatsFor(List.of(metric("median_earnings_10yr", "privacy_suppressed"))));
    }

    @Test
    void suppressedAndImputedEachBringTheirOwnCaveatInAFixedOrder() {
        assertEquals(List.of(AnalyticsService.US_FEDERAL_SOURCE_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT,
                        AnalyticsService.US_FEDERAL_AID_RECIPIENTS_CAVEAT, AnalyticsService.US_FEDERAL_SUPPRESSED_CAVEAT,
                        AnalyticsService.US_FEDERAL_IMPUTED_CAVEAT),
                UsInstitutionRepository.caveatsFor(List.of(metric("applicants_total", "imputed"),
                        metric("x", "privacy_suppressed"), metric("median_debt_completers", "imputed"))));
    }
}
