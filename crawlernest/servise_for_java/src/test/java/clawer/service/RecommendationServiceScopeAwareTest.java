package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RecommendationServiceScopeAwareTest {

    @Test
    void regionModeUsesScopeRankAsPrimarySignal() throws Exception {
        RecommendationService service = new RecommendationService(new NoopScopedRankingReadAdapter(), new ObjectMapper());
        Object candidate = candidate(1L, "ETH Zurich", "Switzerland", 15, 80, 6.0);

        Object globalContext = scopeContext("global", null);
        Object regionContext = scopeContext("region", "Europe");

        Object globalResult = invokeScoreCandidateV3(service, candidate, globalContext, 50, "balanced");
        Object regionResult = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");

        assertEquals(15, readInt(globalResult, "aggregatedRank"));
        assertEquals(80, readInt(regionResult, "aggregatedRank"));
        assertEquals(15, readInt(regionResult, "globalRank"));
        assertEquals(80, readInt(regionResult, "scopeRank"));
        assertNotEquals(readString(globalResult, "category"), readString(regionResult, "category"));
    }

    @Test
    void regionExplanationIncludesRegionalAndGlobalLanguage() throws Exception {
        RecommendationService service = new RecommendationService(new NoopScopedRankingReadAdapter(), new ObjectMapper());
        Object candidate = candidate(2L, "University of Oxford", "United Kingdom", 15, 7, 6.5);
        Object regionContext = scopeContext("region", "Europe");

        Object result = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");
        String explanation = readString(result, "explanation");

        assertTrue(explanation.contains("Ranked #7 in Europe"));
        assertTrue(explanation.contains("global position"));
    }

    @Test
    void sameInputsProduceDeterministicRegionScore() throws Exception {
        RecommendationService service = new RecommendationService(new NoopScopedRankingReadAdapter(), new ObjectMapper());
        Object candidate = candidate(3L, "TU Delft", "Netherlands", 40, 12, 6.5);
        Object regionContext = scopeContext("region", "Europe");

        Object first = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");
        Object second = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");

        assertEquals(readDouble(first, "matchingScore"), readDouble(second, "matchingScore"));
        assertEquals(readString(first, "explanation"), readString(second, "explanation"));
    }

    private Object invokeScoreCandidateV3(
            RecommendationService service,
            Object candidate,
            Object scopeContext,
            int targetRank,
            String riskProfile
    ) throws Exception {
        Method method = RecommendationService.class.getDeclaredMethod(
                "scoreCandidateV3",
                candidate.getClass(),
                String.class,
                String.class,
                Double.class,
                Integer.class,
                String.class,
                Map.class,
                String.class,
                Class.forName("clawer.service.RecommendationService$PoolContext"),
                scopeContext.getClass()
        );
        method.setAccessible(true);
        return method.invoke(
                service,
                candidate,
                null,
                null,
                6.5,
                targetRank,
                riskProfile,
                Map.of("ranking", 0.5, "ielts", 0.2, "confidence", 0.2, "country_match", 0.1),
                null,
                null,
                scopeContext
        );
    }

    private Object candidate(Long id, String name, String country, Integer globalRank, Integer scopeRank, Double ieltsMin) throws Exception {
        Class<?> candidateClass = Class.forName("clawer.service.RecommendationService$Candidate");
        Constructor<?> constructor = candidateClass.getDeclaredConstructor();
        constructor.setAccessible(true);
        Object candidate = constructor.newInstance();
        write(candidate, "canonicalUniversityId", id);
        write(candidate, "universityName", name);
        write(candidate, "country", country);
        write(candidate, "aggregatedRank", globalRank);
        write(candidate, "globalRank", globalRank);
        write(candidate, "scopeRank", scopeRank);
        write(candidate, "coverageRatio", 1.0);
        write(candidate, "ieltsMin", ieltsMin);
        write(candidate, "aggregationMethodVersion", "rank_agg_v1");
        write(candidate, "sourceRanks", Map.of("QS", globalRank));
        return candidate;
    }

    private Object scopeContext(String scope, String region) {
        return RankingContext.fromQuery(scope, region);
    }

    private void write(Object target, String fieldName, Object value) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(target, value);
    }

    private Integer readInt(Object target, String fieldName) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return (Integer) field.get(target);
    }

    private Double readDouble(Object target, String fieldName) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return (Double) field.get(target);
    }

    private String readString(Object target, String fieldName) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return (String) field.get(target);
    }

    private static final class NoopScopedRankingReadAdapter implements ScopedRankingReadAdapter {
        @Override
        public java.util.List<ScopedRankedUniversity> findRankings(RankingContext context, Integer year, String search, int page, int pageSize) {
            return java.util.List.of();
        }

        @Override
        public long countRankings(RankingContext context, Integer year, String search) {
            return 0;
        }

        @Override
        public java.util.List<ScopedRankedUniversity> findRecommendationCandidates(RankingContext context, Integer year, String country) {
            return java.util.List.of();
        }
    }
}
