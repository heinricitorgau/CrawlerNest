package clawer.api;

import clawer.dto.ApiResponse;
import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.model.RecommendationGroupResponse;
import clawer.model.RecommendationResult;
import clawer.service.RecommendationEvidenceService;
import clawer.service.RecommendationService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;

class RecommendationControllerTest {

    @Test
    void testRecommendationsV2ReturnsGroupedJson() {
        FakeRecommendationService service = new FakeRecommendationService();
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
                "Classified as Target",
                "rank_agg_v1",
                Map.of(),
                List.of("category=target")
        );
        service.v2Response = new RecommendationGroupResponse(
                List.of(),
                List.of(target),
                List.of(),
                Map.of("risk_profile", "balanced")
        );

        RecommendationController controller = new RecommendationController(service, mock(RecommendationEvidenceService.class));
        Object response = controller.getRecommendations(
                "United Kingdom", null, null, null,
                6.5, null, 100, null,
                "balanced", null, null, null,
                null, null, null, null, null, null,
                null, null, 10, "v2"
        );

        ApiResponse<?> apiResponse = assertInstanceOf(ApiResponse.class, response);
        Map<?, ?> data = assertInstanceOf(Map.class, apiResponse.getData());
        List<?> targetRows = assertInstanceOf(List.class, data.get("target"));
        RecommendationResult first = assertInstanceOf(RecommendationResult.class, targetRows.get(0));
        assertEquals("target", first.getCategory());
        assertEquals("balanced", apiResponse.getMetadata().get("risk_profile"));
        assertEquals("United Kingdom", service.lastCountry);
    }

    @Test
    void testRecommendationsV3AcceptsScopeAndRegion() {
        FakeRecommendationService service = new FakeRecommendationService();
        service.v3Response = new RecommendationGroupResponse(
                List.of(),
                List.of(),
                List.of(),
                Map.of("version", "v3", "scope", "region", "region", "Europe")
        );

        RecommendationController controller = new RecommendationController(service, mock(RecommendationEvidenceService.class));
        Object response = controller.getRecommendations(
                "United Kingdom", "region", "Europe", "1,2",
                6.5, null, 100, null,
                "balanced", null, null, null,
                null, null, null, null, null, null,
                null, null, 5, "v3"
        );

        ApiResponse<?> apiResponse = assertInstanceOf(ApiResponse.class, response);
        assertEquals("region", apiResponse.getMetadata().get("scope"));
        assertEquals("Europe", apiResponse.getMetadata().get("region"));
        assertEquals("region", service.lastScope);
        assertEquals("Europe", service.lastRegion);
        assertEquals("1,2", service.lastShortlist);
    }

    @Test
    void testRecommendationsV3AcceptsSnakeCaseAliasesAndDefaultsToV3() {
        FakeRecommendationService service = new FakeRecommendationService();
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
                "Confidence is moderate.",
                "hybrid_scoring_v3",
                "decision_policy_v2",
                "explanation_templates_v2",
                "Classified as Safety",
                "rank_agg_v1",
                Map.of("risk_adjustment", 8.0),
                List.of("version=v3", "category=safety")
        );
        service.v3Response = new RecommendationGroupResponse(
                List.of(),
                List.of(),
                List.of(safety),
                Map.of("version", "v3", "risk_profile", "conservative", "country_policy", "hard_filter")
        );

        RecommendationController controller = new RecommendationController(service, mock(RecommendationEvidenceService.class));
        Object response = controller.getRecommendations(
                "United Kingdom", null, null, null,
                null, 6.5, null, 100,
                null, "conservative", null, "hard_filter",
                null, null, null, null, null, null,
                null, null, 3, "v3"
        );

        ApiResponse<?> apiResponse = assertInstanceOf(ApiResponse.class, response);
        Map<?, ?> data = assertInstanceOf(Map.class, apiResponse.getData());
        List<?> safetyRows = assertInstanceOf(List.class, data.get("safety"));
        RecommendationResult first = assertInstanceOf(RecommendationResult.class, safetyRows.get(0));
        assertEquals("safety", first.getCategory());
        assertEquals("hard_filter", apiResponse.getMetadata().get("country_policy"));
        assertEquals("conservative", apiResponse.getMetadata().get("risk_profile"));
    }

    @Test
    void testRecommendationsV3ReturnsBadRequestWhenTargetRankMissing() {
        RecommendationController controller = new RecommendationController(new FakeRecommendationService(), mock(RecommendationEvidenceService.class));

        assertThrows(ResponseStatusException.class, () -> controller.getRecommendations(
                "United Kingdom", null, null, null,
                6.5, null, null, null,
                "balanced", null, null, null,
                null, null, null, null, null, null,
                null, null, 10, null
        ));
    }

    private static final class FakeRecommendationService extends RecommendationService {
        private RecommendationGroupResponse v2Response;
        private RecommendationGroupResponse v3Response;
        private String lastCountry;
        private String lastScope;
        private String lastRegion;
        private String lastShortlist;

        private FakeRecommendationService() {
            super(new NoopScopedRankingReadAdapter(), mock(JdbcTemplate.class), new ObjectMapper());
        }

        @Override
        public RecommendationGroupResponse getRecommendationsV2(
                String country,
                String scope,
                String region,
                String shortlist,
                Double ieltsScore,
                Integer targetRank,
                String riskProfile,
                String preferredRankingSource,
                Integer rankingYear,
                Integer limit
        ) {
            this.lastCountry = country;
            this.lastScope = scope;
            this.lastRegion = region;
            this.lastShortlist = shortlist;
            return v2Response;
        }

        @Override
        public RecommendationGroupResponse getRecommendationsV3(
                String country,
                String scope,
                String region,
                String shortlist,
                String countryPolicy,
                Double ieltsScore,
                Integer targetRank,
                String riskProfile,
                String preferenceWeights,
                String preferredRankingSource,
                String subjectKey,
                Integer rankingYear,
                Integer limit
        ) {
            this.lastCountry = country;
            this.lastScope = scope;
            this.lastRegion = region;
            this.lastShortlist = shortlist;
            return v3Response;
        }
    }

    private static final class NoopScopedRankingReadAdapter implements ScopedRankingReadAdapter {
        @Override
        public List<ScopedRankedUniversity> findRankings(
                RankingContext context,
                Integer year,
                String search,
                String countryCode,
                String countryName,
                int page,
                int pageSize
        ) {
            return List.of();
        }

        @Override
        public List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search) {
            return List.of();
        }

        @Override
        public long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName) {
            return 0L;
        }

        @Override
        public List<ScopedRankedUniversity> findRecommendationCandidates(RankingContext context, Integer year, String country) {
            return List.of();
        }
    }
}
