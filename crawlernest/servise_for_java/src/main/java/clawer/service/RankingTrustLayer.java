package clawer.service;

import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.dto.RankingTrustDTO;
import clawer.dto.TrustExplainDTO;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class RankingTrustLayer {
    private static final double COVERAGE_WEIGHT = 0.50;
    private static final double COMPLETENESS_WEIGHT = 0.20;
    private static final double CONSISTENCY_WEIGHT = 0.30;
    private static final List<String> SOURCE_ORDER = List.of("QS", "THE", "ARWU");

    private RankingTrustLayer() {}

    public static RankingTrustDTO buildTrustScore(ScopedRankedUniversity row) {
        return buildTrustScore(row == null ? null : row.getSourceRanks());
    }

    public static RankingTrustDTO buildTrustScore(Map<String, Integer> sourceRanks) {
        List<Integer> availableRanks = new ArrayList<>();
        Map<String, Integer> explainSources = new LinkedHashMap<>();

        for (String source : SOURCE_ORDER) {
            Integer rank = sourceRanks == null ? null : sourceRanks.get(source);
            explainSources.put(source, rank);
            if (rank != null) {
                availableRanks.add(rank);
            }
        }

        int sourceCount = availableRanks.size();
        double coverageScore = coverageScore(sourceCount);
        double completenessScore = completenessScore(sourceCount);
        double stdDeviation = round(standardDeviation(availableRanks));
        double consistencyScore = consistencyScore(stdDeviation);
        double trustScore = round(clamp(
                (coverageScore * COVERAGE_WEIGHT)
                        + (completenessScore * COMPLETENESS_WEIGHT)
                        + (consistencyScore * CONSISTENCY_WEIGHT)
        ));

        TrustExplainDTO explain = new TrustExplainDTO();
        explain.setSources(explainSources);
        explain.setCoverageScore(coverageScore);
        explain.setConsistencyScore(consistencyScore);
        explain.setStdDeviation(stdDeviation);
        explain.setNotes(buildNotes(sourceCount, consistencyScore, stdDeviation));

        RankingTrustDTO trust = new RankingTrustDTO();
        trust.setTrustScore(trustScore);
        trust.setTrustLevel(resolveTrustLevel(trustScore));
        trust.setTrustExplain(explain);
        return trust;
    }

    private static String resolveTrustLevel(double trustScore) {
        if (trustScore >= 85.0) {
            return "high";
        }
        if (trustScore >= 60.0) {
            return "medium";
        }
        return "low";
    }

    private static double coverageScore(int sourceCount) {
        return switch (sourceCount) {
            case 3 -> 100.0;
            case 2 -> 65.0;
            case 1 -> 35.0;
            default -> 0.0;
        };
    }

    private static double completenessScore(int sourceCount) {
        return switch (sourceCount) {
            case 3 -> 100.0;
            case 2 -> 65.0;
            case 1 -> 35.0;
            default -> 0.0;
        };
    }

    private static double consistencyScore(double stdDeviation) {
        if (stdDeviation <= 5.0) {
            return 100.0;
        }
        if (stdDeviation <= 15.0) {
            return 70.0;
        }
        if (stdDeviation <= 30.0) {
            return 40.0;
        }
        return 20.0;
    }

    private static double standardDeviation(List<Integer> values) {
        if (values == null || values.isEmpty()) {
            return 100.0;
        }
        if (values.size() == 1) {
            return 0.0;
        }
        double mean = values.stream().mapToDouble(Integer::doubleValue).average().orElse(0.0);
        double variance = values.stream()
                .mapToDouble(value -> Math.pow(value - mean, 2))
                .average()
                .orElse(0.0);
        return Math.sqrt(variance);
    }

    private static List<String> buildNotes(int sourceCount, double consistencyScore, double stdDeviation) {
        List<String> notes = new ArrayList<>();
        if (sourceCount <= 1) {
            notes.add("Only one ranking source available");
            notes.add("Limited data — interpret with caution.");
            return notes;
        }
        if (sourceCount == 2) {
            notes.add("Only two ranking sources available");
        }
        if (consistencyScore >= 100.0) {
            notes.add("Strong agreement across sources");
        } else if (stdDeviation > 15.0) {
            notes.add("High variance across sources");
        } else {
            notes.add("Moderate agreement across sources");
        }
        if (consistencyScore <= 40.0) {
            notes.add("Ranking may be unreliable");
        }
        return notes;
    }

    private static double clamp(double value) {
        return Math.max(0.0, Math.min(100.0, value));
    }

    private static double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }
}
