package clawer.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.OptionalInt;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The edition rule every serving read goes through; mirrors resolve_ranking_year in Python. */
class DatasetScopeTest {

    @Test
    @DisplayName("no year reads the default edition, the newest held")
    void noYearReadsTheDefault() {
        DatasetScope scope = new DatasetScope("2025,2026");

        assertEquals(OptionalInt.of(2026), scope.resolveRankingYear(null));
        assertEquals(2026, scope.defaultRankingYear());
    }

    @Test
    @DisplayName("a held year reads that year")
    void heldYearReadsItself() {
        DatasetScope scope = new DatasetScope("2025,2026");

        assertEquals(OptionalInt.of(2025), scope.resolveRankingYear(2025));
    }

    @Test
    @DisplayName("a year not held -- a shadow edition included -- reads nothing")
    void unheldYearReadsNothing() {
        DatasetScope scope = new DatasetScope("2026");

        assertTrue(scope.resolveRankingYear(2025).isEmpty());
        assertTrue(scope.resolveRankingYear(2027).isEmpty());
        assertFalse(scope.isHeld(2025));
    }

    @Test
    @DisplayName("without configuration the release's editions apply")
    void standardScopeIsTheReleaseList() {
        DatasetScope scope = DatasetScope.standard();

        assertEquals(DatasetScope.DATASET_YEARS, scope.heldYears());
        assertEquals(DatasetScope.DEFAULT_RANKING_YEAR, scope.defaultRankingYear());
        assertEquals(DatasetScope.DATASET_YEARS, new DatasetScope("  ").heldYears());
    }

    @Test
    @DisplayName("held years are newest first and render as a PostgreSQL array literal")
    void heldYearsAreOrderedAndBindable() {
        DatasetScope scope = new DatasetScope("2024, 2026,2025,2026");

        assertEquals(List.of(2026, 2025, 2024), scope.heldYears());
        assertEquals("{2026,2025,2024}", scope.heldYearsSqlArray());
    }
}
