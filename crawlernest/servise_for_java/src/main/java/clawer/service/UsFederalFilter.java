package clawer.service;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import org.springframework.jdbc.core.JdbcTemplate;

/**
 * A recommendation filter on US federal figures (College Scorecard / IPEDS): a cap on average net price and
 * a range of admission rate.
 *
 * <p><b>A filter, never a signal.</b> It decides whether a candidate is in the list and nothing else: it
 * never reaches a matching score, a rank, the composite, the coverage ratio or a confidence label, which
 * count ranking sources only (CLAUDE.md, "US federal institutional data").
 *
 * <p><b>No figure is not a pass.</b> A university is kept only when its figure is reported or NCES-imputed and
 * inside the range. One outside the US, one not tied to a UNITID, and one whose figure is suppressed or not
 * available are all left out, each counted under its own reason in the response, never guessed or read as 0.
 */
public final class UsFederalFilter {

    public static final String METRIC_NET_PRICE = "average_net_price";
    public static final String METRIC_ADMISSION_RATE = "admission_rate";

    public static final String REASON_NO_FEDERAL_RECORD = "no_federal_record";
    public static final String REASON_FIGURE_NOT_REPORTED = "figure_not_reported";
    public static final String REASON_OUTSIDE_RANGE = "outside_range";

    private record Figure(BigDecimal value, String status, String referencePeriod) {
    }

    private final Integer maxNetPrice;
    private final Double minAdmissionRate;
    private final Double maxAdmissionRate;
    /** canonical id -> metric key -> figure; a university with no entry has no federal record. */
    private final Map<Long, Map<String, Figure>> figures;
    private final Map<String, Integer> excluded = new TreeMap<>();
    private final Map<String, String> referencePeriods = new TreeMap<>();
    private int kept;

    private UsFederalFilter(Integer maxNetPrice, Double minAdmissionRate, Double maxAdmissionRate,
                            Map<Long, Map<String, Figure>> figures) {
        this.maxNetPrice = maxNetPrice;
        this.minAdmissionRate = minAdmissionRate;
        this.maxAdmissionRate = maxAdmissionRate;
        this.figures = figures;
    }

    /** No filter when no bound is given: nothing is read and every candidate passes. */
    public static UsFederalFilter none() {
        return new UsFederalFilter(null, null, null, Map.of());
    }

    /**
     * Validates the bounds and loads the two figures for every university that has them.
     *
     * @throws IllegalArgumentException for a negative price or a rate outside 0..1, or min above max
     */
    public static UsFederalFilter load(JdbcTemplate jdbc, Integer maxNetPrice, Double minAdmissionRate, Double maxAdmissionRate) {
        validate(maxNetPrice, minAdmissionRate, maxAdmissionRate);
        if (maxNetPrice == null && minAdmissionRate == null && maxAdmissionRate == null) {
            return none();
        }
        Map<Long, Map<String, Figure>> figures = new HashMap<>();
        // Every university with a federal record gets an entry, even with neither metric, so "no record" and
        // "no figure" stay different reasons.
        jdbc.query("SELECT canonical_university_id FROM warehouse.us_institution", rs -> {
            figures.put(rs.getLong(1), new HashMap<>());
        });
        jdbc.query("""
                SELECT canonical_university_id, metric_key, value_number, status, reference_period
                FROM warehouse.us_institution_metric
                WHERE metric_key IN (?, ?)
                """, rs -> {
            figures.computeIfAbsent(rs.getLong(1), k -> new HashMap<>())
                    .put(rs.getString(2), new Figure(rs.getBigDecimal(3), rs.getString(4), rs.getString(5)));
        }, METRIC_NET_PRICE, METRIC_ADMISSION_RATE);
        return new UsFederalFilter(maxNetPrice, minAdmissionRate, maxAdmissionRate, figures);
    }

