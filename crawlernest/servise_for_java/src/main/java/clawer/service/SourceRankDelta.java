package clawer.service;

import java.util.Collection;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * How far a university moved in one ranking source between two editions.
 *
 * <p>A port of {@code crawlernest/core/rank_delta.py}; the rules and why each
 * exists are documented there, and both implementations are pinned against the
 * same cases (see {@code test_rank_delta.py}'s Java checks and
 * {@code SourceRankDeltaTest}). In short:
 * <ul>
 *   <li>Per source only. There is no composite overload: {@code display_rank}
 *       moves when coverage moves, and the trends endpoint withholds it with
 *       {@link RankComparisonPolicy#REASON_COMPOSITE_RANK_NOT_COMPARABLE}.</li>
 *   <li>Ranks are read as the source printed them ("=98", "201–250", "1501+").
 *       {@code rank_position} is a band's lower bound, and for QS the endpoint's
 *       sort ordinal, so subtracting it states a precision no source published.
 *       A row whose printed rank is unavailable is withheld with
 *       {@link #REASON_RANK_DISPLAY_MISSING}.</li>
 *   <li>{@code delta = current - prior}; negative means up. Render
 *       {@link Result#direction()}, never the sign.</li>
 * </ul>
 */
public final class SourceRankDelta {

    public static final String DIRECTION_UP = "up";
    public static final String DIRECTION_DOWN = "down";
    public static final String DIRECTION_UNCHANGED = "unchanged";
    public static final String DIRECTION_INDETERMINATE = "indeterminate";

    public static final String REASON_SINGLE_YEAR_DATASET = RankComparisonPolicy.REASON_SINGLE_YEAR_DATASET;
    public static final String REASON_ENTITY_CHANGED = RankComparisonPolicy.REASON_ENTITY_CHANGED;
    public static final String REASON_NO_PRIOR_ROW = "no_prior_row";
    public static final String REASON_NO_CURRENT_ROW = "no_current_row";
    public static final String REASON_BANDED = "banded";
    public static final String REASON_SUSPICIOUS_MERGE = "suspicious_merge";
    public static final String REASON_RANK_DISPLAY_MISSING = "rank_display_missing";

    private static final Pattern EXACT = Pattern.compile("^=?\\s*(\\d+)$");
    private static final Pattern BAND = Pattern.compile("^(\\d+)\\s*[-–—]\\s*(\\d+)$");
    private static final Pattern OPEN = Pattern.compile("^(\\d+)\\s*\\+$");
    private static final Pattern YEAR_SEGMENT = Pattern.compile(":(?:19|20)\\d{2}(?=:)");

    private SourceRankDelta() {
    }

    /** A published rank as an interval; {@code upper} is null for an open band ("1501+"). */
    public record RankBand(int lower, Integer upper) {
        public boolean isExact() {
            return upper != null && upper == lower;
        }
    }

    /**
     * One source's row for one university in one edition.
     *
     * @param rankDisplay the rank as printed; null when the row has none recorded
     */
    public record Observation(int year, String source, String rankDisplay, String sourceEntityId, boolean suspiciousMerge) {
    }

    /**
     * The movement, or why there is none. {@code value} only when both ranks are
     * exact; {@code min}/{@code max} bound it whenever it is bounded; {@code reason}
     * explains every null and is {@code banded} when only the interval is known.
     */
    public record Result(String source, int currentYear, int priorYear, Integer value, Integer min, Integer max,
                         String direction, String reason) {
        static Result withheld(String source, int currentYear, int priorYear, String reason) {
            return new Result(source, currentYear, priorYear, null, null, null, null, reason);
        }

        /** True when there is a movement (exact or banded) to show at all. */
        public boolean compared() {
            return direction != null;
        }
    }

    public static RankBand parseRankBand(String value) {
        if (value == null) {
            return null;
        }
        String text = value.strip();
        Matcher m = EXACT.matcher(text);
        if (m.matches()) {
            int position = Integer.parseInt(m.group(1));
            return position > 0 ? new RankBand(position, position) : null;
        }
        m = BAND.matcher(text);
        if (m.matches()) {
            int lower = Integer.parseInt(m.group(1));
            int upper = Integer.parseInt(m.group(2));
            return lower > 0 && lower <= upper ? new RankBand(lower, upper) : null;
        }
        m = OPEN.matcher(text);
        if (m.matches()) {
            int lower = Integer.parseInt(m.group(1));
            return lower > 0 ? new RankBand(lower, null) : null;
        }
        return null;
    }

    public static String stableSourceIdentity(String sourceEntityId) {
        if (sourceEntityId == null) {
            return null;
        }
        String stripped = YEAR_SEGMENT.matcher(sourceEntityId.strip()).replaceAll("");
        return stripped.isEmpty() ? null : stripped;
    }

    /**
     * Movement from {@code priorYear} to {@code current.year()} for one source.
     *
     * @param current     this edition's row; required -- a university with no current row has no delta to show
     * @param prior       the prior edition's row for the same source, or null when we hold none
     * @param heldYears   the editions the release holds ({@link DatasetScope#heldYears()})
     * @param lineage     every {@code warehouse.institution_lineage} event naming this university
     */
    public static Result compute(
            Observation current,
            Observation prior,
            int priorYear,
            long canonicalUniversityId,
            Collection<InstitutionLineage.Event> lineage,
            Collection<Integer> heldYears
    ) {
        if (priorYear >= current.year()) {
            throw new IllegalArgumentException("priorYear " + priorYear + " must precede " + current.year());
        }
        if (prior != null) {
            if (prior.year() != priorYear) {
                throw new IllegalArgumentException("prior observation is for " + prior.year() + ", not " + priorYear);
            }
            if (!prior.source().equals(current.source())) {
                throw new IllegalArgumentException("cannot compare " + current.source() + " with " + prior.source());
            }
        }
        String source = current.source();
        int currentYear = current.year();

        if (!heldYears.contains(priorYear)) {
            return Result.withheld(source, currentYear, priorYear, REASON_SINGLE_YEAR_DATASET);
        }
        if (InstitutionLineage.boundary(canonicalUniversityId, priorYear, currentYear, lineage).isPresent()) {
            return Result.withheld(source, currentYear, priorYear, REASON_ENTITY_CHANGED);
        }
        if (prior == null) {
            return Result.withheld(source, currentYear, priorYear, REASON_NO_PRIOR_ROW);
        }
        RankBand c = parseRankBand(current.rankDisplay());
        RankBand p = parseRankBand(prior.rankDisplay());
        if (c == null || p == null) {
            return Result.withheld(source, currentYear, priorYear, REASON_RANK_DISPLAY_MISSING);
        }
        if (current.suspiciousMerge() || prior.suspiciousMerge()) {
            return Result.withheld(source, currentYear, priorYear, REASON_SUSPICIOUS_MERGE);
        }
        String currentIdentity = stableSourceIdentity(current.sourceEntityId());
        String priorIdentity = stableSourceIdentity(prior.sourceEntityId());
        if (currentIdentity != null && priorIdentity != null && !currentIdentity.equals(priorIdentity)) {
            return Result.withheld(source, currentYear, priorYear, REASON_ENTITY_CHANGED);
        }

        if (c.isExact() && p.isExact()) {
            int exact = c.lower() - p.lower();
            return new Result(source, currentYear, priorYear, exact, exact, exact, direction(exact, exact, exact), null);
        }
        Integer min = p.upper() == null ? null : c.lower() - p.upper();
        Integer max = c.upper() == null ? null : c.upper() - p.lower();
        return new Result(source, currentYear, priorYear, null, min, max, direction(min, max, null), REASON_BANDED);
    }

    private static String direction(Integer min, Integer max, Integer exact) {
        if (exact != null) {
            return exact < 0 ? DIRECTION_UP : exact > 0 ? DIRECTION_DOWN : DIRECTION_UNCHANGED;
        }
        if (max != null && max < 0) {
            return DIRECTION_UP;
        }
        if (min != null && min > 0) {
            return DIRECTION_DOWN;
        }
        return DIRECTION_INDETERMINATE;
    }
}
