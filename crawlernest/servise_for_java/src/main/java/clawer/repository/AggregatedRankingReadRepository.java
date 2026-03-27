package clawer.repository;

import clawer.dto.RankingDTO;

import java.util.List;

/**
 * Official read repository for product rankings.
 * Reads ONLY from the aggregated rankings read model.
 */
public interface AggregatedRankingReadRepository {
    List<RankingDTO> findRankings(
            Integer year,
            String search,
            String scope,
            String region,
            int page,
            int pageSize
    );

    long countRankings(Integer year, String search, String scope, String region);
}
