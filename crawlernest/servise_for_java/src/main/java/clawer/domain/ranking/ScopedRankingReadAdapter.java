package clawer.domain.ranking;

import java.util.List;
import java.util.Map;

public interface ScopedRankingReadAdapter {
    List<ScopedRankedUniversity> findRankings(
            RankingContext context,
            Integer year,
            String search,
            String countryCode,
            String countryName,
            int page,
            int pageSize
    );

    long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName);

    List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search);

    List<ScopedRankedUniversity> findRecommendationCandidates(
            RankingContext context,
            Integer year,
            String country
    );
}
