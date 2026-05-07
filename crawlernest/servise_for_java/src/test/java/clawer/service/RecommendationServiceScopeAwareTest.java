package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.model.RecommendationGroupResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

class RecommendationServiceScopeAwareTest {

    @Test
    void regionModeUsesScopeRankAsPrimarySignal() throws Exception {
        RecommendationService service = service(new NoopScopedRankingReadAdapter());
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
        RecommendationService service = service(new NoopScopedRankingReadAdapter());
        Object candidate = candidate(2L, "University of Oxford", "United Kingdom", 15, 7, 6.5);
        Object regionContext = scopeContext("region", "Europe");

        Object result = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");
        String explanation = readString(result, "explanation");

        assertTrue(explanation.contains("Ranked #7 in Europe"));
        assertTrue(explanation.contains("global position"));
    }

    @Test
    void sameInputsProduceDeterministicRegionScore() throws Exception {
        RecommendationService service = service(new NoopScopedRankingReadAdapter());
        Object candidate = candidate(3L, "TU Delft", "Netherlands", 40, 12, 6.5);
        Object regionContext = scopeContext("region", "Europe");

        Object first = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");
        Object second = invokeScoreCandidateV3(service, candidate, regionContext, 50, "balanced");

        assertEquals(readDouble(first, "matchingScore"), readDouble(second, "matchingScore"));
        assertEquals(readString(first, "explanation"), readString(second, "explanation"));
    }

    @Test
    void recommendationExplainShowsReasonsAndWarnings() throws Exception {
        RecommendationService service = service(new NoopScopedRankingReadAdapter());
        Object candidate = candidate(4L, "Imperial College London", "United Kingdom", 42, 42, 7.5, Map.of("QS", 6, "THE", 9, "ARWU", 11));
        Object globalContext = scopeContext("global", null);

        Object result = invokeScoreCandidateV3(service, candidate, globalContext, 50, "balanced");
        Object explain = readObject(result, "recommendationExplain");

        assertNotNull(explain);
        assertTrue(readDouble(explain, "fitScore") > 0.0);
        assertTrue(readStringList(explain, "reasons").stream().anyMatch(value -> value.contains("target")));
        assertTrue(readStringList(explain, "warnings").stream().anyMatch(value -> value.contains("IELTS") || value.contains("confidence") || value.contains("source")));
    }

    @Test
    void recommendationResultsAreDeduplicatedByCanonicalUniversityId() {
        RecommendationService service = service(new DuplicateScopedRankingReadAdapter());
        RecommendationGroupResponse response = service.getRecommendationsV3(
                "United Kingdom",
                "global",
                null,
                null,
                "hard_filter",
                6.5,
                50,
                "balanced",
                null,
                null,
                null,
                2026,
                5
        );

        long duplicateIdCount = response.getTarget().stream()
                .filter(item -> item.getCanonicalUniversityId() == 101L)
                .count();

        assertEquals(1L, duplicateIdCount);
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
                Class.forName("clawer.service.RecommendationService$SubjectScoringContext"),
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
                disabledSubjectScoringContext(),
                null,
                scopeContext
        );
    }

    private Object disabledSubjectScoringContext() throws Exception {
        Class<?> subjectContextClass = Class.forName("clawer.service.RecommendationService$SubjectScoringContext");
        Constructor<?> constructor = subjectContextClass.getDeclaredConstructor(String.class, String.class, Map.class);
        constructor.setAccessible(true);
        return constructor.newInstance(null, null, Map.of());
    }

    private RecommendationService service(ScopedRankingReadAdapter adapter) {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        return new RecommendationService(adapter, jdbcTemplate, new ObjectMapper());
    }

    private Object candidate(Long id, String name, String country, Integer globalRank, Integer scopeRank, Double ieltsMin) throws Exception {
        return candidate(id, name, country, globalRank, scopeRank, ieltsMin, Map.of("QS", globalRank));
    }

    private Object candidate(Long id, String name, String country, Integer globalRank, Integer scopeRank, Double ieltsMin, Map<String, Integer> sourceRanks) throws Exception {
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
        write(candidate, "sourceRanks", sourceRanks);
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

    private Object readObject(Object target, String fieldName) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return field.get(target);
    }

    @SuppressWarnings("unchecked")
    private List<String> readStringList(Object target, String fieldName) throws Exception {
        Field field = target.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return (List<String>) field.get(target);
    }

    private static final class NoopScopedRankingReadAdapter implements ScopedRankingReadAdapter {
        @Override
        public java.util.List<ScopedRankedUniversity> findRankings(
                RankingContext context,
                Integer year,
                String search,
                String countryCode,
                String countryName,
                int page,
                int pageSize
        ) {
            return java.util.List.of();
        }

        @Override
        public long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName) {
            return 0L;
        }

        @Override
        public java.util.List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search) {
            return java.util.List.of();
        }

        @Override
        public java.util.List<ScopedRankedUniversity> findRecommendationCandidates(RankingContext context, Integer year, String country) {
            return java.util.List.of();
        }
    }

    private static final class DuplicateScopedRankingReadAdapter implements ScopedRankingReadAdapter {
        @Override
        public java.util.List<ScopedRankedUniversity> findRankings(
                RankingContext context,
                Integer year,
                String search,
                String countryCode,
                String countryName,
                int page,
                int pageSize
        ) {
            return java.util.List.of();
        }

        @Override
        public long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName) {
            return 0L;
        }

        @Override
        public java.util.List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search) {
            return java.util.List.of();
        }

        @Override
        public java.util.List<ScopedRankedUniversity> findRecommendationCandidates(RankingContext context, Integer year, String country) {
            ScopedRankedUniversity stronger = new ScopedRankedUniversity();
            stronger.setCanonicalUniversityId(101L);
            stronger.setUniversityName("Duplicate University");
            stronger.setCountry("United Kingdom");
            stronger.setRankingYear(2026);
            stronger.setGlobalRank(42);
            stronger.setScopeRank(42);
            stronger.setCoverageRatio(1.0);
            stronger.setIeltsMin(6.5);
            stronger.setAggregationMethodVersion("rank_agg_v2");
            stronger.setSourceRanks(Map.of("QS", 42, "THE", 45));

            ScopedRankedUniversity weaker = new ScopedRankedUniversity();
            weaker.setCanonicalUniversityId(101L);
            weaker.setUniversityName("Duplicate University");
            weaker.setCountry("United Kingdom");
            weaker.setRankingYear(2026);
            weaker.setGlobalRank(90);
            weaker.setScopeRank(90);
            weaker.setCoverageRatio(0.5);
            weaker.setIeltsMin(7.0);
            weaker.setAggregationMethodVersion("rank_agg_v2");
            weaker.setSourceRanks(Map.of("QS", 90));

            return java.util.List.of(stronger, weaker);
        }
    }
}
