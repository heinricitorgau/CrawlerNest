package clawer.api;

import clawer.dto.RankingDTO;
import clawer.dto.ApiResponse;
import clawer.dto.RankingCountryOptionDTO;
import clawer.service.RankingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
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
    private final JdbcTemplate jdbcTemplate;

    public RankingController(RankingService rankingService, JdbcTemplate jdbcTemplate) {
        this.rankingService = rankingService;
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Retrieves rankings from preview warehouse tables for frontend browsing.
     */
    @GetMapping
    public ResponseEntity<?> getPreviewRankings(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(required = false, defaultValue = "20") Integer pageSize,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String search,
            @RequestParam(required = false) String scope,
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String country,
            @RequestParam(required = false) String source
    ) {
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

        if (country != null && !country.isBlank() && !rankingService.isSupportedCountry(year, search, country)) {
            return ResponseEntity.badRequest().body(validationErrorResponse("Unsupported country."));
        }
        if ("region".equalsIgnoreCase(safeScope)
                && country != null
                && !country.isBlank()
                && !rankingService.isCountryAllowedForScopeRegion(year, search, safeScope, safeRegion, country)) {
            return ResponseEntity.badRequest().body(validationErrorResponse(
                    "Unsupported country for the current scope/region."
            ));
        }

        String normalizedSearch = trimToNull(search);
        String normalizedCountry = trimToNull(country);
        long totalCount = countPreviewRankings(year, normalizedSearch, safeScope, safeRegion, normalizedCountry);
        List<Map<String, Object>> items = findPreviewRankings(
                year,
                normalizedSearch,
                safeScope,
                safeRegion,
                normalizedCountry,
                safePage,
                safeSize
        );

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("totalCount", totalCount);
        metadata.put("page", safePage + 1);
        metadata.put("pageSize", safeSize);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("items", items);
        data.put("metadata", metadata);

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("success", true);
        response.put("data", data);
        response.put("metadata", metadata);
        return ResponseEntity.ok(response);
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
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String country
    ) {
        LOGGER.info(
                "GET /api/v1/rankings/{} called with page={}, pageSize={}, year={}, search={}, scope={}, region={}, country={}",
                source,
                page,
                pageSize,
                year,
                search,
                scope,
                region,
                country
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
        if (country != null && !country.isBlank() && !rankingService.isSupportedCountry(year, search, country)) {
            return ResponseEntity.badRequest().body(validationErrorResponse(
                    "Unsupported country."
            ));
        }
        if ("region".equalsIgnoreCase(safeScope)
                && country != null
                && !country.isBlank()
                && !rankingService.isCountryAllowedForScopeRegion(year, search, safeScope, safeRegion, country)) {
            return ResponseEntity.badRequest().body(validationErrorResponse(
                    "Unsupported country for the current scope/region."
            ));
        }
        String resolvedCountryCode = rankingService.resolveCountryCode(year, search, safeScope, safeRegion, country);
        LOGGER.info("country={}, resolvedCountryCode={}, scope={}, region={}", country, resolvedCountryCode, safeScope, safeRegion);
        List<RankingDTO> items = rankingService.getRankings(safePage, safeSize, year, search, safeScope, safeRegion, resolvedCountryCode);
        long totalCount = rankingService.countRankings(year, search, safeScope, safeRegion, resolvedCountryCode);
        List<RankingCountryOptionDTO> countryOptions = rankingService.getCountryOptions(year, search, safeScope, safeRegion);
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("totalCount", totalCount);
        metadata.put("page", safePage + 1);
        metadata.put("pageSize", safeSize);
        metadata.put("countryOptions", countryOptions);
        return ResponseEntity.ok(ApiResponse.success(
                Map.of("items", items),
                metadata
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

    private List<Map<String, Object>> findPreviewRankings(
            Integer year,
            String search,
            String scope,
            String region,
            String country,
            int page,
            int pageSize
    ) {
        String sql = previewRankingsCte() + """
                SELECT
                    canonical_university_id,
                    university_name,
                    slug,
                    CASE WHEN ? = 'region' THEN scope_rank ELSE global_rank END AS aggregated_rank,
                    global_rank,
                    CASE WHEN ? = 'region' THEN scope_rank ELSE global_rank END AS scope_rank,
                    GREATEST(0, 100 - ((CASE WHEN ? = 'region' THEN scope_rank ELSE global_rank END) * 2))::double precision AS composite_score,
                    primary_source,
                    source_count,
                    ranking_year,
                    country
                FROM filtered
                ORDER BY
                    CASE WHEN ? = 'region' THEN scope_rank ELSE global_rank END ASC,
                    university_name ASC,
                    canonical_university_id ASC
                LIMIT ? OFFSET ?
                """;

        List<Object> args = new ArrayList<>();
        addPreviewQueryArgs(args, year, scope, region, country, search);
        args.add(scope);
        args.add(scope);
        args.add(scope);
        args.add(scope);
        args.add(pageSize);
        args.add(page * pageSize);

        return jdbcTemplate.queryForList(sql, args.toArray()).stream().map(row -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("canonicalUniversityId", row.get("canonical_university_id"));
            item.put("universityName", row.get("university_name"));
            item.put("slug", row.get("slug"));
            item.put("aggregatedRank", row.get("aggregated_rank"));
            item.put("globalRank", row.get("global_rank"));
            item.put("scopeRank", row.get("scope_rank"));
            item.put("compositeScore", row.get("composite_score"));
            item.put("primarySource", row.get("primary_source"));
            item.put("sourceCount", row.get("source_count"));
            item.put("rankingYear", row.get("ranking_year"));
            item.put("country", row.get("country"));
            return item;
        }).toList();
    }

    private long countPreviewRankings(Integer year, String search, String scope, String region, String country) {
        String sql = previewRankingsCte() + "SELECT COUNT(*) FROM filtered";
        List<Object> args = new ArrayList<>();
        addPreviewQueryArgs(args, year, scope, region, country, search);
        Long count = jdbcTemplate.queryForObject(sql, Long.class, args.toArray());
        return count == null ? 0L : count;
    }

    private void addPreviewQueryArgs(
            List<Object> args,
            Integer year,
            String scope,
            String region,
            String country,
            String search
    ) {
        args.add(year);
        args.add(year);
        args.add("region".equalsIgnoreCase(scope) ? region : null);
        args.add("region".equalsIgnoreCase(scope) ? region : null);
        args.add(country);
        args.add(country);
        for (int i = 0; i < 15; i++) {
            args.add(search);
        }
    }

    private String previewRankingsCte() {
        return """
                WITH admission_country AS (
                    SELECT
                        canonical_university_id,
                        MIN(NULLIF(country, '')) AS country
                    FROM warehouse.admission_records_preview
                    GROUP BY canonical_university_id
                ),
                per_university AS (
                    SELECT
                        rr.canonical_university_id,
                        MIN(cu.display_name) AS university_name,
                        MIN(cu.canonical_slug) AS slug,
                        COALESCE(ac.country, MIN(c.country_name), 'Unknown') AS country,
                        MIN(COALESCE(c.region_name, '')) AS region_name,
                        MIN(rr.rank_position) AS best_rank,
                        MIN(rr.ranking_year) AS ranking_year,
                        COUNT(DISTINCT COALESCE(rs.source_code, CAST(rr.ranking_source_id AS text))) AS source_count,
                        (
                            ARRAY_AGG(
                                COALESCE(rs.source_code, CAST(rr.ranking_source_id AS text))
                                ORDER BY rr.rank_position ASC,
                                         COALESCE(rs.source_code, CAST(rr.ranking_source_id AS text)) ASC
                            )
                        )[1] AS primary_source
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.canonical_university cu
                      ON cu.canonical_university_id = rr.canonical_university_id
                    LEFT JOIN warehouse.countries c
                      ON c.country_id = cu.country_id
                    LEFT JOIN warehouse.ranking_source rs
                      ON rs.ranking_source_id = rr.ranking_source_id
                    LEFT JOIN admission_country ac
                      ON ac.canonical_university_id = rr.canonical_university_id
                    WHERE rr.rank_position IS NOT NULL
                      AND rr.canonical_university_id IS NOT NULL
                      AND rr.universe_type = 'global'
                      AND (?::integer IS NULL OR rr.ranking_year = ?::integer)
                    GROUP BY rr.canonical_university_id, ac.country
                ),
                globally_ranked AS (
                    SELECT
                        pu.*,
                        ROW_NUMBER() OVER (
                            ORDER BY pu.best_rank ASC, pu.university_name ASC, pu.canonical_university_id ASC
                        ) AS global_rank
                    FROM per_university pu
                ),
                scope_ranked AS (
                    SELECT
                        gr.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY gr.region_name
                            ORDER BY gr.best_rank ASC, gr.university_name ASC, gr.canonical_university_id ASC
                        ) AS scope_rank
                    FROM globally_ranked gr
                    WHERE (?::text IS NULL OR gr.region_name = ?::text)
                ),
                filtered AS (
                    SELECT *
                    FROM scope_ranked sr
                    WHERE (?::text IS NULL OR lower(sr.country) = lower(?::text))
                      AND (
                          ?::text IS NULL
                          OR lower(sr.university_name) = lower(?::text)
                          OR lower(sr.university_name) LIKE lower(?::text) || '%%'
                          OR lower(sr.country) = lower(?::text)
                          OR lower(sr.country) LIKE lower(?::text) || '%%'
                          OR EXISTS (
                              SELECT 1
                              FROM warehouse.university_alias ua
                              WHERE ua.canonical_university_id = sr.canonical_university_id
                                AND (
                                    lower(ua.alias_text) = lower(?::text)
                                    OR lower(ua.alias_normalized) = lower(?::text)
                                    OR lower(ua.alias_text) LIKE lower(?::text) || '%%'
                                    OR lower(ua.alias_normalized) LIKE lower(?::text) || '%%'
                                    OR (
                                        char_length(?::text) >= 4
                                        AND (
                                            lower(ua.alias_text) LIKE '%%' || lower(?::text) || '%%'
                                            OR lower(ua.alias_normalized) LIKE '%%' || lower(?::text) || '%%'
                                        )
                                    )
                                )
                          )
                          OR (
                              char_length(?::text) >= 4
                              AND (
                                  lower(sr.university_name) LIKE '%%' || lower(?::text) || '%%'
                                  OR lower(sr.country) LIKE '%%' || lower(?::text) || '%%'
                              )
                          )
                      )
                )
                """;
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
