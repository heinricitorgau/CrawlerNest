package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.RankingScope;
import clawer.dto.RankingDTO;
import clawer.repository.AggregatedRankingReadRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service for handling university rankings business logic.
 */
@Service
public class RankingService {
    private static final Logger LOGGER = LoggerFactory.getLogger(RankingService.class);

    private final AggregatedRankingReadRepository aggregatedRankingReadRepository;

    public RankingService(AggregatedRankingReadRepository aggregatedRankingReadRepository) {
        this.aggregatedRankingReadRepository = aggregatedRankingReadRepository;
    }

    public List<RankingDTO> getRankings(int page, int pageSize, Integer year, String search, String scope, String region) {
        String normalizedSearch = normalizeSearch(search);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        LOGGER.info(
                "Aggregated rankings request received: page={}, pageSize={}, year={}, search={}, scope={}, region={}, rankingLabel={}",
                page + 1,
                pageSize,
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                rankingContext.rankingLabel()
        );
        long totalAfterFiltering = aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region()
        );
        LOGGER.info(
                "Aggregated rankings counts: totalAfterFiltering={}, page={}, pageSize={}, source=AGGREGATED, year={}, search={}, scope={}, region={}",
                totalAfterFiltering,
                page + 1,
                pageSize,
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region()
        );
        return aggregatedRankingReadRepository.findRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                page,
                pageSize
        );
    }

    public long countRankings(Integer year, String search, String scope, String region) {
        String normalizedSearch = normalizeSearch(search);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        return aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region()
        );
    }

    public boolean isSupportedSource(String source) {
        return source == null || source.isBlank() || "AGGREGATED".equalsIgnoreCase(source);
    }

    public boolean isSupportedScope(String scope) {
        try {
            RankingScope.fromQueryValue(scope);
            return true;
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }

    public boolean requiresRegion(String scope) {
        try {
            return RankingScope.fromQueryValue(scope) == RankingScope.REGION;
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }

    public boolean isSupportedRegion(String region) {
        return RankingContext.isSupportedRegion(region);
    }

    public String normalizeScope(String scope) {
        return RankingScope.fromQueryValue(scope).apiValue();
    }

    public String normalizeRegion(String region) {
        return RankingContext.normalizeRegion(region);
    }

    private String normalizeSearch(String search) {
        if (search == null) {
            return null;
        }

        String normalized = search.trim();
        return normalized.isEmpty() ? null : normalized;
    }
}
