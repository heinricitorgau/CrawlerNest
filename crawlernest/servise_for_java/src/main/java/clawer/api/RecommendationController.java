package clawer.api;

import clawer.model.RecommendationResult;
import clawer.service.RecommendationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    public RecommendationController(RecommendationService recommendationService) {
        this.recommendationService = recommendationService;
    }

    @GetMapping
    public List<RecommendationResult> getRecommendations(
            @RequestParam(required = false) String country,
            @RequestParam(required = false) Double ielts,
            @RequestParam(required = false) Integer targetRank,
            @RequestParam(required = false) String preferredRankingSource,
            @RequestParam(required = false) Integer rankingYear,
            @RequestParam(defaultValue = "10") Integer limit
    ) {
        return recommendationService.getRecommendations(
                country,
                ielts,
                targetRank,
                preferredRankingSource,
                rankingYear,
                limit
        );
    }
}
