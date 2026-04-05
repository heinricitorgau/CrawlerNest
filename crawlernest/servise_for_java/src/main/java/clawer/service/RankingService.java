package clawer.service;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.RankingScope;
import clawer.dto.RankingCountryOptionDTO;
import clawer.dto.RankingDTO;
import clawer.repository.AggregatedRankingReadRepository;
import clawer.repository.CountryRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.LinkedHashMap;
import java.util.Optional;
import java.util.Comparator;
import java.util.Map;

/**
 * Service for handling university rankings business logic.
 */
@Service
public class RankingService {
    private static final Logger LOGGER = LoggerFactory.getLogger(RankingService.class);

    private final AggregatedRankingReadRepository aggregatedRankingReadRepository;
    private final CountryRepository countryRepository;

    public RankingService(
            AggregatedRankingReadRepository aggregatedRankingReadRepository,
            CountryRepository countryRepository
    ) {
        this.aggregatedRankingReadRepository = aggregatedRankingReadRepository;
        this.countryRepository = countryRepository;
    }

    public List<RankingDTO> getRankings(int page, int pageSize, Integer year, String search, String scope, String region, String countryCode) {
        String normalizedSearch = normalizeSearch(search);
        String countryToken = trimCountryToken(countryCode);
        String countryNameForSql = resolveCountryNameForSqlFilter(countryToken);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        LOGGER.info(
                "Aggregated rankings request received: page={}, pageSize={}, year={}, search={}, scope={}, region={}, country={}, rankingLabel={}",
                page + 1,
                pageSize,
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                countryToken,
                rankingContext.rankingLabel()
        );
        long totalAfterFiltering = aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                null,
                countryNameForSql
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
                countryToken
        );
        return aggregatedRankingReadRepository.findRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                null,
                countryNameForSql,
                page,
                pageSize
        );
    }

    public long countRankings(Integer year, String search, String scope, String region, String countryCode) {
        String normalizedSearch = normalizeSearch(search);
        String countryToken = trimCountryToken(countryCode);
        String countryNameForSql = resolveCountryNameForSqlFilter(countryToken);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        return aggregatedRankingReadRepository.countRankings(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region(),
                null,
                countryNameForSql
        );
    }

    public List<RankingCountryOptionDTO> getCountryOptions(Integer year, String search, String scope, String region) {
        String normalizedSearch = normalizeSearch(search);
        RankingContext rankingContext = RankingContext.fromQuery(scope, region);
        List<RankingCountryOptionDTO> rawOptions = aggregatedRankingReadRepository.findCountryOptions(
                year,
                normalizedSearch,
                rankingContext.apiScope(),
                rankingContext.region()
        );
        Map<String, Long> canonicalCounts = new LinkedHashMap<>();
        for (RankingCountryOptionDTO option : rawOptions) {
            String canonicalName = CountryNormalization.normalizeCountry(option.getName());
            if (canonicalName == null) {
                continue;
            }
            canonicalCounts.merge(canonicalName, option.getCount(), Long::sum);
        }
        return canonicalCounts.entrySet().stream()
                .map(entry -> new RankingCountryOptionDTO(null, entry.getKey(), entry.getValue()))
                .sorted(Comparator
                        .comparingLong(RankingCountryOptionDTO::getCount).reversed()
                        .thenComparing(RankingCountryOptionDTO::getName))
                .toList();
    }

    public String resolveCountryCode(Integer year, String search, String scope, String region, String countryFilter) {
        String countryToken = CountryNormalization.normalizeCountry(countryFilter);
        if (countryToken == null) {
            return null;
        }
        return findCountryByToken(countryToken)
                .map(country -> country.getCountryCode() == null || country.getCountryCode().isBlank()
                        ? country.getCountryName()
                        : country.getCountryCode())
                .orElse(null);
    }

    public boolean isSupportedCountry(Integer year, String search, String countryFilter) {
        String countryToken = CountryNormalization.normalizeCountry(countryFilter);
        if (countryToken == null) {
            return false;
        }
        return countryRepository.existsByCountryNameIgnoreCase(countryToken)
                || countryRepository.existsByCountryCodeIgnoreCase(countryToken);
    }

    public boolean isCountryAllowedForScopeRegion(Integer year, String search, String scope, String region, String countryFilter) {
        String countryToken = CountryNormalization.normalizeCountry(countryFilter);
        String normalizedRegion = normalizeRegion(region);
        if (countryToken == null || normalizedRegion == null) {
            return false;
        }
        return countryRepository.existsByCountryNameIgnoreCaseAndRegionNameIgnoreCase(countryToken, normalizedRegion)
                || countryRepository.existsByCountryCodeIgnoreCaseAndRegionNameIgnoreCase(countryToken, normalizedRegion);
    }

    /**
     * Canonical country name from {@code warehouse.countries.country_name} for the matched option, used in SQL
     * {@code LOWER(c.country_name) = LOWER(?)}. Falls back to the resolved token if the option has no name.
     */
    private String resolveCountryNameForSqlFilter(String countryToken) {
        if (countryToken == null) {
            return null;
        }
        String normalizedCountry = CountryNormalization.normalizeCountry(countryToken);
        return findCountryByToken(normalizedCountry)
                .map(country -> country.getCountryName() == null || country.getCountryName().isBlank()
                        ? normalizedCountry
                        : country.getCountryName())
                .orElse(normalizedCountry);
    }

    private Optional<clawer.model.Country> findCountryByToken(String countryToken) {
        if (countryToken == null || countryToken.isBlank()) {
            return Optional.empty();
        }
        return countryRepository.findByCountryNameIgnoreCase(countryToken)
                .or(() -> countryRepository.findByCountryCodeIgnoreCase(countryToken));
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

    private static String trimCountryToken(String countryCode) {
        if (countryCode == null) {
            return null;
        }
        String trimmed = countryCode.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    String normalizeCountry(String input) {
        return CountryNormalization.normalizeCountry(input);
    }
}
