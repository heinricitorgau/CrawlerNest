package clawer.api;

import clawer.model.RecommendationResult;
import clawer.service.RecommendationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST Controller for generating University recommendations.
 */
@RestController
@RequestMapping("/recommendations")
public class RecommendationController {

    private final RecommendationService recommendationService;

    public RecommendationController(RecommendationService recommendationService) {
        this.recommendationService = recommendationService;
    }

    /**
     * Generates recommendations based on preferred subject and student's admission score.
     * @param subject The preferred field of study (e.g., "Computer Science")
     * @param score The student's admission score (e.g., 90.0)
     * @return List of recommended Universities with match scores
     */
    @GetMapping
    public List<RecommendationResult> getRecommendations(
            @RequestParam(required = false) String subject,
            @RequestParam(required = false) Double score) {
        
        return recommendationService.getRecommendations(subject, score);
    }
}
