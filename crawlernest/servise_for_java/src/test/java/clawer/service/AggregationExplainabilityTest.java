package clawer.service;

import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.dto.AggregationExplainDTO;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

class AggregationExplainabilityTest {

    @Test
    void test_aggregation_explain_structure() {
        ScopedRankedUniversity row = new ScopedRankedUniversity();
        Map<String, Integer> sourceRanks = new LinkedHashMap<>();
        sourceRanks.put("QS", 4);
        sourceRanks.put("THE", 5);
        row.setSourceRanks(sourceRanks);
        row.setAggregationMethodVersion("rank_agg_v2");
        row.setCoverageRatio(0.67);
        row.setCompositeScore(93.4);

        AggregationExplainDTO explain = AggregationExplainability.buildAggregationExplain(row);

        assertNotNull(explain);
        assertEquals(4, explain.getSources().get("QS"));
        assertEquals(5, explain.getSources().get("THE"));
        assertNull(explain.getSources().get("ARWU"));
        assertEquals(0.222, explain.getWeights().get("QS"));
        assertEquals(0.654, explain.getWeights().get("THE"));
        assertEquals(0.124, explain.getWeights().get("ARWU"));
        assertEquals(2, explain.getAvailableSourceCount());
        // (4 * 0.222 + 5 * 0.654) / (0.222 + 0.654), renormalised over the two
        // sources actually present.
        assertEquals(4.746575, explain.getAggregatedRankValue());
        assertEquals("Two ranking sources available.", explain.getNote());
        assertEquals(row.getAggregationMethodVersion(), explain.getAggregationMethodVersion());
        assertEquals(row.getCoverageRatio(), explain.getCoverageRatio());
        assertEquals(row.getCompositeScore(), explain.getCompositeScore());
    }
}
