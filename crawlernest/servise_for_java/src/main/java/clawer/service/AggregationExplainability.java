package clawer.service;

import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.dto.AggregationExplainDTO;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class AggregationExplainability {
    private static final List<String> SOURCE_ORDER = List.of("QS", "THE", "ARWU");
    private static final Map<String, Double> SOURCE_WEIGHTS = Map.of(
            "QS", 0.40,
            "THE", 0.35,
            "ARWU", 0.25
    );

    private AggregationExplainability() {}

    public static AggregationExplainDTO buildAggregationExplain(ScopedRankedUniversity row) {
        if (row == null || row.getSourceRanks() == null || row.getSourceRanks().isEmpty()) {
            return null;
        }

        Map<String, Integer> sources = new LinkedHashMap<>();
        Map<String, Double> weights = new LinkedHashMap<>();
        double weightedRankSum = 0.0;
        double availableWeightSum = 0.0;
        int availableSourceCount = 0;

        for (String source : SOURCE_ORDER) {
            Integer rank = row.getSourceRanks().get(source);
            Double weight = SOURCE_WEIGHTS.getOrDefault(source, 0.0);
            sources.put(source, rank);
            weights.put(source, weight);
            if (rank != null) {
                weightedRankSum += rank * weight;
                availableWeightSum += weight;
                availableSourceCount += 1;
            }
        }

        if (availableSourceCount == 0 || availableWeightSum <= 0.0) {
            return null;
        }

        AggregationExplainDTO explain = new AggregationExplainDTO();
        explain.setSources(sources);
        explain.setWeights(weights);
        explain.setAggregatedRankValue(round(weightedRankSum / availableWeightSum));
        explain.setAvailableSourceCount(availableSourceCount);
        return explain;
    }

    private static double round(double value) {
        return Math.round(value * 1_000_000d) / 1_000_000d;
    }
}
