package clawer.service;

import java.util.Collection;
import java.util.Optional;
import java.util.Set;

/**
 * Structural changes to institutions, and when they make two editions incomparable.
 *
 * <p>Mirrors {@code crawlernest/core/institution_lineage.py}; the rule and its
 * reasoning are documented there and in
 * {@code crawlernest-schema/institution_lineage_postgresql.sql}. Both
 * implementations are tested against the same cases.
 */
public final class InstitutionLineage {

    /** The kinds {@code warehouse.institution_lineage.kind} allows. */
    public static final Set<String> KINDS = Set.of("merger", "split", "rename");

    /**
     * How far an edition's label can run ahead of the institutional state it
     * describes. QS and THE label an edition a year after they publish it, so the
     * 2026 edition can describe an institution as it stood in 2025. Widening the
     * window by this much withholds, at worst, one comparison that was in fact
     * sound -- the safe direction to be wrong in.
     */
    public static final int EDITION_LAG_YEARS = 1;

    private InstitutionLineage() {
    }

    /** One row of {@code warehouse.institution_lineage}. */
    public record Event(long predecessorCanonicalId, long successorCanonicalId, int effectiveYear, String kind) {
        public boolean involves(long canonicalUniversityId) {
            return predecessorCanonicalId == canonicalUniversityId || successorCanonicalId == canonicalUniversityId;
        }
    }

    /**
     * The event that puts a boundary between {@code priorYear} and
     * {@code currentYear} for this university, if any.
     *
     * <p>A university is on the boundary when it is either side of an event whose
     * effective year falls inside the compared window, widened by
     * {@link #EDITION_LAG_YEARS} on the prior side.
     */
    public static Optional<Event> boundary(
            long canonicalUniversityId,
            int priorYear,
            int currentYear,
            Collection<Event> events
    ) {
        if (priorYear >= currentYear) {
            throw new IllegalArgumentException("priorYear " + priorYear + " must precede currentYear " + currentYear);
        }
        int windowStart = priorYear - EDITION_LAG_YEARS;
        return events.stream()
                .filter(event -> event.involves(canonicalUniversityId))
                .filter(event -> event.effectiveYear() >= windowStart && event.effectiveYear() <= currentYear)
                .findFirst();
    }
}
