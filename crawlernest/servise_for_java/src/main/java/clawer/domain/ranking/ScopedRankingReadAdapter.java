package clawer.domain.ranking;

import java.util.List;

public interface ScopedRankingReadAdapter {
    List<ScopedRankedUniversity> findRankings(
            RankingContext context,
            Integer year,
            String search,
            int page,
            int pageSize
    );

    long countRankings(RankingContext context, Integer year, String search);

    List<ScopedRankedUniversity> findRecommendationCandidates(
            RankingContext context,
            Integer year,
            String country
    );
}
