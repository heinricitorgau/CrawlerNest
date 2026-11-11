package clawer.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
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

    /**
     * Which editions each source actually covers, newest first.
     *
     * <p>Mirrors {@code DATASET_COVERAGE} in {@code crawlernest/core/dataset.py}.
     * ARWU and THE reach back to 2015; QS has gaps (no 2015, 2016, 2021). A flat list of years
     * cannot say that, and the snapshot caveat names a source -- rendering it over
     * every held edition would claim QS published tables for ten editions holding
     * no QS row.
     */
    public static final Map<String, List<Integer>> DATASET_COVERAGE = Map.of(
            "QS", List.of(2026, 2025, 2024, 2023, 2022, 2020, 2019, 2018, 2017),
            "THE", List.of(2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015),
            "ARWU", List.of(2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015));

    /**
     * The (source, edition) pairs the warehouse holds that were not crawled from the
     * source directly, with the date of the Internet Archive capture the ranks were
     * read from. An edition in {@link #DATASET_COVERAGE} and not here was crawled live.
     *
     * <p>Mirrors {@code DATASET_ARCHIVE_EDITIONS} in {@code crawlernest/core/dataset.py};
     * {@code test_caveat_contract.py} compares the literals, and compares the dates with
     * the archive manifest and its ingest receipts.
     */
    public static final Map<String, Map<Integer, String>> DATASET_ARCHIVE_EDITIONS = Map.of(
            "QS", Map.of(2024, "2026-03-29", 2023, "2026-05-10", 2022, "2022-04-09", 2020, "2021-02-16", 2019, "2021-02-21", 2018, "2021-02-12", 2017, "2022-04-26"));

    /** Ranking sources ingested, widest first. Mirrors {@code DATASET_SOURCES} in Python. */
    public static final List<String> DATASET_SOURCES = List.of("QS", "THE", "ARWU");

    /**
     * Every ranking edition the warehouse holds, newest first. Changing it is a data migration.
     *
     * <p>The union of {@link #DATASET_COVERAGE}, written out because
     * {@code test_caveat_contract.py} reads this literal and compares it with the
     * Python and TypeScript ones; {@link #datasetYearsMatchCoverage} keeps the
     * literal honest against the map beside it.
     */
    public static final List<Integer> DATASET_YEARS = List.of(
            2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015);

    static {
        if (!datasetYearsMatchCoverage()) {
            throw new IllegalStateException(
                    "DATASET_YEARS is not the union of DATASET_COVERAGE; one of the two is wrong");
        }
    }

    static {
        DATASET_ARCHIVE_EDITIONS.forEach((source, editions) -> {
            if (!DATASET_COVERAGE.getOrDefault(source, List.of()).containsAll(editions.keySet())) {
                throw new IllegalStateException(
                        "DATASET_ARCHIVE_EDITIONS names " + source + " editions DATASET_COVERAGE does not hold");
            }
        });
    }

    /** The capture date of an archive-sourced edition, or null when it was crawled live. */
    public static String archiveCaptureDate(String source, int year) {
        return DATASET_ARCHIVE_EDITIONS.getOrDefault(source, Map.of()).get(year);
    }

    /** One source's editions that were crawled from it directly, newest first. */
    public static List<Integer> liveYears(String source) {
        Map<Integer, String> archived = DATASET_ARCHIVE_EDITIONS.getOrDefault(source, Map.of());
        return DATASET_COVERAGE.getOrDefault(source, List.of()).stream()
                .filter(year -> !archived.containsKey(year))
                .toList();
    }

    /** True when the literal list is exactly the editions some source covers. */
    static boolean datasetYearsMatchCoverage() {
        List<Integer> union = DATASET_COVERAGE.values().stream()
                .flatMap(List::stream)
                .distinct()
                .sorted(Comparator.reverseOrder())
                .toList();
        return union.equals(DATASET_YEARS);
    }

    /**
     * The sources holding ranks for an edition, in {@link #DATASET_SOURCES} order.
     * Empty for an edition the warehouse does not hold. {@code sources_for_year} in
     * Python and {@code sourcesForYear} in TypeScript are the same rule.
     */
    public static List<String> sourcesFor(int year) {
        return DATASET_SOURCES.stream()
                .filter(source -> DATASET_COVERAGE.getOrDefault(source, List.of()).contains(year))
                .toList();
    }

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
