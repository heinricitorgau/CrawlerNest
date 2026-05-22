package clawer.api;

import clawer.service.RecommendationEvidenceService;
import clawer.service.RecommendationService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;
    private final RecommendationEvidenceService evidenceService;

    public RecommendationController(
            RecommendationService recommendationService,
            RecommendationEvidenceService evidenceService
    ) {
        this.recommendationService = recommendationService;
        this.evidenceService = evidenceService;
    }

    @GetMapping
    public Object getRecommendations(
            @RequestParam(required = false) String country,
            @RequestParam(required = false) String scope,
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String shortlist,
            @RequestParam(name = "ielts", required = false) Double ielts,
            @RequestParam(name = "ieltsScore", required = false) Double ieltsScore,
            @RequestParam(name = "targetRank", required = false) Integer targetRank,
            @RequestParam(name = "target_rank", required = false) Integer targetRankSnakeCase,
            @RequestParam(name = "riskProfile", required = false) String riskProfile,
            @RequestParam(name = "risk_profile", required = false) String riskProfileSnakeCase,
            @RequestParam(name = "countryPolicy", required = false) String countryPolicy,
            @RequestParam(name = "country_policy", required = false) String countryPolicySnakeCase,
            @RequestParam(name = "preferenceWeights", required = false) String preferenceWeights,
            @RequestParam(name = "preference_weights", required = false) String preferenceWeightsSnakeCase,
            @RequestParam(name = "preferredRankingSource", required = false) String preferredRankingSource,
            @RequestParam(name = "preferred_ranking_source", required = false) String preferredRankingSourceSnakeCase,
            @RequestParam(name = "rankingYear", required = false) Integer rankingYear,
            @RequestParam(name = "ranking_year", required = false) Integer rankingYearSnakeCase,
            @RequestParam(name = "subject", required = false) String subject,
            @RequestParam(name = "subject_key", required = false) String subjectSnakeCase,
            @RequestParam(defaultValue = "10") Integer limit,
            @RequestParam(defaultValue = "v3") String version
    ) {
        try {
            Double resolvedIelts = firstNonNull(ielts, ieltsScore);
            Integer resolvedTargetRank = firstNonNull(targetRank, targetRankSnakeCase);
            String resolvedRiskProfile = firstNonBlank(riskProfile, riskProfileSnakeCase);
            String resolvedCountryPolicy = firstNonBlank(countryPolicy, countryPolicySnakeCase);
            String resolvedPreferenceWeights = firstNonBlank(preferenceWeights, preferenceWeightsSnakeCase);
            String resolvedPreferredRankingSource = firstNonBlank(preferredRankingSource, preferredRankingSourceSnakeCase);
            Integer resolvedRankingYear = firstNonNull(rankingYear, rankingYearSnakeCase);
            String resolvedSubject = firstNonBlank(subject, subjectSnakeCase);

            if ("v1".equalsIgnoreCase(version)) {
                return clawer.dto.ApiResponse.success(recommendationService.getRecommendations(
                        country,
                        scope,
                        region,
                        shortlist,
                        resolvedIelts,
                        resolvedTargetRank,
                        resolvedPreferredRankingSource,
                        resolvedRankingYear,
                        limit
                ));
            }
            if ("v3".equalsIgnoreCase(version)) {
                if (resolvedTargetRank == null) {
                    throw new IllegalArgumentException("targetRank is required for recommendation v3.");
                }
                clawer.model.RecommendationGroupResponse res = recommendationService.getRecommendationsV3(
                        country,
                        scope,
                        region,
                        shortlist,
                        resolvedCountryPolicy,
                        resolvedIelts,
                        resolvedTargetRank,
                        resolvedRiskProfile,
                        resolvedPreferenceWeights,
                        resolvedPreferredRankingSource,
                        resolvedSubject,
                        resolvedRankingYear,
                        limit
                );
                return clawer.dto.ApiResponse.success(Map.of(
                        "reach", res.getReach(),
                        "target", res.getTarget(),
                        "safety", res.getSafety()
                ), res.getMetadata());
            }
            if (resolvedTargetRank == null) {
                throw new IllegalArgumentException("targetRank is required for recommendation v2.");
            }
            clawer.model.RecommendationGroupResponse res = recommendationService.getRecommendationsV2(
                    country,
                    scope,
                    region,
                    shortlist,
                    resolvedIelts,
                    resolvedTargetRank,
                    resolvedRiskProfile,
                    resolvedPreferredRankingSource,
                    resolvedRankingYear,
                    limit
            );
            return clawer.dto.ApiResponse.success(Map.of(
                    "reach", res.getReach(),
                    "target", res.getTarget(),
                    "safety", res.getSafety()
            ), res.getMetadata());
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }

    /**
     * GET /api/v1/recommendations/explain
     *
     * Returns evidence backing a recommendation for a specific university.
     * Readonly — does not recalculate scores or mutate any data.
     * Returns 404 if the university is not found.
     */
    @GetMapping("/explain")
    public Object getExplain(
            @RequestParam(name = "canonicalUniversityId") Long canonicalUniversityId,
            @RequestParam(name = "ieltsScore", required = false) Double ieltsScore,
            @RequestParam(name = "targetRank", required = false) Integer targetRank,
            @RequestParam(name = "country", required = false) String country,
            @RequestParam(name = "subjectKey", required = false) String subjectKey
    ) {
        if (canonicalUniversityId == null || canonicalUniversityId <= 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "canonicalUniversityId is required and must be positive.");
        }
        Map<String, Object> evidence = evidenceService.getEvidence(
                canonicalUniversityId, ieltsScore, targetRank, country, subjectKey
        );
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("timestamp", Instant.now().toString());
        metadata.put("endpoint", "recommendations/explain");
        metadata.put("readonly", true);
        metadata.put("canonical_university_id", canonicalUniversityId);
        return clawer.dto.ApiResponse.success(evidence, metadata);
    }

    private static <T> T firstNonNull(T primary, T secondary) {
        return primary != null ? primary : secondary;
    }

    private static String firstNonBlank(String primary, String secondary) {
        if (primary != null && !primary.isBlank()) {
            return primary;
        }
        if (secondary != null && !secondary.isBlank()) {
            return secondary;
        }
        return null;
    }
}
