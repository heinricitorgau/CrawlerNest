package clawer.service;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** A filter on figures: no figure is never a pass, and every exclusion is counted under its reason. */
class UsFederalFilterTest {

    private static final String NET = UsFederalFilter.METRIC_NET_PRICE;
    private static final String ADM = UsFederalFilter.METRIC_ADMISSION_RATE;

    private static Object[] fig(Object value, String status) {
        return new Object[] {value, status, "AcadYr 2024-25"};
    }

    private final Map<Long, Map<String, Object[]>> rows = Map.of(
            1L, Map.of(NET, fig(20000, "reported"), ADM, fig(0.30, "reported")),
            2L, Map.of(NET, fig(45000, "reported"), ADM, fig(0.05, "reported")),
            3L, Map.of(NET, fig(null, "not_available"), ADM, fig(0.50, "reported")),
            4L, Map.of(NET, fig(15000, "imputed"), ADM, fig(0.80, "imputed")),
            5L, Map.of());

    @Test
    void noBoundsMeansNoFilterAndNothingCounted() {
        UsFederalFilter filter = UsFederalFilter.none();
        assertFalse(filter.active());
        assertTrue(filter.keeps(99L));
        assertEquals(Map.of("applied", false), filter.describe());
    }

    @Test
    void aNetPriceCapKeepsOnlyFiguresUnderItAndCountsEveryExclusionByReason() {
        UsFederalFilter filter = UsFederalFilter.forTest(30000, null, null, rows);
        assertTrue(filter.keeps(1L));
        assertFalse(filter.keeps(2L));   // over the cap
        assertFalse(filter.keeps(3L));   // no figure: never read as 0
        assertTrue(filter.keeps(4L));    // NCES-imputed counts as a figure
        assertFalse(filter.keeps(5L));   // a federal record without the metric
        assertFalse(filter.keeps(99L));  // outside the US, or not tied to a UNITID

        Map<String, Object> described = filter.describe();
        assertEquals(2, described.get("kept"));
        assertEquals(Map.of(
                UsFederalFilter.REASON_OUTSIDE_RANGE, 1,
                UsFederalFilter.REASON_FIGURE_NOT_REPORTED, 2,
                UsFederalFilter.REASON_NO_FEDERAL_RECORD, 1), described.get("excluded"));
        assertEquals(List.of(AnalyticsService.US_FEDERAL_FILTER_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT),
                described.get("caveats"));
        assertEquals(Map.of(NET, "AcadYr 2024-25"), described.get("reference_periods"));
    }

    @Test
    void anAdmissionRateRangeIsInclusiveAndCombinesWithTheCap() {
        UsFederalFilter filter = UsFederalFilter.forTest(30000, 0.30, 0.90, rows);
        assertTrue(filter.keeps(1L));    // 0.30 is inside an inclusive range
        assertFalse(filter.keeps(2L));
        assertTrue(filter.keeps(4L));
    }

    @Test
    void impossibleBoundsAreRefused() {
        assertThrows(IllegalArgumentException.class, () -> UsFederalFilter.forTest(-1, null, null, rows));
        assertThrows(IllegalArgumentException.class, () -> UsFederalFilter.forTest(null, 1.5, null, rows));
        assertThrows(IllegalArgumentException.class, () -> UsFederalFilter.forTest(null, 0.8, 0.2, rows));
    }
}
