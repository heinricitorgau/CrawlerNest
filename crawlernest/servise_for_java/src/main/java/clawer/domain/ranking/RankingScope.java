package clawer.domain.ranking;

import java.util.Locale;

public enum RankingScope {
    GLOBAL("global"),
    REGION("region");

    private final String apiValue;

    RankingScope(String apiValue) {
        this.apiValue = apiValue;
    }

    public String apiValue() {
        return apiValue;
    }

    public static RankingScope fromQueryValue(String scope) {
        if (scope == null || scope.isBlank()) {
            return GLOBAL;
        }

        String normalized = scope.trim().toLowerCase(Locale.ROOT);
        return switch (normalized) {
            case "global" -> GLOBAL;
            case "region" -> REGION;
            default -> throw new IllegalArgumentException("scope must be either global or region.");
        };
    }
}
