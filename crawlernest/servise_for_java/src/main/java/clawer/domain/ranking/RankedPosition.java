package clawer.domain.ranking;

public record RankedPosition(RankingContext context, Integer globalRank, Integer scopeRank) {

    public static RankedPosition of(RankingContext context, Integer globalRank, Integer scopeRank) {
        Integer resolvedScopeRank = context.isRegion() ? scopeRank : globalRank;
        return new RankedPosition(context, globalRank, resolvedScopeRank);
    }

    public Integer displayRank() {
        return context.isRegion() ? scopeRank : globalRank;
    }

    public Integer compatibilityAggregatedRank() {
        return displayRank();
    }

    public boolean hasSecondaryGlobalReference() {
        return context.isRegion()
                && globalRank != null
                && scopeRank != null
                && !globalRank.equals(scopeRank);
    }

    public String primaryRankSummary() {
        Integer displayRank = displayRank();
        if (displayRank == null) {
            return context.isRegion() ? "regional rank unavailable" : "global rank unavailable";
        }
        if (!context.isRegion()) {
            return "Ranked #" + displayRank + " globally";
        }
        if (globalRank == null) {
            return "Ranked #" + displayRank + " in " + context.region();
        }
        return "Ranked #" + displayRank + " in " + context.region() + ", with a global position at #" + globalRank;
    }
}
