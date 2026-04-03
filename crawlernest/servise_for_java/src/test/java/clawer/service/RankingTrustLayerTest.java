package clawer.service;

import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.dto.RankingTrustDTO;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RankingTrustLayerTest {

    @Test
    void test_trust_score_calculation() {
        ScopedRankedUniversity consistent = new ScopedRankedUniversity();
        consistent.setSourceRanks(sourceRanks(4, 5, 6));
        RankingTrustDTO highTrust = RankingTrustLayer.buildTrustScore(consistent);
        assertEquals("high", highTrust.getTrustLevel());
        assertTrue(highTrust.getTrustScore() >= 85.0);

        ScopedRankedUniversity moderate = new ScopedRankedUniversity();
        moderate.setSourceRanks(sourceRanks(10, 20, null));
        RankingTrustDTO mediumTrust = RankingTrustLayer.buildTrustScore(moderate);
        assertEquals("medium", mediumTrust.getTrustLevel());
        assertTrue(mediumTrust.getTrustScore() >= 60.0 && mediumTrust.getTrustScore() < 85.0);

        ScopedRankedUniversity singleSource = new ScopedRankedUniversity();
        singleSource.setSourceRanks(sourceRanks(4, null, null));
        RankingTrustDTO lowTrust = RankingTrustLayer.buildTrustScore(singleSource);
        assertEquals("low", lowTrust.getTrustLevel());
        assertTrue(lowTrust.getTrustScore() < 60.0);

        ScopedRankedUniversity inconsistent = new ScopedRankedUniversity();
        inconsistent.setSourceRanks(sourceRanks(4, 80, null));
        RankingTrustDTO inconsistentTrust = RankingTrustLayer.buildTrustScore(inconsistent);
        assertEquals("low", inconsistentTrust.getTrustLevel());
        assertTrue(inconsistentTrust.getTrustScore() < 60.0);
    }

    private Map<String, Integer> sourceRanks(Integer qs, Integer the, Integer arwu) {
        Map<String, Integer> ranks = new LinkedHashMap<>();
        ranks.put("QS", qs);
        ranks.put("THE", the);
        ranks.put("ARWU", arwu);
        return ranks;
    }
}
