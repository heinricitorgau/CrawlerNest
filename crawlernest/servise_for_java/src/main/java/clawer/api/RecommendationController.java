package clawer.api;

import clawer.service.RecommendationService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    public RecommendationController(RecommendationService recommendationService) {
        this.recommendationService = recommendationService;
    }

    @GetMapping
    public Object getRecommendations(
            @RequestParam(required = false) String country,
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

            if ("v1".equalsIgnoreCase(version)) {
                return recommendationService.getRecommendations(
                        country,
                        resolvedIelts,
                        resolvedTargetRank,
                        resolvedPreferredRankingSource,
                        resolvedRankingYear,
                        limit
                );
            }
            if ("v3".equalsIgnoreCase(version)) {
                if (resolvedTargetRank == null) {
                    throw new IllegalArgumentException("targetRank is required for recommendation v3.");
                }
                return recommendationService.getRecommendationsV3(
                        country,
                        resolvedCountryPolicy,
                        resolvedIelts,
                        resolvedTargetRank,
                        resolvedRiskProfile,
                        resolvedPreferenceWeights,
                        resolvedPreferredRankingSource,
                        resolvedRankingYear,
                        limit
                );
            }
            if (resolvedTargetRank == null) {
                throw new IllegalArgumentException("targetRank is required for recommendation v2.");
            }
            return recommendationService.getRecommendationsV2(
                    country,
                    resolvedIelts,
                    resolvedTargetRank,
                    resolvedRiskProfile,
                    resolvedPreferredRankingSource,
                    resolvedRankingYear,
                    limit
            );
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
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
