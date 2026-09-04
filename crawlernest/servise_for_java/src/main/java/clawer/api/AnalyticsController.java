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
     * - per-source coverage, counted from the warehouse rather than asserted
     * - the ranking data is a point-in-time snapshot
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
     * sources. Which sources are actually present, and how much of the table
     * each one covers, is read from the warehouse and disclosed in the caveats
     * array rather than asserted here.
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

        // Source coverage comes from AnalyticsService so this endpoint and the
        // trends endpoint cannot describe the same warehouse differently. It used
        // to be stated here as a constant -- "THE data is not available", "all
        // universities have single-source coverage" -- which was true when
        // written and false the day THE was ingested for part of the table.
        List<String> caveats = new ArrayList<>();
        analyticsService.appendSourceCoverageCaveats(caveats);
        caveats.add(AnalyticsService.SNAPSHOT_CAVEAT);
        caveats.add("Disagreement is only measurable where two or more sources rank the same university. Single-source rows carry no disagreement signal rather than a zero one.");

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

    /**
     * GET /api/v1/analytics/disagreement-risk
     *
     * Returns the modelled probability that THE places a university
     * substantially differently from QS, predicted from QS indicators alone.
     *
     * Separate from estimated-scores rather than a parameter on it: both read
     * the same table, but one returns a 0-100 score and this returns a 0-1
     * probability, and one response shape for two quantities would mean one
     * field name for two meanings.
     *
     * A probability is not a finding, and the caveats say so. Readonly.
     *
     * @param supportedOnly omit rows outside the model's support; defaults to
     *                      false so they stay visible rather than being dropped
     * @param limit         maximum rows, capped by the service
     */
    @GetMapping("/disagreement-risk")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getDisagreementRisk(
            @RequestParam(name = "supported_only", defaultValue = "false") boolean supportedOnly,
            @RequestParam(name = "limit", defaultValue = "50") int limit
    ) {
        Map<String, Object> riskData = analyticsService.getDisagreementRisk(supportedOnly, limit);

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("endpoint", "disagreement-risk");
        metadata.put("readonly", true);
        metadata.put("caveats", riskData.get("caveats"));

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("model", riskData.get("model"));
        response.put("total_count", riskData.get("total_count"));
        response.put("items", riskData.get("items"));
        response.put("evaluation_timestamp", riskData.get("evaluation_timestamp"));

        return ResponseEntity.ok(ApiResponse.success(response, metadata));
    }
}
