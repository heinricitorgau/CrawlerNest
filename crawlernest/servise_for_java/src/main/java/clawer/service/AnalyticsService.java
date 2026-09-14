package clawer.service;

import clawer.repository.InstitutionLineageRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * Service for providing analytics on university ranking data.
 * All queries are strictly readonly — no mutations to the database.
 */
@Service
public class AnalyticsService {

    private static final int TREND_LIMIT = 200;
    private static final int ESTIMATE_LIMIT = 200;

    /**
     * Modelling targets stored in analytics.ml_predictions.
     *
     * Every read of v_ml_predictions_latest must filter on one of these. The view
     * holds the latest run *per target*, so an unfiltered query returns two
     * different quantities in one list -- 0-100 scores and 0-1 probabilities --
     * and sorting that by predicted_value buries one behind the other.
     */
    private static final String TARGET_OVERALL_SCORE = "qs_overall_score";
    private static final String TARGET_DISAGREEMENT = "qs_the_disagreement";

    /**
     * Disclosure attached to any response carrying a value produced by the
     * modelling layer rather than published by a ranking source.
     *
     * Single source of truth: {@code AnalyticsController} references this
     * constant rather than repeating the text, and
     * {@code AnalyticsCaveatContractTest} asserts that
     * {@code docs/analytics/ANALYTICS_EXPLAINABILITY.md} carries it verbatim.
     * Change the string here and the test will tell you if the doc drifted.
     */
    public static final String ESTIMATED_SCORE_CAVEAT =
            "Some values in this response are model estimates produced by CrawlerNest, not figures published by the ranking source. Estimated values are labelled as estimates, carry a support flag, and never replace a published rank.";

    /**
     * Ranking editions the warehouse holds, newest first. Defined in
     * {@link DatasetScope}, which every serving read resolves its edition through;
     * re-exported here because the snapshot caveat renders from it.
     */
    public static final List<Integer> DATASET_YEARS = DatasetScope.DATASET_YEARS;

    /**
     * The snapshot disclosure with its editions left open. Byte-identical to
     * {@code SNAPSHOT_CAVEAT_TEMPLATE} in caveats.py and caveatMessages.ts and to
     * the copy in ANALYTICS_EXPLAINABILITY.md. {@code {years}} is replaced
     * literally by {@link #formatEditionYears}.
     */
    public static final String SNAPSHOT_CAVEAT_TEMPLATE =
            "QS ranking data is a point-in-time snapshot of the {years} published tables. Figures may not reflect rankings republished since this snapshot was ingested.";

    /**
     * Snapshot disclosure for the ranking data.
     *
     * Previously named an age -- "last ingested at RC-1 packaging (approximately
     * 354 hours ago)" -- which was accurate when written and overstated the data's
     * age by roughly two weeks once the 2026 re-crawl landed on 2026-09-04. An age
     * written into a constant is a disclosure with an expiry date, so this states
     * that the data is a snapshot without claiming a distance from it.
     *
     * The year it names is the same kind of expiring fact, so it is rendered from
     * {@link #DATASET_YEARS} through {@link #SNAPSHOT_CAVEAT_TEMPLATE}. For the
     * single 2026 edition the result is the exact sentence this constant held.
     */
    public static final String SNAPSHOT_CAVEAT = snapshotCaveat(DATASET_YEARS);

    /**
     * Per-source coverage disclosures, for callers that need them as constants.
     *
     * {@link #appendSourceCoverageCaveats} remains the preferred path because it
     * counts the warehouse rather than asserting a shape. These exist for the
     * surfaces that cannot run a query -- the frontend's caveatMessages.ts mirrors
     * them, and Python's crawlernest/core/caveats.py holds the third copy.
     *
     * Both previously said the source "is not available at RC-1", which stopped
     * being true when THE (1,637 ranks) and ARWU (838) were ingested for 2026.
     */
    public static final String THE_PARTIAL_CAVEAT =
            "THE (Times Higher Education) covers part of this dataset. A missing THE rank means either that the THE data ingested here does not include the university or that this platform could not match it. It does not mean THE declines to rank it.";

