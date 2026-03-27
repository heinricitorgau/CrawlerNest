package clawer.api;

import clawer.dto.RankingDTO;
import clawer.dto.ApiResponse;
import clawer.service.RankingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * REST Controller for accessing Ranking data.
 */
@RestController
@RequestMapping("/api/v1/rankings")
public class RankingController {
    private static final Logger LOGGER = LoggerFactory.getLogger(RankingController.class);

    private final RankingService rankingService;

    public RankingController(RankingService rankingService) {
        this.rankingService = rankingService;
    }

    /**
     * Retrieves all rankings across all sources.
     * @return List of RankingDTO objects
     */
    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, Object>>> getAllRankings(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) String source,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String scope,
            @RequestParam(required = false) String region
    ) {
        LOGGER.info(
                "GET /api/v1/rankings called with page={}, pageSize={}, source={}, year={}, search={}, scope={}, region={}",
                page,
                pageSize,
                source,
                year,
                search,
                scope,
                region
        );
        int safePage = Math.max(page, 1) - 1;
        int safeSize = Math.min(Math.max(pageSize == null ? 20 : pageSize, 1), 100);
        String safeSource = (source == null || source.isBlank()) ? "AGGREGATED" : source;
        if (!rankingService.isSupportedSource(safeSource)) {
            return ResponseEntity.badRequest().body(unsupportedSourceResponse());
        }
        String safeScope = rankingService.normalizeScope(scope);
        String safeRegion = rankingService.normalizeRegion(region);
        ResponseEntity<ApiResponse<Map<String, Object>>> validationError = validateScopeAndRegion(safeScope, safeRegion);
        if (validationError != null) {
            return validationError;
        }
        return ResponseEntity.ok(ApiResponse.success(
                Map.of("items", rankingService.getRankings(safePage, safeSize, year, search, safeScope, safeRegion))
        ));
    }

    /**
     * Retrieves rankings from a specific source (e.g., "qs", "the").
     * @param source The ranking source identifier
     * @return List of RankingDTO objects from that source
     */
    @GetMapping("/{source}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRankingsBySource(
            @PathVariable String source,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String scope,
            @RequestParam(required = false) String region
    ) {
        LOGGER.info(
                "GET /api/v1/rankings/{} called with page={}, pageSize={}, year={}, search={}, scope={}, region={}",
                source,
                page,
                pageSize,
                year,
                search,
                scope,
                region
        );
        int safePage = Math.max(page, 1) - 1;
        int safeSize = Math.min(Math.max(pageSize == null ? 20 : pageSize, 1), 100);
        if (!rankingService.isSupportedSource(source)) {
            return ResponseEntity.badRequest().body(unsupportedSourceResponse());
        }
        String safeScope = rankingService.normalizeScope(scope);
        String safeRegion = rankingService.normalizeRegion(region);
        ResponseEntity<ApiResponse<Map<String, Object>>> validationError = validateScopeAndRegion(safeScope, safeRegion);
        if (validationError != null) {
            return validationError;
        }
        return ResponseEntity.ok(ApiResponse.success(
                Map.of("items", rankingService.getRankings(safePage, safeSize, year, search, safeScope, safeRegion))
        ));
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> validateScopeAndRegion(String scope, String region) {
        if (!rankingService.isSupportedScope(scope)) {
            return ResponseEntity.badRequest().body(validationErrorResponse("Only scope=global or scope=region is supported."));
        }

        if (rankingService.requiresRegion(scope) && (region == null || region.isBlank())) {
            return ResponseEntity.badRequest().body(validationErrorResponse("region is required when scope=region."));
        }

        if (rankingService.requiresRegion(scope) && !rankingService.isSupportedRegion(region)) {
            return ResponseEntity.badRequest().body(validationErrorResponse(
                    "Unsupported region. Supported values: Europe, Asia, North America, Latin America, Oceania, Africa."
            ));
        }

        return null;
    }

    private ApiResponse<Map<String, Object>> unsupportedSourceResponse() {
        ApiResponse<Map<String, Object>> response = new ApiResponse<>();
        response.setSuccess(false);
        response.setData(Map.of(
                "items", List.<RankingDTO>of(),
                "error", "Only source=AGGREGATED is supported for product rankings."
        ));
        return response;
    }

    private ApiResponse<Map<String, Object>> validationErrorResponse(String errorMessage) {
        ApiResponse<Map<String, Object>> response = new ApiResponse<>();
        response.setSuccess(false);
        response.setData(Map.of(
                "items", List.<RankingDTO>of(),
                "error", errorMessage
        ));
        return response;
    }
}
