package clawer.service;

import java.util.Collection;

/**
 * Why a rank movement is not reported, for the one Java surface that pairs two
 * editions: the ranking-trends endpoint.
 *
 * <p>It never produces a number. The endpoint compares {@code display_rank}, the
 * composite position among the universities this platform holds, and that moves
 * whenever source coverage moves -- a delta between a QS-only edition and a
 * QS+THE+ARWU edition would mostly measure our ingest and report it as the
 * university's. {@code crawlernest/core/rank_delta.py} computes movement per
 * source, with band intervals; exposing that is Phase 4. Until then this says, per
 * row, which of the reasons applies.
 *
 * <p>The first two codes are the same strings as {@code REASON_SINGLE_YEAR_DATASET}
 * and {@code REASON_ENTITY_CHANGED} in {@code rank_delta.py};
 * {@code test_caveat_contract.py} checks they have not drifted.
 *
 * <p>Deliberately not named {@code RankDeltaCalculator}: an uncommitted file of
 * that name in the main checkout computes a composite delta, and a tracked file
 * at the same path would collide with it rather than replace it.
 */
public final class RankComparisonPolicy {

    /** Only one edition is held, so there is nothing to compare against. */
    public static final String REASON_SINGLE_YEAR_DATASET = "single_year_dataset";

    /** An institution-lineage event separates the two editions. */
    public static final String REASON_ENTITY_CHANGED = "entity_changed";

    /** Both editions exist, but a composite rank is not comparable across them. */
    public static final String REASON_COMPOSITE_RANK_NOT_COMPARABLE = "composite_rank_not_comparable";

    private RankComparisonPolicy() {
    }

    /**
     * The reason no movement is reported for one university.
     *
     * @param priorYear the edition compared against, or {@code null} when only one is held
     */
    public static String withholdReason(
            long canonicalUniversityId,
            Integer priorYear,
            int currentYear,
            Collection<InstitutionLineage.Event> lineage
    ) {
        if (priorYear == null) {
            return REASON_SINGLE_YEAR_DATASET;
        }
        if (InstitutionLineage.boundary(canonicalUniversityId, priorYear, currentYear, lineage).isPresent()) {
            return REASON_ENTITY_CHANGED;
        }
        return REASON_COMPOSITE_RANK_NOT_COMPARABLE;
    }
}
