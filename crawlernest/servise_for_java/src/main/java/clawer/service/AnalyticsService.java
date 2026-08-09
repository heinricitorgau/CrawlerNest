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

    private List<String> buildTrendCaveats(boolean singleYear, boolean noData, boolean containsModelEstimates) {
        List<String> caveats = new ArrayList<>();
        caveats.add("THE (Times Higher Education) data is not available. Analysis reflects QS source only.");
        caveats.add("ARWU (Academic Ranking of World Universities) data is not available. Analysis reflects QS source only.");
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
