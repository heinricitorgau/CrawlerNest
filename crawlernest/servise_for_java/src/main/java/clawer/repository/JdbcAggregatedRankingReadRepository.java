package clawer.repository;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.dto.RankingDTO;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public class JdbcAggregatedRankingReadRepository implements AggregatedRankingReadRepository {
    private final ScopedRankingReadAdapter scopedRankingReadAdapter;

    public JdbcAggregatedRankingReadRepository(ScopedRankingReadAdapter scopedRankingReadAdapter) {
        this.scopedRankingReadAdapter = scopedRankingReadAdapter;
    }

    @Override
    public List<RankingDTO> findRankings(
            Integer year,
            String search,
            String scope,
            String region,
            int page,
            int pageSize
    ) {
        RankingContext context = RankingContext.fromQuery(scope, region);
        return scopedRankingReadAdapter.findRankings(context, year, search, page, pageSize)
                .stream()
                .map(row -> toRankingDto(row, context))
                .toList();
    }

    @Override
    public long countRankings(Integer year, String search, String scope, String region) {
        RankingContext context = RankingContext.fromQuery(scope, region);
        return scopedRankingReadAdapter.countRankings(context, year, search);
    }

    private RankingDTO toRankingDto(ScopedRankedUniversity row, RankingContext context) {
        RankingDTO dto = new RankingDTO();
        dto.setCanonicalUniversityId(row.getCanonicalUniversityId());
        dto.setUniversityName(row.getUniversityName());
        dto.setCountry(row.getCountry());
        dto.setSlug(row.getSlug());
        dto.setAggregatedRank(row.rankedPosition(context).compatibilityAggregatedRank());
        dto.setGlobalRank(row.getGlobalRank());
        dto.setScopeRank(context.isRegion() ? row.getScopeRank() : null);
        dto.setCompositeScore(row.getCompositeScore());
        dto.setRankingYear(row.getRankingYear());
        dto.setPrimarySource("AGGREGATED");
        dto.setSourceCount(row.getSourceCount());
        return dto;
    }
}
