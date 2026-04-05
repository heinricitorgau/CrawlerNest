package clawer.repository;

import clawer.dto.RankingDTO;
import clawer.dto.RankingCountryOptionDTO;

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
            String countryCode,
            String countryName,
            int page,
            int pageSize
    );

    long countRankings(Integer year, String search, String scope, String region, String countryCode, String countryName);

    List<RankingCountryOptionDTO> findCountryOptions(Integer year, String search, String scope, String region);
}
