package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.RankingScope;
import clawer.dto.RankingCountryOptionDTO;
import clawer.dto.RankingDTO;
import clawer.repository.AggregatedRankingReadRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Locale;

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

    public List<RankingDTO> getRankings(int page, int pageSize, Integer year, String search, String scope, String region, String countryCode) {
        String normalizedSearch = normalizeSearch(search);
        String normalizedCountryCode = normalizeCountryCode(countryCode);
        String normalizedCountryName = normalizeCountryName(countryCode);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        LOGGER.info(
                "Aggregated rankings request received: page={}, pageSize={}, year={}, search={}, scope={}, region={}, country={}, rankingLabel={}",
                page + 1,
                pageSize,
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                normalizedCountryCode,
                rankingContext.rankingLabel()
        );
        long totalAfterFiltering = aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                normalizedCountryCode,
                normalizedCountryName
        );
        LOGGER.info(
                "Aggregated rankings counts: totalAfterFiltering={}, page={}, pageSize={}, source=AGGREGATED, year={}, search={}, scope={}, region={}, country={}",
                totalAfterFiltering,
                page + 1,
                pageSize,
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                normalizedCountryCode
        );
        return aggregatedRankingReadRepository.findRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                normalizedCountryCode,
                normalizedCountryName,
                page,
                pageSize
        );
    }

    public long countRankings(Integer year, String search, String scope, String region, String countryCode) {
        String normalizedSearch = normalizeSearch(search);
        String normalizedCountryCode = normalizeCountryCode(countryCode);
        String normalizedCountryName = normalizeCountryName(countryCode);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        return aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                normalizedCountryCode,
                normalizedCountryName
        );
    }

    public List<RankingCountryOptionDTO> getCountryOptions(Integer year, String search, String scope, String region) {
        String normalizedSearch = normalizeSearch(search);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        return aggregatedRankingReadRepository.findCountryOptions(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region()
        );
    }

    public String resolveCountryCode(Integer year, String search, String scope, String region, String countryFilter) {
        if (countryFilter == null || countryFilter.isBlank()) {
            return null;
        }

        String normalizedFilter = countryFilter.trim();
        String uppercaseFilter = normalizedFilter.toUpperCase(Locale.ROOT);

        return getCountryOptions(year, search, scope, region).stream()
                .filter(option ->
                        uppercaseFilter.equals(option.getCode())
                                || normalizedFilter.equalsIgnoreCase(option.getName()))
                .map(option -> option.getCode() == null || option.getCode().isBlank()
                        ? option.getName()
                        : option.getCode())
                .findFirst()
                .orElse(null);
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

    private String normalizeCountryCode(String countryCode) {
        if (countryCode == null) {
            return null;
        }

        String normalized = countryCode.trim().toUpperCase();
        return normalized.isEmpty() ? null : normalized;
    }

    private String normalizeCountryName(String countryName) {
        if (countryName == null) {
            return null;
        }

        String normalized = countryName.trim();
        return normalized.isEmpty() ? null : normalized;
    }
}
