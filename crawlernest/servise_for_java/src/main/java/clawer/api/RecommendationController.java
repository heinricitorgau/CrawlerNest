package clawer.api;

import clawer.model.RecommendationResult;
import clawer.service.RecommendationService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

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
            @RequestParam(required = false) Double ielts,
            @RequestParam(required = false) Integer targetRank,
            @RequestParam(required = false) String riskProfile,
            @RequestParam(required = false) String preferenceWeights,
            @RequestParam(required = false) String preferredRankingSource,
            @RequestParam(required = false) Integer rankingYear,
            @RequestParam(defaultValue = "10") Integer limit,
            @RequestParam(defaultValue = "v2") String version
    ) {
        try {
            if ("v1".equalsIgnoreCase(version)) {
                return recommendationService.getRecommendations(
                        country,
                        ielts,
                        targetRank,
                        preferredRankingSource,
                        rankingYear,
                        limit
                );
            }
            if ("v3".equalsIgnoreCase(version)) {
                if (targetRank == null) {
                    throw new IllegalArgumentException("targetRank is required for recommendation v3.");
                }
                return recommendationService.getRecommendationsV3(
                        country,
                        ielts,
                        targetRank,
                        riskProfile,
                        preferenceWeights,
                        preferredRankingSource,
                        rankingYear,
                        limit
                );
            }
            if (targetRank == null) {
                throw new IllegalArgumentException("targetRank is required for recommendation v2.");
            }
            return recommendationService.getRecommendationsV2(
                    country,
                    ielts,
                    targetRank,
                    riskProfile,
                    preferredRankingSource,
                    rankingYear,
                    limit
            );
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }
}
