package clawer.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.OptionalInt;
import java.util.stream.Collectors;

/**
 * Which ranking editions a read is allowed to see.
 *
 * <p>Every multi-year relation -- {@code analytics.aggregated_rankings},
 * {@code v_aggregated_rankings_latest}, {@code v_recommendation_candidates_latest},
 * {@code warehouse.ranking_record}, the model predictions -- holds one row per
 * university <em>per edition</em>. A read that does not name an edition reads all
 * of them, and three things go wrong the moment a second edition is loaded: each
 * university appears once per edition, "the newest row for this university"
 * silently becomes an older edition's rank for any university the current edition
 * lacks, and an edition loaded but not yet released (a shadow ingest) is served as
 * if it were live.
 *
 * <p>So no serving read decides its own edition. It asks this:
 * <ul>
 *   <li>no year requested: the default edition, the newest one held;</li>
 *   <li>a held year requested: that year;</li>
 *   <li>any other year: nothing. The caller returns an empty result rather than
 *       querying, so a shadow edition is invisible even to {@code ?year=2025}.
 *       There is no exception: nothing maps one to a 4xx here, and an empty result
 *       is what a year with no rows has always returned.</li>
 * </ul>
 *
 * <p>{@link #DATASET_YEARS} is the release's list and mirrors
 * {@code crawlernest/core/dataset.py}; {@code test_caveat_contract.py} compares
 * the literals. The {@code crawlernest.dataset.years} property exists for
 * integration tests, whose fixtures live in an edition no crawl writes (2099) so
 * that the live warehouse they run against cannot leak into their assertions.
 * Setting it in production would contradict the caveats, which render from the
 * static list.
 */
@Component
public class DatasetScope {

    /** Every ranking edition the warehouse holds, newest first. Changing it is a data migration. */
    public static final List<Integer> DATASET_YEARS = List.of(2026, 2025);

    /** The edition a read uses when the caller names none. */
    public static final int DEFAULT_RANKING_YEAR = Collections.max(DATASET_YEARS);

    private final List<Integer> heldYears;
    private final int defaultRankingYear;

    /** The release's editions. */
    public DatasetScope() {
        this("");
    }

    @Autowired
    public DatasetScope(@Value("${crawlernest.dataset.years:}") String override) {
        List<Integer> years = parse(override);
        this.heldYears = years.isEmpty() ? DATASET_YEARS : years;
        this.defaultRankingYear = Collections.max(this.heldYears);
    }

    /** The scope a test or a non-Spring caller gets without configuration. */
    public static DatasetScope standard() {
        return new DatasetScope();
    }

    public List<Integer> heldYears() {
        return heldYears;
    }

    public int defaultRankingYear() {
        return defaultRankingYear;
    }

    public boolean isHeld(int year) {
        return heldYears.contains(year);
    }

    /** The edition to read for a request, or empty when the requested edition is not held. */
    public OptionalInt resolveRankingYear(Integer requestedYear) {
        if (requestedYear == null) {
            return OptionalInt.of(defaultRankingYear);
        }
        return isHeld(requestedYear) ? OptionalInt.of(requestedYear) : OptionalInt.empty();
    }

    /**
     * The held editions as a PostgreSQL array literal, bound as {@code ?::int[]}.
     * Built from integers, so it cannot carry anything but digits and commas.
     */
    public String heldYearsSqlArray() {
        return heldYears.stream().map(String::valueOf).collect(Collectors.joining(",", "{", "}"));
    }

    private static List<Integer> parse(String override) {
        if (override == null || override.isBlank()) {
            return List.of();
        }
        return Arrays.stream(override.split(","))
                .map(String::trim)
                .filter(value -> !value.isEmpty())
                .map(Integer::valueOf)
                .distinct()
                .sorted(Comparator.reverseOrder())
                .toList();
    }
}
