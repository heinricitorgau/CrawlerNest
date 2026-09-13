package clawer.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The same cases as TestInstitutionLineageWithholds in test_rank_delta.py, against
 * the two mergers the warehouse holds and the canonical ids they resolve to.
 */
class RankComparisonPolicyTest {

    private static final long TOKYO_TECH = 85;
    private static final long TMDU = 668;
    private static final long ADELAIDE = 82;
    private static final long UNISA = 339;

    private static final List<InstitutionLineage.Event> LINEAGE = List.of(
            new InstitutionLineage.Event(TMDU, TOKYO_TECH, 2024, "merger"),
            new InstitutionLineage.Event(UNISA, ADELAIDE, 2026, "merger"));

    @Test
    @DisplayName("both sides of a merger are withheld as entity_changed")
    void mergerWithholdsBothRecords() {
        assertEquals(RankComparisonPolicy.REASON_ENTITY_CHANGED,
                RankComparisonPolicy.withholdReason(TOKYO_TECH, 2025, 2026, LINEAGE));
        assertEquals(RankComparisonPolicy.REASON_ENTITY_CHANGED,
                RankComparisonPolicy.withholdReason(TMDU, 2025, 2026, LINEAGE));
    }

    @Test
    @DisplayName("an unrelated university is still not given a composite delta")
    void unrelatedUniversityGetsTheCompositeReason() {
        assertEquals(RankComparisonPolicy.REASON_COMPOSITE_RANK_NOT_COMPARABLE,
                RankComparisonPolicy.withholdReason(12345, 2025, 2026, LINEAGE));
    }

    @Test
    @DisplayName("a single held edition reports the dataset reason")
    void singleEditionReportsTheDatasetReason() {
        assertEquals(RankComparisonPolicy.REASON_SINGLE_YEAR_DATASET,
                RankComparisonPolicy.withholdReason(TOKYO_TECH, null, 2026, LINEAGE));
    }

    @Test
    @DisplayName("the window reaches one edition label back, and over-withholds rather than under")
    void windowEdges() {
        assertTrue(InstitutionLineage.boundary(TOKYO_TECH, 2025, 2026, LINEAGE).isPresent());
        assertTrue(InstitutionLineage.boundary(TOKYO_TECH, 2026, 2027, LINEAGE).isEmpty());
        assertTrue(InstitutionLineage.boundary(ADELAIDE, 2026, 2027, LINEAGE).isPresent());
        assertTrue(InstitutionLineage.boundary(ADELAIDE, 2027, 2028, LINEAGE).isPresent());
        assertTrue(InstitutionLineage.boundary(ADELAIDE, 2028, 2029, LINEAGE).isEmpty());
    }

    @Test
    @DisplayName("a record whose institution changed in place is on its own boundary")
    void selfLineageCounts() {
        List<InstitutionLineage.Event> rename = List.of(new InstitutionLineage.Event(TOKYO_TECH, TOKYO_TECH, 2024, "rename"));
        assertTrue(InstitutionLineage.boundary(TOKYO_TECH, 2025, 2026, rename).isPresent());
    }

    @Test
    @DisplayName("the prior edition must precede the current one")
    void priorMustPrecedeCurrent() {
        assertThrows(IllegalArgumentException.class,
                () -> InstitutionLineage.boundary(TOKYO_TECH, 2026, 2026, LINEAGE));
    }
}
