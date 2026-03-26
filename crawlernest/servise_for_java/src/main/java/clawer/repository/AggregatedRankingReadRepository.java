package clawer.repository;

import clawer.dto.RankingDTO;

import java.util.List;

/**
 * Official read repository for product rankings.
 * Reads ONLY from the aggregated rankings read model.
 */
public interface AggregatedRankingReadRepository {
    List<RankingDTO> findRankings(Integer year, int offset, int limit);

    long countRankings(Integer year);
}
