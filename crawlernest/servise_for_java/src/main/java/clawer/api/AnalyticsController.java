package clawer.api;

import clawer.dto.ApiResponse;
import clawer.service.AnalyticsService;
import clawer.service.SourceIntelligenceService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Analytics endpoints for the Competition Track.
 *
 * All endpoints are strictly readonly. No data is mutated, no pipeline is
 * triggered, and no scores are changed. Each response includes a caveats
 * array disclosing known data limitations (stale data, unavailable sources,
 * single-year coverage, and any modelled value present in the payload).
 *
 * The model-estimate disclosure is not repeated here: this class references
 * {@link AnalyticsService#ESTIMATED_SCORE_CAVEAT} so the string has one
 * definition rather than two copies to keep in step.
 */
@RestController
@RequestMapping("/api/v1/analytics")
public class AnalyticsController {

    private final AnalyticsService analyticsService;
    private final SourceIntelligenceService sourceIntelligenceService;

    public AnalyticsController(
            AnalyticsService analyticsService,
            SourceIntelligenceService sourceIntelligenceService
    ) {
        this.analyticsService = analyticsService;
        this.sourceIntelligenceService = sourceIntelligenceService;
    }

    /**
     * GET /api/v1/analytics/ranking-trends
     *
     * Returns ranking trend data across available aggregation years.
     *
     * When multiple years are available, includes rank delta (positive = improved,
     * negative = declined). When only one year is available, returns that year's
     * data with rank_delta = null and single_year_only = true.
     *
     * Caveats are always included in the response metadata:
     * - THE and ARWU unavailable at RC-1
     * - QS data stale since RC-1 packaging
     * - Single-year limitation when applicable
     */
    @GetMapping("/ranking-trends")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRankingTrends() {
        Map<String, Object> trendData = analyticsService.getRankingTrends();

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("endpoint", "ranking-trends");
        metadata.put("readonly", true);
        metadata.put("caveats", trendData.get("caveats"));

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("available_years", trendData.get("available_years"));
        response.put("single_year_only", trendData.get("single_year_only"));
        response.put("total_count", trendData.get("total_count"));
        response.put("items", trendData.get("items"));
        response.put("evaluation_timestamp", trendData.get("evaluation_timestamp"));

        return ResponseEntity.ok(ApiResponse.success(response, metadata));
    }

    /**
     * GET /api/v1/analytics/source-disagreement
     *
     * Returns source disagreement analysis across all aggregated universities.
     *
     * Identifies universities with the largest rank spread between available
     * sources. At RC-1, THE and ARWU are unavailable — analysis reflects QS
     * source only. This is disclosed in the caveats array.
     *
     * Includes:
     * - Universities with largest rank spread (top 10)
     * - Source overlap counts (QS, THE, ARWU)
     * - Confidence bucket distribution (high/medium/low)
     * - Missing source coverage percentages
     * - Thresholds used for agreement/disagreement classification
     */
    @GetMapping("/source-disagreement")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSourceDisagreement() {
        Map<String, Object> agreementData = sourceIntelligenceService.getSourceAgreementDiagnostics();

        // Add analytics-specific caveats to the response.
        List<String> caveats = new ArrayList<>(List.of(
                "THE (Times Higher Education) data is not available. Disagreement analysis reflects QS source only.",
                "ARWU (Academic Ranking of World Universities) data is not available. Disagreement analysis reflects QS source only.",
                "QS ranking data was last ingested at RC-1 packaging. Data may not reflect the current published rankings.",
                "At RC-1, all universities have single-source (QS-only) coverage. Multi-source disagreement analysis becomes available when THE and ARWU are ingested."
        ));

        // Disagreement diagnostics are computed from published ranks only. When
        // the modelled disagreement probability is surfaced here, this flag
        // becomes the condition that carries ESTIMATED_SCORE_CAVEAT with it.
        AnalyticsService.appendModelEstimateCaveat(caveats, false);
        caveats = List.copyOf(caveats);

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("endpoint", "source-disagreement");
        metadata.put("readonly", true);
        metadata.put("caveats", caveats);

        Map<String, Object> response = new LinkedHashMap<>(agreementData);
        response.put("analytics_caveats", caveats);

        return ResponseEntity.ok(ApiResponse.success(response, metadata));
    }

    /**
     * GET /api/v1/analytics/estimated-scores
     *
     * Returns model-estimated overall scores for universities whose score the
     * ranking source publishes component indicators for but withholds a total
     * for.
     *
     * This is the only analytics surface carrying values CrawlerNest produced
     * rather than values a ranking body published, so every non-empty response
     * includes {@link AnalyticsService#ESTIMATED_SCORE_CAVEAT}. Each item also
     * carries {@code is_estimated} and a support flag saying whether the model
     * was fitted on comparable cases.
     *
     * Readonly, like every endpoint here. Estimates live in their own tables and
     * never modify a published rank.
     *
     * @param supportedOnly when true, omit estimates that fall outside the
     *                      model's support; defaults to false so the unsupported
     *                      ones are visible rather than quietly dropped
     * @param limit         maximum rows to return, capped by the service
     */
    @GetMapping("/estimated-scores")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getEstimatedScores(
            @RequestParam(name = "supported_only", defaultValue = "false") boolean supportedOnly,
            @RequestParam(name = "limit", defaultValue = "50") int limit
    ) {
        Map<String, Object> estimateData = analyticsService.getEstimatedScores(supportedOnly, limit);

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("endpoint", "estimated-scores");
        metadata.put("readonly", true);
        metadata.put("caveats", estimateData.get("caveats"));

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("model", estimateData.get("model"));
        response.put("total_count", estimateData.get("total_count"));
        response.put("items", estimateData.get("items"));
        response.put("evaluation_timestamp", estimateData.get("evaluation_timestamp"));

        return ResponseEntity.ok(ApiResponse.success(response, metadata));
    }
}