    public static final String ARWU_PARTIAL_CAVEAT =
            "ARWU (Academic Ranking of World Universities) covers part of this dataset. A missing ARWU rank means either that the ARWU data ingested here does not include the university or that this platform could not match it. It does not mean ARWU declines to rank it.";

    /** The set every recommendation and analytics surface carries. */
    public static final List<String> STANDARD_CAVEATS =
            List.of(SNAPSHOT_CAVEAT, THE_PARTIAL_CAVEAT, ARWU_PARTIAL_CAVEAT);

    /**
     * Disclosure for a surfaced disagreement probability.
     *
     * Separate from {@link #ESTIMATED_SCORE_CAVEAT} because that one does not
     * cover the likeliest misreading: "0.99 disagreement" reads as a measured
     * conflict, and most universities the classifier scores carry no THE rank for
     * anything to have conflicted with.
     */
    /**
     * Disclosure for an estimate the model was not fitted anywhere near.
     *
     * {@link #ESTIMATED_SCORE_CAVEAT} promises the reader a support flag. For the
     * overall-score model 351 of 787 rows carry it set to false -- 45%, and those
     * rows are systematically lower than the supported ones -- so a response that
     * mentions the flag without ever saying it fired is disclosing the mechanism
     * and withholding the result.
     */
    public static final String UNSUPPORTED_ESTIMATE_CAVEAT =
            "Some estimates here fall outside the data the model was fitted on and are marked unsupported. The model has seen no comparable cases for them. That is a statement about the evidence behind the estimate, not a measurement of how wrong it is.";

    /** Carried wherever a per-source rankDelta is shown. See {@link SourceRankDelta}. */
    public static final String RANK_CHANGE_CAVEAT =
            "Rank changes compare one source's published ranks between two editions. They are not changes in a composite or platform rank, a banded rank gives a range rather than a number, and no change is shown when the institution or its source entry changed between editions.";

    /** Carried by ranking trends when more than one edition is held; see {@link RankComparisonPolicy}. */
    public static final String COMPOSITE_RANK_NOT_COMPARED_CAVEAT =
            "Composite ranks are not compared between editions. A university's composite position moves whenever source coverage changes, so rank movement is reported per source on each university's page instead.";

    public static final String DISAGREEMENT_ESTIMATE_CAVEAT =
            "Cross-source disagreement probability is a model estimate of how likely QS and THE are to disagree about a university, not an observed difference between published ranks. A probability is not a rank gap, and most scored universities carry no THE rank to compare against.";

    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;
    private final InstitutionLineageRepository institutionLineageRepository;
    private final ObjectMapper objectMapper;

    @Autowired
    public AnalyticsService(
            JdbcTemplate jdbcTemplate,
            ObjectMapper objectMapper,
            DatasetScope datasetScope,
            InstitutionLineageRepository institutionLineageRepository
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.datasetScope = datasetScope;
        this.institutionLineageRepository = institutionLineageRepository;
    }

