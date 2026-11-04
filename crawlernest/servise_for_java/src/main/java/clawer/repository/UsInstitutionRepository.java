package clawer.repository;

import clawer.dto.UsInstitutionDTO;
import clawer.service.AnalyticsService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * Reads {@code warehouse.us_institution} and {@code warehouse.us_institution_metric}
 * (crawlernest-schema/us_institution_postgresql.sql), which
 * crawlernest-jobs/us_institution_loader.py fills from committed files.
 */
@Repository
public class UsInstitutionRepository {
    private static final Logger LOGGER = LoggerFactory.getLogger(UsInstitutionRepository.class);

    /** U.S. federal works are not under copyright; the sources are still named wherever the figures appear. */
    public static final String LICENSE = "Public domain (U.S. federal government work)";

    public static final List<UsInstitutionDTO.Source> SOURCES = List.of(
            new UsInstitutionDTO.Source("COLLEGE_SCORECARD", "College Scorecard", "U.S. Department of Education",
                    "https://collegescorecard.ed.gov/data/", LICENSE),
            new UsInstitutionDTO.Source("IPEDS", "IPEDS", "National Center for Education Statistics (NCES)",
                    "https://nces.ed.gov/ipeds/", LICENSE));

    /** Value keys whose presence brings in {@link AnalyticsService#US_FEDERAL_AID_RECIPIENTS_CAVEAT}. */
    static final Set<String> AID_METRICS = Set.of("median_earnings_10yr", "median_debt_completers");

    private final JdbcTemplate jdbcTemplate;

    public UsInstitutionRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * The federal record matched to this university, or empty when none is: the
     * university is outside the US, or the loader could not tie it to a UNITID.
     *
     * <p>Empty, with a warning, on a database bootstrapped before the tables existed.
     */
    public Optional<UsInstitutionDTO> findByCanonicalUniversityId(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return Optional.empty();
        }
        Boolean present = jdbcTemplate.queryForObject(
                "SELECT to_regclass('warehouse.us_institution') IS NOT NULL "
                        + "AND to_regclass('warehouse.us_institution_metric') IS NOT NULL", Boolean.class);
        if (present == null || !present) {
            LOGGER.warn("warehouse.us_institution is missing; apply crawlernest-schema/us_institution_postgresql.sql");
            return Optional.empty();
        }
        List<UsInstitutionDTO.Metric> metrics = jdbcTemplate.query("""
                SELECT source, metric_key, source_field, unit, value_number, value_text, status, status_detail,
                       reference_period, release
                FROM warehouse.us_institution_metric
                WHERE canonical_university_id = ?
                ORDER BY source, metric_key
                """,
                (rs, n) -> new UsInstitutionDTO.Metric(
                        rs.getString("source"), rs.getString("metric_key"), rs.getString("source_field"),
                        rs.getString("unit"), rs.getBigDecimal("value_number"), rs.getString("value_text"),
                        rs.getString("status"), rs.getString("status_detail"), rs.getString("reference_period"),
                        rs.getString("release")),
                canonicalUniversityId);
        return jdbcTemplate.query("""
                SELECT canonical_university_id, unitid, institution_name, city, state_code, website,
                       match_method, wikidata_id
                FROM warehouse.us_institution
                WHERE canonical_university_id = ?
                """,
                (rs, n) -> new UsInstitutionDTO(
                        rs.getLong("canonical_university_id"), rs.getInt("unitid"), rs.getString("institution_name"),
                        rs.getString("city"), rs.getString("state_code"), rs.getString("website"),
                        rs.getString("match_method"), rs.getString("wikidata_id"), SOURCES, metrics,
                        caveatsFor(metrics)),
                canonicalUniversityId).stream().findFirst();
    }

    /**
     * The caveats a set of values carries, in a fixed order. Mirrors
     * {@code us_federal_caveats} in crawlernest/core/caveats.py.
     */
    public static List<String> caveatsFor(List<UsInstitutionDTO.Metric> metrics) {
        List<String> out = new ArrayList<>(List.of(
                AnalyticsService.US_FEDERAL_SOURCE_CAVEAT, AnalyticsService.US_FEDERAL_PERIODS_CAVEAT));
        boolean aidShown = metrics.stream().anyMatch(m -> AID_METRICS.contains(m.key()) && hasFigure(m));
        if (aidShown) {
            out.add(AnalyticsService.US_FEDERAL_AID_RECIPIENTS_CAVEAT);
        }
        if (metrics.stream().anyMatch(m -> "privacy_suppressed".equals(m.status()))) {
            out.add(AnalyticsService.US_FEDERAL_SUPPRESSED_CAVEAT);
        }
        if (metrics.stream().anyMatch(m -> "imputed".equals(m.status()))) {
            out.add(AnalyticsService.US_FEDERAL_IMPUTED_CAVEAT);
        }
        return List.copyOf(out);
    }

    private static boolean hasFigure(UsInstitutionDTO.Metric m) {
        return "reported".equals(m.status()) || "imputed".equals(m.status());
    }
}
