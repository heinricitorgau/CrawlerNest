package clawer.domain.ranking;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class RankingContextDomainTest {

    @Test
    void globalContextUsesGlobalLabelAndDisplayRank() {
        RankingContext context = RankingContext.fromQuery("global", null);
        RankedPosition rankedPosition = RankedPosition.of(context, 15, 999);

        assertEquals("Global Rankings", context.rankingLabel());
        assertEquals("Browsing universities ranked globally.", context.browseSummary());
        assertEquals(15, rankedPosition.displayRank());
        assertEquals(15, rankedPosition.compatibilityAggregatedRank());
        assertEquals("Ranked #15 globally", rankedPosition.primaryRankSummary());
    }

    @Test
    void regionContextUsesRegionLabelAndScopeRank() {
        RankingContext context = RankingContext.fromQuery("region", "europe");
        RankedPosition rankedPosition = RankedPosition.of(context, 15, 7);

        assertEquals("Europe Rankings", context.rankingLabel());
        assertEquals("Europe rank", context.rankReferenceLabel());
        assertEquals(7, rankedPosition.displayRank());
        assertEquals(7, rankedPosition.compatibilityAggregatedRank());
        assertEquals("Ranked #7 in Europe, with a global position at #15", rankedPosition.primaryRankSummary());
    }

    @Test
    void regionContextRejectsMissingOrUnsupportedRegion() {
        assertThrows(IllegalArgumentException.class, () -> RankingContext.fromQuery("region", null));
        assertThrows(IllegalArgumentException.class, () -> RankingContext.fromQuery("region", "Atlantis"));
    }
}
