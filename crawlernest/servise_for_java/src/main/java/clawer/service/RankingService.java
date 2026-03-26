package clawer.service;

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

    public List<RankingDTO> getRankings(int page, int pageSize, Integer year) {
        LOGGER.info("Aggregated rankings request received: page={}, pageSize={}, year={}", page + 1, pageSize, year);
        long totalAfterFiltering = aggregatedRankingReadRepository.countRankings(year);
        LOGGER.info(
                "Aggregated rankings counts: totalAfterFiltering={}, page={}, pageSize={}, source=AGGREGATED, year={}",
                totalAfterFiltering,
                page + 1,
                pageSize,
                year
        );
        int offset = page * pageSize;
        return aggregatedRankingReadRepository.findRankings(year, offset, pageSize);
    }

    public boolean isSupportedSource(String source) {
        return source == null || source.isBlank() || "AGGREGATED".equalsIgnoreCase(source);
    }
}
