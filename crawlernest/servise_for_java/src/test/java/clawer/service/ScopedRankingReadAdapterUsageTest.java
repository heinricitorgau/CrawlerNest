package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.dto.RankingDTO;
import clawer.model.RecommendationGroupResponse;
import clawer.model.RecommendationResult;
import clawer.repository.JdbcAggregatedRankingReadRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.mock;

class ScopedRankingReadAdapterUsageTest {

    @Test
    void rankingsRepositoryDelegatesScopedUniverseToSharedAdapter() {
        ScopedRankedUniversity row = baseRow(1L, "ETH Zurich", "Switzerland", "eth-zurich", 15, 7);
        FakeScopedRankingReadAdapter adapter = new FakeScopedRankingReadAdapter(List.of(row));
        JdbcAggregatedRankingReadRepository repository = new JdbcAggregatedRankingReadRepository(adapter);

        List<RankingDTO> results = repository.findRankings(2026, null, "region", "Europe", null, null, 0, 20);

        assertEquals(1, results.size());
        assertEquals("region", adapter.lastContext.apiScope());
        assertEquals("Europe", adapter.lastContext.region());
        assertEquals(7, results.get(0).getAggregatedRank());
        assertEquals(15, results.get(0).getGlobalRank());
        assertEquals(7, results.get(0).getScopeRank());
    }

    @Test
    void recommendationServiceBuildsCandidatesFromSharedAdapter() {
        ScopedRankedUniversity row = baseRow(2L, "University of Oxford", "United Kingdom", "oxford", 15, 7);
        row.setCoverageRatio(1.0);
        row.setIeltsMin(6.5);
        row.setAggregationMethodVersion("rank_agg_v1");
        row.setSourceRanks(Map.of("QS", 15));

        FakeScopedRankingReadAdapter adapter = new FakeScopedRankingReadAdapter(List.of(row));
        RecommendationService service = new RecommendationService(adapter, mock(JdbcTemplate.class), new ObjectMapper());

        RecommendationGroupResponse response = service.getRecommendationsV3(
                null,
                "region",
                "Europe",
                null,
                null,
                7.0,
                50,
                "balanced",
                null,
                null,
                null,
                2026,
                5
        );

        RecommendationResult result = response.getReach().isEmpty()
                ? response.getTarget().isEmpty() ? response.getSafety().get(0) : response.getTarget().get(0)
                : response.getReach().get(0);

        assertEquals("region", adapter.lastContext.apiScope());
        assertEquals("Europe", adapter.lastContext.region());
        assertEquals(7, result.getAggregatedRank());
        assertEquals(15, result.getGlobalRank());
        assertEquals(7, result.getScopeRank());
        assertNotNull(result.getExplanation());
    }

    @Test
    void recommendationNaturallySeesImprovedRegionCoverageFromSharedAdapter() {
        ScopedRankedUniversity row = baseRow(29L, "University of Barcelona", "Spain", "barcelona", 120, 18);
        row.setCoverageRatio(1.0);
        row.setIeltsMin(6.0);
        row.setAggregationMethodVersion("rank_agg_v1");
        row.setSourceRanks(Map.of("QS", 45));

        FakeScopedRankingReadAdapter adapter = new FakeScopedRankingReadAdapter(List.of(row));
        RecommendationService service = new RecommendationService(adapter, mock(JdbcTemplate.class), new ObjectMapper());

        RecommendationGroupResponse response = service.getRecommendationsV3(
                null,
                "region",
                "Europe",
                null,
                null,
                7.0,
                30,
                "balanced",
                null,
                null,
                null,
                2026,
                5
        );

        RecommendationResult result = response.getReach().isEmpty()
                ? response.getTarget().isEmpty() ? response.getSafety().get(0) : response.getTarget().get(0)
                : response.getReach().get(0);

        assertEquals("University of Barcelona", result.getUniversityName());
        assertEquals(120, result.getGlobalRank());
        assertEquals(18, result.getScopeRank());
        assertEquals(18, result.getAggregatedRank());
    }

    private ScopedRankedUniversity baseRow(
            Long canonicalUniversityId,
            String universityName,
            String country,
            String slug,
            Integer globalRank,
            Integer scopeRank
    ) {
        ScopedRankedUniversity row = new ScopedRankedUniversity();
        row.setCanonicalUniversityId(canonicalUniversityId);
        row.setUniversityName(universityName);
        row.setCountry(country);
        row.setSlug(slug);
        row.setRankingYear(2026);
        row.setGlobalRank(globalRank);
        row.setScopeRank(scopeRank);
        row.setCompositeScore(95.0);
        row.setSourceCount(1);
        return row;
    }

    private static final class FakeScopedRankingReadAdapter implements ScopedRankingReadAdapter {
        private final List<ScopedRankedUniversity> rows;
        private RankingContext lastContext;

        private FakeScopedRankingReadAdapter(List<ScopedRankedUniversity> rows) {
            this.rows = rows;
        }

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
            this.lastContext = context;
            return rows;
        }

        @Override
        public long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName) {
            this.lastContext = context;
            return rows.size();
        }

        @Override
        public List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search) {
            this.lastContext = context;
            return List.of();
        }

        @Override
        public List<ScopedRankedUniversity> findRecommendationCandidates(RankingContext context, Integer year, String country) {
            this.lastContext = context;
            return rows;
        }
    }
}
