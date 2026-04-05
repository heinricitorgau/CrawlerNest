package clawer.repository;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.dto.RankingCountryOptionDTO;
import clawer.dto.RankingDTO;
import clawer.dto.RankingTrustDTO;
import clawer.service.AggregationExplainability;
import clawer.service.RankingTrustLayer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

@Repository
public class JdbcAggregatedRankingReadRepository implements AggregatedRankingReadRepository {
    private static final Logger LOGGER = LoggerFactory.getLogger(JdbcAggregatedRankingReadRepository.class);
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
            String countryCode,
            String countryName,
            int page,
            int pageSize
    ) {
        RankingContext context = RankingContext.fromQuery(scope, region);
        return scopedRankingReadAdapter.findRankings(context, year, search, countryCode, countryName, page, pageSize)
                .stream()
                .map(row -> toRankingDto(row, context))
                .toList();
    }

    @Override
    public long countRankings(Integer year, String search, String scope, String region, String countryCode, String countryName) {
        RankingContext context = RankingContext.fromQuery(scope, region);
        return scopedRankingReadAdapter.countRankings(context, year, search, countryCode, countryName);
    }

    @Override
    public List<RankingCountryOptionDTO> findCountryOptions(Integer year, String search, String scope, String region) {
        RankingContext context = RankingContext.fromQuery(scope, region);
        return scopedRankingReadAdapter.findCountryOptions(context, year, search)
                .stream()
                .map(this::toCountryOptionDto)
                .toList();
    }

    private RankingDTO toRankingDto(ScopedRankedUniversity row, RankingContext context) {
        RankingDTO dto = new RankingDTO();
        int actualSourceCount = row.getSourceRanks() == null ? 0 : row.getSourceRanks().size();
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
        dto.setSourceCount(actualSourceCount);
        dto.setAggregationExplain(AggregationExplainability.buildAggregationExplain(row));
        RankingTrustDTO trust = RankingTrustLayer.buildTrustScore(row);
        dto.setTrustScore(trust.getTrustScore());
        dto.setTrustLevel(trust.getTrustLevel());
        dto.setTrustExplain(trust.getTrustExplain());
        LOGGER.info(
                "ranking dto evidence debug: canonicalUniversityId={}, sourceRanks={}, sourceCount(row)={}, sourceCount(actual)={}, aggregationExplain.sources={}, aggregationExplain.availableSourceCount={}, aggregationExplain.aggregatedRankValue={}, trustScore={}, trustLevel={}, trustExplain.sources={}, trustExplain.notes={}",
                row.getCanonicalUniversityId(),
                row.getSourceRanks(),
                row.getSourceCount(),
                actualSourceCount,
                dto.getAggregationExplain() == null ? null : dto.getAggregationExplain().getSources(),
                dto.getAggregationExplain() == null ? null : dto.getAggregationExplain().getAvailableSourceCount(),
                dto.getAggregationExplain() == null ? null : dto.getAggregationExplain().getAggregatedRankValue(),
                trust.getTrustScore(),
                trust.getTrustLevel(),
                trust.getTrustExplain() == null ? null : trust.getTrustExplain().getSources(),
                trust.getTrustExplain() == null ? null : trust.getTrustExplain().getNotes()
        );
        return dto;
    }

    private RankingCountryOptionDTO toCountryOptionDto(Map<String, Object> row) {
        return new RankingCountryOptionDTO(
                (String) row.get("country_code"),
                (String) row.get("country_name"),
                ((Number) row.get("country_count")).longValue()
        );
    }
}
