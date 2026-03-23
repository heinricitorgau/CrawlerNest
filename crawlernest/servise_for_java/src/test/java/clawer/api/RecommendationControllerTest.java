package clawer.api;

import clawer.model.RecommendationGroupResponse;
import clawer.model.RecommendationResult;
import clawer.service.RecommendationService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(RecommendationController.class)
class RecommendationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private RecommendationService recommendationService;

    @Test
    void testRecommendationsV2ReturnsGroupedJson() throws Exception {
        RecommendationResult target = new RecommendationResult(
                1L,
                "Target Uni",
                "United Kingdom",
                92,
                6.0,
                89.4,
                "target",
                null,
                92.0,
                "Confidence is high based on ranking-source agreement and data completeness.",
                "hybrid_scoring_v3",
                "decision_policy_v1",
                "explanation_templates_v1",
                "Classified as Target: rank #92 sits close to your target #100, so it is a balanced option. Recommended because ranking score is 88.00, confidence is high, overall fit score is 89.40.",
                "rank_agg_v1",
                Map.of(),
                List.of("category=target")
        );
        RecommendationGroupResponse response = new RecommendationGroupResponse(
                List.of(),
                List.of(target),
                List.of(),
                Map.of("risk_profile", "balanced")
        );

        when(recommendationService.getRecommendationsV2(
                eq("United Kingdom"),
                eq(6.5),
                eq(100),
                eq("balanced"),
                eq(null),
                eq(null),
                eq(10)
        )).thenReturn(response);

        mockMvc.perform(get("/recommendations")
                        .param("country", "United Kingdom")
                        .param("ielts", "6.5")
                        .param("targetRank", "100")
                        .param("riskProfile", "balanced")
                        .param("version", "v2")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.target[0].category").value("target"))
                .andExpect(jsonPath("$.metadata.risk_profile").value("balanced"));
    }

    @Test
    void testRecommendationsV3AcceptsPreferenceWeights() throws Exception {
        RecommendationResult reach = new RecommendationResult(
                2L,
                "Reach Uni",
                "United States",
                40,
                6.5,
                91.2,
                "reach",
                "strong",
                88.0,
                "Confidence is high because data completeness and ranking-source agreement support this decision.",
                "hybrid_scoring_v3",
                "decision_policy_v2",
                "explanation_templates_v2",
                "Boosted due to aggressive profile favoring higher-ranked universities.",
                "rank_agg_v1",
                Map.of("country_match_score", 25.0),
                List.of("version=v3")
        );
        RecommendationGroupResponse response = new RecommendationGroupResponse(
                List.of(reach),
                List.of(),
                List.of(),
                Map.of("risk_profile", "aggressive", "version", "v3", "country_policy", "none")
        );

        when(recommendationService.getRecommendationsV3(
                eq("United Kingdom"),
                eq(null),
                eq(6.5),
                eq(100),
                eq("aggressive"),
                eq("{\"ranking\":0.6,\"ielts\":0.15,\"confidence\":0.15,\"country_match\":0.1}"),
                eq(null),
                eq(null),
                eq(10)
        )).thenReturn(response);

        mockMvc.perform(get("/recommendations")
                        .param("country", "United Kingdom")
                        .param("ielts", "6.5")
                        .param("targetRank", "100")
                        .param("riskProfile", "aggressive")
                        .param("preferenceWeights", "{\"ranking\":0.6,\"ielts\":0.15,\"confidence\":0.15,\"country_match\":0.1}")
                        .param("version", "v3")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.reach[0].preferenceAlignment").value("strong"))
                .andExpect(jsonPath("$.reach[0].recommendationConfidence").value(88.0))
                .andExpect(jsonPath("$.reach[0].scoringVersion").value("hybrid_scoring_v3"))
                .andExpect(jsonPath("$.metadata.version").value("v3"));
    }

    @Test
    void testRecommendationsV3AcceptsSnakeCaseAliasesAndDefaultsToV3() throws Exception {
        RecommendationResult safety = new RecommendationResult(
                3L,
                "Safety Uni",
                "United Kingdom",
                130,
                6.0,
                84.1,
                "safety",
                "moderate",
                81.0,
                "Confidence is moderate because ranking coverage is solid but some admission data is missing.",
                "hybrid_scoring_v3",
                "decision_policy_v2",
                "explanation_templates_v2",
                "Classified as Safety: rank #130 is below your target threshold #100, so it is a lower-risk option.",
                "rank_agg_v1",
                Map.of("risk_adjustment", 8.0),
                List.of("version=v3", "category=safety")
        );
        RecommendationGroupResponse response = new RecommendationGroupResponse(
                List.of(),
                List.of(),
                List.of(safety),
                Map.of("version", "v3", "risk_profile", "conservative", "country_policy", "hard_filter")
        );

        when(recommendationService.getRecommendationsV3(
                eq("United Kingdom"),
                eq("hard_filter"),
                eq(6.5),
                eq(100),
                eq("conservative"),
                eq(null),
                eq(null),
                eq(null),
                eq(3)
        )).thenReturn(response);

        mockMvc.perform(get("/recommendations")
                        .param("country", "United Kingdom")
                        .param("country_policy", "hard_filter")
                        .param("ieltsScore", "6.5")
                        .param("target_rank", "100")
                        .param("risk_profile", "conservative")
                        .param("limit", "3")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.safety[0].category").value("safety"))
                .andExpect(jsonPath("$.safety[0].recommendationConfidence").value(81.0))
                .andExpect(jsonPath("$.metadata.version").value("v3"))
                .andExpect(jsonPath("$.metadata.country_policy").value("hard_filter"))
                .andExpect(jsonPath("$.metadata.risk_profile").value("conservative"));
    }

    @Test
    void testRecommendationsV3ReturnsBadRequestWhenTargetRankMissing() throws Exception {
        mockMvc.perform(get("/recommendations")
                        .param("country", "United Kingdom")
                        .param("ielts", "6.5")
                        .param("riskProfile", "balanced")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest());
    }
}