    static UsFederalFilter forTest(Integer maxNetPrice, Double minAdmissionRate, Double maxAdmissionRate,
                                   Map<Long, Map<String, Object[]>> rows) {
        validate(maxNetPrice, minAdmissionRate, maxAdmissionRate);
        Map<Long, Map<String, Figure>> figures = new HashMap<>();
        rows.forEach((id, metrics) -> {
            Map<String, Figure> byKey = new HashMap<>();
            metrics.forEach((key, row) -> byKey.put(key, new Figure(
                    row[0] == null ? null : new BigDecimal(row[0].toString()), (String) row[1], (String) row[2])));
            figures.put(id, byKey);
        });
        return new UsFederalFilter(maxNetPrice, minAdmissionRate, maxAdmissionRate, figures);
    }

    private static void validate(Integer maxNetPrice, Double minAdmissionRate, Double maxAdmissionRate) {
        if (maxNetPrice != null && maxNetPrice < 0) {
            throw new IllegalArgumentException("maxNetPrice must be 0 or more (US dollars a year).");
        }
        for (Double rate : new Double[] {minAdmissionRate, maxAdmissionRate}) {
            if (rate != null && (rate.isNaN() || rate < 0 || rate > 1)) {
                throw new IllegalArgumentException("Admission rate bounds are fractions between 0 and 1.");
            }
        }
        if (minAdmissionRate != null && maxAdmissionRate != null && minAdmissionRate > maxAdmissionRate) {
            throw new IllegalArgumentException("minAdmissionRate is above maxAdmissionRate.");
        }
    }

    public boolean active() {
        return maxNetPrice != null || minAdmissionRate != null || maxAdmissionRate != null;
    }

    /** Whether the candidate stays in the list; a candidate that does not is counted under its reason. */
    public boolean keeps(Long canonicalUniversityId) {
        if (!active()) {
            return true;
        }
        Map<String, Figure> record = canonicalUniversityId == null ? null : figures.get(canonicalUniversityId);
        if (record == null) {
            return drop(REASON_NO_FEDERAL_RECORD);
        }
        if (maxNetPrice != null) {
            String reason = check(record.get(METRIC_NET_PRICE), METRIC_NET_PRICE, null, maxNetPrice.doubleValue());
            if (reason != null) {
                return drop(reason);
            }
        }
        if (minAdmissionRate != null || maxAdmissionRate != null) {
            String reason = check(record.get(METRIC_ADMISSION_RATE), METRIC_ADMISSION_RATE, minAdmissionRate, maxAdmissionRate);
            if (reason != null) {
                return drop(reason);
            }
        }
        kept++;
        return true;
    }

    private String check(Figure figure, String key, Double min, Double max) {
        if (figure == null || figure.value() == null
                || !("reported".equals(figure.status()) || "imputed".equals(figure.status()))) {
            return REASON_FIGURE_NOT_REPORTED;
        }
        referencePeriods.put(key, figure.referencePeriod());
        double value = figure.value().doubleValue();
        if ((min != null && value < min) || (max != null && value > max)) {
            return REASON_OUTSIDE_RANGE;
        }
        return null;
    }

    private boolean drop(String reason) {
        excluded.merge(reason, 1, Integer::sum);
        return false;
    }

    /** What the response says about the filter: the bounds, how many it kept and left out, and why. */
    public Map<String, Object> describe() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("applied", active());
        if (!active()) {
            return out;
        }
        Map<String, Object> bounds = new LinkedHashMap<>();
        if (maxNetPrice != null) bounds.put("max_net_price_usd", maxNetPrice);
        if (minAdmissionRate != null) bounds.put("min_admission_rate", minAdmissionRate);
        if (maxAdmissionRate != null) bounds.put("max_admission_rate", maxAdmissionRate);
        out.put("bounds", bounds);
        out.put("kept", kept);
        out.put("excluded", Map.copyOf(excluded));
        out.put("reference_periods", Map.copyOf(referencePeriods));
        out.put("caveats", List.of(AnalyticsService.US_FEDERAL_FILTER_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT));
        return out;
    }
}
