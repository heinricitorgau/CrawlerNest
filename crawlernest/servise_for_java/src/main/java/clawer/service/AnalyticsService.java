package clawer.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

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

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public AnalyticsService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * Returns ranking trend data across available years.
     *
     * When multiple years of aggregated data exist, computes rank delta between
     * the most recent year and the prior year. When only one year is available,
     * returns that year's data with singleYearOnly = true and no delta values.
     *
     * Readonly: reads analytics.aggregated_rankings only.
     */
    public Map<String, Object> getRankingTrends() {
        Map<String, Object> data = new LinkedHashMap<>();

        // Determine available ranking years (finished runs only).
        List<Integer> years = jdbcTemplate.queryForList("""
                SELECT DISTINCT ar.ranking_year
                FROM analytics.aggregated_rankings ar
                JOIN analytics.aggregation_runs run
                  ON run.aggregation_run_id = ar.aggregation_run_id
                WHERE run.status = 'finished'
                  AND ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                ORDER BY ar.ranking_year DESC
                """, Integer.class);

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
                item.put("source_count_current", countSources(row.get("source_ranks_json")));
                item.put("source_count_previous", null);
                items.add(item);
            }
            data.put("items", items);
            data.put("total_count", items.size());
        } else {
            // Multi-year: compute deltas between most recent and prior year.
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
                    LEFT JOIN analytics.aggregated_rankings prev
                      ON prev.canonical_university_id = cur.canonical_university_id
                     AND prev.universe_type = 'global'
                     AND prev.universe_key = 'global'
                    LEFT JOIN analytics.aggregation_runs prev_run
                      ON prev_run.aggregation_run_id = prev.aggregation_run_id
                     AND prev_run.status = 'finished'
                     AND prev.ranking_year = ?
                    WHERE cur_run.status = 'finished'
                      AND cur.universe_type = 'global'
                      AND cur.universe_key = 'global'
                      AND cur.ranking_year = ?
                      AND cur.display_rank IS NOT NULL
                    ORDER BY cur.display_rank ASC
                    LIMIT ?
                    """, previousYear, currentYear, TREND_LIMIT);

            List<Map<String, Object>> items = new ArrayList<>();
            for (Map<String, Object> row : rows) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("canonical_university_id", row.get("canonical_university_id"));
                item.put("university_name", row.get("university_name"));
                item.put("slug", row.get("slug"));
                item.put("country_name", row.get("country_name"));
                item.put("current_year", row.get("current_year"));
                item.put("current_rank", row.get("current_rank"));
                item.put("previous_year", row.get("previous_year"));
                item.put("previous_rank", row.get("previous_rank"));

                Number cur = (Number) row.get("current_rank");
                Number prev = (Number) row.get("previous_rank");
                Integer delta = (cur != null && prev != null)
                        ? prev.intValue() - cur.intValue()
                        : null;
                item.put("rank_delta", delta);
                item.put("source_count_current", countSources(row.get("current_sources")));
                item.put("source_count_previous", countSources(row.get("previous_sources")));
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
                   AND (%s OR is_supported)
                 ORDER BY predicted_value DESC
                 LIMIT %d
                """.formatted(supportedOnly ? "FALSE" : "TRUE", cappedLimit),
                TARGET_OVERALL_SCORE);

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
                   AND (%s OR is_supported)
                 ORDER BY predicted_value DESC
                 LIMIT %d
                """.formatted(supportedOnly ? "FALSE" : "TRUE", cappedLimit),
                TARGET_DISAGREEMENT);

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
        Map<String, Integer> coverage = new LinkedHashMap<>();
        for (String source : List.of("QS", "THE", "ARWU")) {
            Integer count = jdbcTemplate.queryForObject("""
                    SELECT count(*)
                    FROM analytics.v_aggregated_rankings_latest
                    WHERE source_ranks_json -> ? IS NOT NULL
                      AND source_ranks_json -> ? <> 'null'::jsonb
                    """, Integer.class, source, source);
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
        caveats.add("QS ranking data was last ingested at RC-1 packaging. Data may not reflect the current published rankings.");
        if (singleYear && !noData) {
            caveats.add("Year-over-year trend analysis requires data from multiple aggregation runs. Current coverage is a single year — no rank delta is available.");
        }
        if (noData) {
            caveats.add("No aggregated ranking data is currently available.");
        }
        appendModelEstimateCaveat(caveats, containsModelEstimates);
        return caveats;
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
     * Today every caller passes {@code false}: {@code analytics.ml_predictions}
     * does not exist yet, so no endpoint can carry an estimate. The flag flips
     * where estimates are joined in, and the contract and its tests are in place
     * before the first estimate can reach a response rather than after.
     */
    public static void appendModelEstimateCaveat(List<String> caveats, boolean containsModelEstimates) {
        if (containsModelEstimates) {
            caveats.add(ESTIMATED_SCORE_CAVEAT);
        }
    }
}