    public AnalyticsService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this(jdbcTemplate, objectMapper, DatasetScope.standard(), new InstitutionLineageRepository(jdbcTemplate));
    }

    /**
     * Returns ranking trend data across the editions the warehouse holds.
     *
     * Only held editions count: an edition with finished aggregation runs but not
     * yet released (a shadow ingest) is neither listed in available_years nor
     * used as the "previous" year, so loading it changes nothing here.
     *
     * No rank delta is ever computed. rank_delta is null on every row and
     * rank_delta_reason says why -- see {@link RankComparisonPolicy}: a single
     * held edition, an institution-lineage event between the two editions, or,
     * otherwise, that a composite rank is not comparable across editions. Rows on
     * a lineage boundary also drop previous_rank, which belongs to a different
     * institution.
     *
     * Readonly: reads analytics.aggregated_rankings and warehouse.institution_lineage.
     */
    public Map<String, Object> getRankingTrends() {
        Map<String, Object> data = new LinkedHashMap<>();

        // Editions with finished runs, restricted to the ones this release holds.
        List<Integer> years = jdbcTemplate.queryForList("""
                SELECT DISTINCT ar.ranking_year
                FROM analytics.aggregated_rankings ar
                JOIN analytics.aggregation_runs run
                  ON run.aggregation_run_id = ar.aggregation_run_id
                WHERE run.status = 'finished'
                  AND ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                  AND ar.ranking_year = ANY(?::int[])
                ORDER BY ar.ranking_year DESC
                """, Integer.class, datasetScope.heldYearsSqlArray());

        data.put("available_years", years);
        boolean singleYearOnly = years.size() < 2;
        data.put("single_year_only", singleYearOnly);

        if (years.isEmpty()) {
            data.put("items", List.of());
            data.put("total_count", 0);
            // No rows at all, so certainly no modelled values among them.
            data.put("caveats", buildTrendCaveats(true, true, false));
            data.put("evaluation_timestamp", Instant.now().toString());
            return data;
        }

        int currentYear = years.get(0);

        if (singleYearOnly) {
            // Return current-year rankings with null deltas.
            List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                    SELECT cu.canonical_university_id,
                           cu.display_name AS university_name,
                           cu.canonical_slug AS slug,
                           c.country_name,
                           ar.ranking_year,
                           ar.display_rank AS current_rank,
                           ar.source_ranks_json
                    FROM analytics.aggregated_rankings ar
                    JOIN analytics.aggregation_runs run
                      ON run.aggregation_run_id = ar.aggregation_run_id
                    JOIN warehouse.canonical_university cu
                      ON cu.canonical_university_id = ar.canonical_university_id
                    LEFT JOIN warehouse.countries c
                      ON c.country_id = cu.country_id
                    WHERE run.status = 'finished'
                      AND ar.universe_type = 'global'
                      AND ar.universe_key = 'global'
                      AND ar.ranking_year = ?
                      AND ar.display_rank IS NOT NULL
                    ORDER BY ar.display_rank ASC
                    LIMIT ?
                    """, currentYear, TREND_LIMIT);

            List<Map<String, Object>> items = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("canonical_university_id", row.get("canonical_university_id"));
                item.put("university_name", row.get("university_name"));
                item.put("slug", row.get("slug"));
                item.put("country_name", row.get("country_name"));
                item.put("current_year", row.get("ranking_year"));
                item.put("current_rank", row.get("current_rank"));
                item.put("previous_year", null);
                item.put("previous_rank", null);
                item.put("rank_delta", null);
                item.put("rank_delta_reason", RankComparisonPolicy.REASON_SINGLE_YEAR_DATASET);
                item.put("source_count_current", countSources(row.get("source_ranks_json")));
                item.put("source_count_previous", null);
                items.add(item);
            }
            data.put("items", items);
            data.put("total_count", items.size());
        } else {
            // Multi-year: pair each university with the prior held edition, for
            // context only. The prior edition's filters live inside the derived
            // table: joined bare, `prev` matched every edition of the university,
            // the current one included, and duplicated the row.
            int previousYear = years.get(1);
            List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                    SELECT
                        cur.canonical_university_id,
                        cu.display_name AS university_name,
                        cu.canonical_slug AS slug,
                        c.country_name,
                        cur.ranking_year AS current_year,
                        cur.display_rank  AS current_rank,
                        cur.source_ranks_json AS current_sources,
                        prev.ranking_year AS previous_year,
                        prev.display_rank  AS previous_rank,
                        prev.source_ranks_json AS previous_sources
                    FROM analytics.aggregated_rankings cur
                    JOIN analytics.aggregation_runs cur_run
                      ON cur_run.aggregation_run_id = cur.aggregation_run_id
                    JOIN warehouse.canonical_university cu
                      ON cu.canonical_university_id = cur.canonical_university_id
                    LEFT JOIN warehouse.countries c
                      ON c.country_id = cu.country_id
                    LEFT JOIN (
                        SELECT p.canonical_university_id, p.ranking_year, p.display_rank, p.source_ranks_json
                        FROM analytics.aggregated_rankings p
                        JOIN analytics.aggregation_runs p_run
                          ON p_run.aggregation_run_id = p.aggregation_run_id
                        WHERE p_run.status = 'finished'
                          AND p.universe_type = 'global'
                          AND p.universe_key = 'global'
                          AND p.ranking_year = ?
                    ) prev
                      ON prev.canonical_university_id = cur.canonical_university_id
                    WHERE cur_run.status = 'finished'
                      AND cur.universe_type = 'global'
                      AND cur.universe_key = 'global'
                      AND cur.ranking_year = ?
                      AND cur.display_rank IS NOT NULL
                    ORDER BY cur.display_rank ASC
                    LIMIT ?
                    """, previousYear, currentYear, TREND_LIMIT);

            List<Long> ids = rows.stream()
                    .map(row -> ((Number) row.get("canonical_university_id")).longValue())
                    .toList();
            List<InstitutionLineage.Event> lineage = institutionLineageRepository.findInvolving(ids);

            List<Map<String, Object>> items = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                long canonicalUniversityId = ((Number) row.get("canonical_university_id")).longValue();
                String reason = RankComparisonPolicy.withholdReason(
                        canonicalUniversityId, previousYear, currentYear, lineage);
                boolean acrossLineage = RankComparisonPolicy.REASON_ENTITY_CHANGED.equals(reason);

                Map<String, Object> item = new LinkedHashMap<>();
                item.put("canonical_university_id", row.get("canonical_university_id"));
                item.put("university_name", row.get("university_name"));
                item.put("slug", row.get("slug"));
                item.put("country_name", row.get("country_name"));
                item.put("current_year", row.get("current_year"));
                item.put("current_rank", row.get("current_rank"));
                item.put("previous_year", previousYear);
                item.put("previous_rank", acrossLineage ? null : row.get("previous_rank"));
                item.put("rank_delta", null);
                item.put("rank_delta_reason", reason);
                item.put("source_count_current", countSources(row.get("current_sources")));
                item.put("source_count_previous", acrossLineage ? null : countSources(row.get("previous_sources")));
                items.add(item);
            }
            data.put("items", items);
            data.put("total_count", items.size());
        }

        // Trends read analytics.aggregated_rankings only, which holds published
        // figures. Flips when analytics.ml_predictions is joined in.
        data.put("caveats", buildTrendCaveats(singleYearOnly, false, false));
        data.put("evaluation_timestamp", Instant.now().toString());
        return data;
    }

    /**
     * Returns model-estimated overall scores for universities whose score the
     * ranking source withholds.
     *
     * This is the one analytics surface that carries values CrawlerNest produced
     * rather than values a ranking body published, so it is the one that sets
     * {@code containsModelEstimates} and ships {@link #ESTIMATED_SCORE_CAVEAT}.
     *
     * The modelling tables are optional: a deployment that has never run the
     * scoring job has no analytics.ml_predictions. That is not an error, so this
     * returns an empty result with an explanatory caveat rather than failing.
     *
     * Readonly: reads analytics.v_ml_predictions_latest only.
     */
    public Map<String, Object> getEstimatedScores(boolean supportedOnly, int limit) {
        Map<String, Object> data = new LinkedHashMap<>();
        int cappedLimit = Math.max(1, Math.min(limit, ESTIMATE_LIMIT));

        Boolean viewPresent = jdbcTemplate.queryForObject(
                "SELECT to_regclass('analytics.v_ml_predictions_latest') IS NOT NULL", Boolean.class);

        if (viewPresent == null || !viewPresent) {
            data.put("items", List.of());
            data.put("total_count", 0);
            data.put("model", null);
            List<String> caveats = new ArrayList<>();
            caveats.add("No model estimates are available. The modelling layer has not been run against this database.");
            data.put("caveats", caveats);
            data.put("evaluation_timestamp", Instant.now().toString());
            return data;
        }

        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT model_name, model_version, trained_at, support_threshold,
                       canonical_university_id, university_name, slug, country_name,
                       ranking_year, predicted_value, support_distance, is_supported, is_estimated
                  FROM analytics.v_ml_predictions_latest
                 WHERE target = ?
                   AND ranking_year = ?
                   AND (%s OR is_supported)
                 ORDER BY predicted_value DESC
                 LIMIT %d
                """.formatted(supportedOnly ? "FALSE" : "TRUE", cappedLimit),
                TARGET_OVERALL_SCORE, datasetScope.defaultRankingYear());

        List<Map<String, Object>> items = new ArrayList<>();
        Map<String, Object> model = null;
        for (Map<String, Object> row : rows) {
            if (model == null) {
                model = new LinkedHashMap<>();
                model.put("name", row.get("model_name"));
                model.put("version", row.get("model_version"));
                model.put("trained_at", String.valueOf(row.get("trained_at")));
                model.put("support_threshold", row.get("support_threshold"));
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("canonical_university_id", row.get("canonical_university_id"));
            item.put("university_name", row.get("university_name"));
            item.put("slug", row.get("slug"));
            item.put("country_name", row.get("country_name"));
            item.put("ranking_year", row.get("ranking_year"));
            item.put("estimated_overall_score", row.get("predicted_value"));
            item.put("support_distance", row.get("support_distance"));
            item.put("is_supported", row.get("is_supported"));
            item.put("is_estimated", row.get("is_estimated"));
            items.add(item);
        }

        data.put("items", items);
        data.put("total_count", items.size());
        data.put("model", model);

        List<String> caveats = new ArrayList<>();
        caveats.add("Estimates cover universities ranked below the published score cut-off. The ranking source publishes their component indicators but withholds the overall score.");
        caveats.add("Cross-validated error is measured on universities that do have a published score. Those are a different population from these, so it does not describe the error here.");
        if (!supportedOnly) {
            caveats.add("Rows with is_supported = false sit outside the range of data the model was fitted on. Their estimates carry no support from comparable cases.");
        }
        appendModelEstimateCaveat(caveats, !items.isEmpty());
        data.put("caveats", caveats);
        data.put("evaluation_timestamp", Instant.now().toString());
        return data;
    }

    /**
     * Returns the modelled probability that THE ranks a university substantially
     * differently from QS, predicted from QS indicators alone.
     *
     * Deliberately a separate surface from {@link #getEstimatedScores}, rather
     * than a parameter on it. Both read the same table, but one returns a 0-100
     * score and the other a 0-1 probability; sharing a response shape would mean
     * sharing a field name for two different quantities.
     *
     * Readonly: reads analytics.v_ml_predictions_latest only.
     */
    public Map<String, Object> getDisagreementRisk(boolean supportedOnly, int limit) {
        Map<String, Object> data = new LinkedHashMap<>();
        int cappedLimit = Math.max(1, Math.min(limit, ESTIMATE_LIMIT));

        Boolean viewPresent = jdbcTemplate.queryForObject(
                "SELECT to_regclass('analytics.v_ml_predictions_latest') IS NOT NULL", Boolean.class);

        if (viewPresent == null || !viewPresent) {
            data.put("items", List.of());
            data.put("total_count", 0);
            data.put("model", null);
            List<String> caveats = new ArrayList<>();
            caveats.add("No disagreement predictions are available. The modelling layer has not been run against this database.");
            data.put("caveats", caveats);
            data.put("evaluation_timestamp", Instant.now().toString());
            return data;
        }

        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT model_name, model_version, trained_at, support_threshold,
                       canonical_university_id, university_name, slug, country_name,
                       ranking_year, predicted_value, support_distance, is_supported, is_estimated
                  FROM analytics.v_ml_predictions_latest
                 WHERE target = ?
                   AND ranking_year = ?
                   AND (%s OR is_supported)
                 ORDER BY predicted_value DESC
                 LIMIT %d
                """.formatted(supportedOnly ? "FALSE" : "TRUE", cappedLimit),
                TARGET_DISAGREEMENT, datasetScope.defaultRankingYear());

        List<Map<String, Object>> items = new ArrayList<>();
        Map<String, Object> model = null;
        for (Map<String, Object> row : rows) {
            if (model == null) {
                model = new LinkedHashMap<>();
                model.put("name", row.get("model_name"));
                model.put("version", row.get("model_version"));
                model.put("trained_at", String.valueOf(row.get("trained_at")));
                model.put("support_threshold", row.get("support_threshold"));
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("canonical_university_id", row.get("canonical_university_id"));
            item.put("university_name", row.get("university_name"));
            item.put("slug", row.get("slug"));
            item.put("country_name", row.get("country_name"));
            item.put("ranking_year", row.get("ranking_year"));
            item.put("disagreement_probability", row.get("predicted_value"));
            item.put("support_distance", row.get("support_distance"));
            item.put("is_supported", row.get("is_supported"));
            item.put("is_estimated", row.get("is_estimated"));
            items.add(item);
        }

        data.put("items", items);
        data.put("total_count", items.size());
        data.put("model", model);

        List<String> caveats = new ArrayList<>();
        caveats.add("This is a probability, not a finding. A high value means universities with similar QS profiles are often placed differently by THE, not that this university has been shown to be misranked.");
        caveats.add("The model is trained on the universities QS and THE both rank. Universities outside that overlap are scored by extrapolation, which the support flag reports per row.");
        caveats.add("THE data is not ingested in this release, so no prediction here can currently be checked against an actual THE placement.");
        if (!supportedOnly) {
            caveats.add("Rows with is_supported = false sit outside the range of data the model was fitted on. Their probabilities carry no support from comparable cases.");
        }
        appendModelEstimateCaveat(caveats, !items.isEmpty());
        data.put("caveats", caveats);
        data.put("evaluation_timestamp", Instant.now().toString());
        return data;
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private int countSources(Object sourceRanksJson) {
        if (sourceRanksJson == null) return 0;
        try {
            Map<String, Object> ranks = objectMapper.readValue(
                    sourceRanksJson.toString(), new TypeReference<>() {});
            int count = 0;
            for (Object rank : ranks.values()) {
                if (rank != null) count++;
            }
            return count;
        } catch (Exception ex) {
            return 0;
        }
    }

    /**
     * Sources in the order the caveats list them, with their display names.
     *
     * <p>A List rather than a Map because Map.of does not preserve order, and a
     * caveats array whose entries move between restarts is hard to diff and hard
     * to write a contract test against.
     */
    private static final List<Map.Entry<String, String>> SOURCE_LABELS = List.of(
            Map.entry("QS", "QS (Quacquarelli Symonds)"),
            Map.entry("THE", "THE (Times Higher Education)"),
            Map.entry("ARWU", "ARWU (Academic Ranking of World Universities)"));

    /**
     * How many aggregated rows carry a non-null rank for each source.
     *
     * <p>Read from the data rather than stated as a constant. These caveats used
     * to assert "THE data is not available", which was true when written and
     * became false the day THE was ingested for part of the table — the sort of
     * disclosure that is worse than none, because it is specific and confident.
     */
    private Map<String, Integer> sourceCoverage() {
        // The default edition only. Counted over every edition, "N of M" doubles
        // when a second edition is loaded and describes no table anyone is shown.
        Map<String, Integer> coverage = new LinkedHashMap<>();
        for (String source : List.of("QS", "THE", "ARWU")) {
            Integer count = jdbcTemplate.queryForObject("""
                    SELECT count(*)
                    FROM analytics.v_aggregated_rankings_latest
                    WHERE source_ranks_json -> ? IS NOT NULL
                      AND source_ranks_json -> ? <> 'null'::jsonb
                      AND ranking_year = ?
                    """, Integer.class, source, source, datasetScope.defaultRankingYear());
            coverage.put(source, count == null ? 0 : count);
        }
        return coverage;
    }

    /**
     * Disclose each source's coverage, including what a missing rank means.
     *
     * <p>A null rank is ambiguous and the ambiguity matters: it can mean the
     * source does not rank the university, or that this platform could not match
     * the university to the source's table. Only the second is our doing, and
     * reporting it as the first would blame the institution for our gap.
     */
    public void appendSourceCoverageCaveats(List<String> caveats) {
        Map<String, Integer> coverage = sourceCoverage();
        int total = coverage.values().stream().mapToInt(Integer::intValue).max().orElse(0);

        for (Map.Entry<String, String> entry : SOURCE_LABELS) {
            int covered = coverage.getOrDefault(entry.getKey(), 0);
            if (covered == 0) {
                caveats.add(entry.getValue() + " data is not available. No university carries a rank from this source.");
            } else if (total > 0 && covered < total) {
                // Two causes, and naming only one of them was wrong the moment a
                // partial snapshot was ingested: ARWU's covers its top 30, so most
                // of its absences are the snapshot's limit rather than a failed
                // match. Both are ours. Neither is the source declining to rank.
                caveats.add(String.format(
                        "%s covers %d of %d universities. A missing %s rank means either that the "
                                + "%s data ingested here does not include the university or that this "
                                + "platform could not match it — not that %s does not rank it.",
                        entry.getValue(), covered, total, entry.getKey(), entry.getKey(), entry.getKey()));
            }
        }
    }

    private List<String> buildTrendCaveats(boolean singleYear, boolean noData, boolean containsModelEstimates) {
        List<String> caveats = new ArrayList<>();
        appendSourceCoverageCaveats(caveats);
        caveats.add(SNAPSHOT_CAVEAT);
        if (singleYear && !noData) {
            caveats.add("Year-over-year trend analysis requires data from multiple aggregation runs. Current coverage is a single year — no rank delta is available.");
        }
        if (!singleYear && !noData) {
            caveats.add(COMPOSITE_RANK_NOT_COMPARED_CAVEAT);
        }
        if (noData) {
            caveats.add("No aggregated ranking data is currently available.");
        }
        appendModelEstimateCaveat(caveats, containsModelEstimates);
        return caveats;
    }

    /**
     * Held editions as prose: {@code 2026}, {@code 2025 and 2026},
     * {@code 2024, 2025 and 2026}. Ascending and de-duplicated whatever order they
     * arrive in. The rows in ANALYTICS_EXPLAINABILITY.md are the specification;
     * Python and TypeScript test their renderers against the same rows.
     */
    public static String formatEditionYears(Collection<Integer> years) {
        List<String> ordered = new TreeSet<>(years).stream().map(String::valueOf).toList();
        if (ordered.isEmpty()) {
            throw new IllegalArgumentException("a snapshot caveat has to name at least one edition");
        }
        if (ordered.size() == 1) {
            return ordered.get(0);
        }
        return String.join(", ", ordered.subList(0, ordered.size() - 1))
                + " and " + ordered.get(ordered.size() - 1);
    }

    /** The snapshot disclosure for the given editions. */
    public static String snapshotCaveat(Collection<Integer> years) {
        return SNAPSHOT_CAVEAT_TEMPLATE.replace("{years}", formatEditionYears(years));
    }

    /**
     * Adds {@link #ESTIMATED_SCORE_CAVEAT} when the payload carries a modelled
     * value.
     *
     * The caveat is conditional rather than always-on because an unconditional
     * disclosure would be false: most responses contain nothing but published
     * figures, and a caveat that appears when it does not apply teaches readers
     * to skip the caveats array.
     *
     * {@code analytics.ml_predictions} is populated as of the 2026-09-14 run --
     * 787 overall-score estimates and 1,482 disagreement probabilities -- so the
     * flag is now reachable rather than hypothetical. Callers that join an
     * estimate in must pass {@code true}; the Python read path in
     * {@code agent/tools/ml_tools.py} enforces the same pairing structurally, by
     * returning the caveats with the rows rather than beside them.
     */
    public static void appendModelEstimateCaveat(List<String> caveats, boolean containsModelEstimates) {
        if (containsModelEstimates) {
            caveats.add(ESTIMATED_SCORE_CAVEAT);
        }
    }
}
