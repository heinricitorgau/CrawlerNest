package clawer.domain.ranking;

import java.util.Arrays;
import java.util.Locale;
import java.util.Set;

public record RankingContext(RankingScope scope, String region) {
    private static final Set<String> SUPPORTED_REGIONS = Set.of(
            "Europe",
            "Asia",
            "North America",
            "Latin America",
            "Oceania",
            "Africa"
    );

    public static RankingContext fromQuery(String scope, String region) {
        RankingScope rankingScope = RankingScope.fromQueryValue(scope);
        String normalizedRegion = normalizeRegion(region);
        if (rankingScope == RankingScope.REGION) {
            if (normalizedRegion == null) {
                throw new IllegalArgumentException("region is required when scope=region.");
            }
            if (!SUPPORTED_REGIONS.contains(normalizedRegion)) {
                throw new IllegalArgumentException("Unsupported region. Supported values: Europe, Asia, North America, Latin America, Oceania, Africa.");
            }
            return new RankingContext(rankingScope, normalizedRegion);
        }
        return new RankingContext(RankingScope.GLOBAL, null);
    }

    public static String normalizeRegion(String region) {
        if (region == null || region.isBlank()) {
            return null;
        }

        String trimmed = region.trim().toLowerCase(Locale.ROOT);
        return Arrays.stream(trimmed.split("\\s+"))
                .map(word -> Character.toUpperCase(word.charAt(0)) + word.substring(1))
                .reduce((left, right) -> left + " " + right)
                .orElse(trimmed);
    }

    public static boolean isSupportedRegion(String region) {
        String normalized = normalizeRegion(region);
        return normalized != null && SUPPORTED_REGIONS.contains(normalized);
    }

    public boolean isRegion() {
        return scope == RankingScope.REGION;
    }

    public String apiScope() {
        return scope.apiValue();
    }

    public String regionOrEmpty() {
        return region == null ? "" : region;
    }

    public String universeType() {
        return isRegion() ? "region" : "global";
    }

    public String universeKey() {
        if (!isRegion()) {
            return "global";
        }
        return region.toLowerCase(Locale.ROOT).replace(' ', '-');
    }

    public String rankingLabel() {
        return isRegion() ? region + " Rankings" : "Global Rankings";
    }

    public String rankReferenceLabel() {
        return isRegion() ? region + " rank" : "global rank";
    }

    public String browseSummary() {
        return isRegion()
                ? "Browsing universities ranked within " + region + "."
                : "Browsing universities ranked globally.";
    }
}
