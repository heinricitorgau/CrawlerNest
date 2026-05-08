package clawer.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class SourceIntelligenceService {
    private static final List<String> MAJOR_SOURCES = List.of("QS", "THE", "ARWU");
    private static final int AGREEMENT_THRESHOLD = 25;
    private static final int SEVERE_DISAGREEMENT_THRESHOLD = 100;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public SourceIntelligenceService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> getSourceComparison(Long canonicalUniversityId) {
        Map<String, Object> aggregate = latestAggregate(canonicalUniversityId);
        if (aggregate == null) {
            return emptyUniversityComparison(canonicalUniversityId);
        }

        Integer rankingYear = toInteger(aggregate.get("ranking_year"));
        Map<String, Object> sourceRanks = jsonMap(aggregate.get("source_ranks_json"));
        Map<String, Object> normalizedScores = jsonMap(aggregate.get("source_normalized_scores_json"));
        Map<String, Object> weights = jsonMap(aggregate.get("source_weights_used_json"));
        Map<String, Double> rawScores = sourceScores(canonicalUniversityId, rankingYear);

        List<Map<String, Object>> sources = buildSources(sourceRanks, normalizedScores, weights, rawScores);
        List<String> missingSources = missingSources(sourceRanks);
        Map<String, Object> disagreement = disagreementMetrics(sourceRanks);
        String confidence = classifyConfidence(sourceRanks);

        Map<String, Object> data = baseAggregateFields(aggregate);
        data.put("sources", sources);
        data.put("missing_sources", missingSources);
        data.put("rank_spread", disagreement.get("rank_spread"));
        data.put("confidence", confidence);
        data.put("confidence_reasoning", confidenceReasoning(sourceRanks, confidence));
        data.put("source_disagreement_metrics", disagreement);
        data.put("aggregation_contribution", buildContributions(normalizedScores, weights));
        return data;
    }

    public Map<String, Object> explainRanking(Long canonicalUniversityId) {
        Map<String, Object> aggregate = latestAggregate(canonicalUniversityId);
        if (aggregate == null) {
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("canonical_university_id", canonicalUniversityId);
            data.put("why_this_rank_exists", "No latest aggregated ranking row exists for this university.");
            data.put("source_contributions", List.of());
            data.put("weighted_aggregation_inputs", List.of());
            data.put("normalized_scores", Map.of());
            data.put("missing_source_penalties", List.of());
            data.put("confidence", "low");
            data.put("confidence_reasoning", "No source coverage is available.");
            return data;
        }

        Map<String, Object> sourceRanks = jsonMap(aggregate.get("source_ranks_json"));
        Map<String, Object> normalizedScores = jsonMap(aggregate.get("source_normalized_scores_json"));
        Map<String, Object> weights = jsonMap(aggregate.get("source_weights_used_json"));
        String confidence = classifyConfidence(sourceRanks);

        Map<String, Object> data = baseAggregateFields(aggregate);
        data.put("why_this_rank_exists", whyRankExists(aggregate, sourceRanks));
        data.put("source_contributions", buildContributions(normalizedScores, weights));
        data.put("weighted_aggregation_inputs", buildWeightedInputs(sourceRanks, normalizedScores, weights));
        data.put("normalized_scores", orderedNumericJson(normalizedScores));
        data.put("source_weights_used", orderedNumericJson(weights));
        data.put("missing_source_penalties", buildMissingSourcePenalties(weights));
        data.put("source_disagreement_metrics", disagreementMetrics(sourceRanks));
        data.put("confidence", confidence);
        data.put("confidence_reasoning", confidenceReasoning(sourceRanks, confidence));
        data.put("formula_note", "Explain layer only. Aggregation formula remains the stored weighted normalized score output.");
        return data;
    }

    public Map<String, Object> getSourceAgreementDiagnostics() {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT ar.canonical_university_id,
                       cu.display_name AS university_name,
                       cu.canonical_slug AS slug,
                       ar.ranking_year,
                       ar.display_rank,
                       ar.source_ranks_json
                FROM analytics.v_aggregated_rankings_latest ar
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ar.canonical_university_id
                WHERE ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                  AND ar.display_rank IS NOT NULL
                  AND ar.ranking_year = (
                      SELECT MAX(latest.ranking_year)
                      FROM analytics.v_aggregated_rankings_latest latest
                      WHERE latest.universe_type = 'global'
                        AND latest.universe_key = 'global'
                        AND latest.display_rank IS NOT NULL
                  )
                """);

        long total = rows.size();
        long qsCount = 0;
        long theCount = 0;
        long arwuCount = 0;
        long qsTheOverlap = 0;
        long anyMultiSource = 0;
        double qsTheDiffSum = 0.0;
        Map<String, Integer> confidenceBuckets = new LinkedHashMap<>();
        confidenceBuckets.put("high", 0);
        confidenceBuckets.put("medium", 0);
        confidenceBuckets.put("low", 0);
        Map<String, Long> missingCounts = new LinkedHashMap<>();
        for (String source : MAJOR_SOURCES) {
            missingCounts.put(source, 0L);
        }
        List<Map<String, Object>> outliers = new ArrayList<>();

        for (Map<String, Object> row : rows) {
            Map<String, Object> ranks = jsonMap(row.get("source_ranks_json"));
            boolean hasQs = numericValue(ranks.get("QS")) != null;
            boolean hasThe = numericValue(ranks.get("THE")) != null;
            boolean hasArwu = numericValue(ranks.get("ARWU")) != null;
            qsCount += hasQs ? 1 : 0;
            theCount += hasThe ? 1 : 0;
            arwuCount += hasArwu ? 1 : 0;
            anyMultiSource += countAvailableSources(ranks) >= 2 ? 1 : 0;
            for (String source : MAJOR_SOURCES) {
                if (numericValue(ranks.get(source)) == null) {
                    missingCounts.put(source, missingCounts.get(source) + 1L);
                }
            }

            Double qsRank = numericValue(ranks.get("QS"));
            Double theRank = numericValue(ranks.get("THE"));
            if (qsRank != null && theRank != null) {
                qsTheOverlap += 1;
                qsTheDiffSum += Math.abs(qsRank - theRank);
            }

            String confidence = classifyConfidence(ranks);
            confidenceBuckets.put(confidence, confidenceBuckets.get(confidence) + 1);
            Map<String, Object> disagreement = disagreementMetrics(ranks);
            Number spread = (Number) disagreement.get("rank_spread");
            if (spread != null && spread.doubleValue() > 0) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("canonical_university_id", row.get("canonical_university_id"));
                item.put("university_name", row.get("university_name"));
                item.put("slug", row.get("slug"));
                item.put("ranking_year", row.get("ranking_year"));
                item.put("aggregated_rank", row.get("display_rank"));
                item.put("source_ranks", orderedRankJson(ranks));
                item.put("rank_spread", spread);
                item.put("confidence", confidence);
                outliers.add(item);
            }
        }

        outliers.sort(Comparator.comparingDouble((Map<String, Object> row) ->
                ((Number) row.get("rank_spread")).doubleValue()).reversed());

        Map<String, Object> overlap = new LinkedHashMap<>();
        overlap.put("total_universities", total);
        overlap.put("qs_count", qsCount);
        overlap.put("the_count", theCount);
        overlap.put("arwu_count", arwuCount);
        overlap.put("qs_the_overlap_count", qsTheOverlap);
        overlap.put("qs_the_overlap_pct", pct(qsTheOverlap, total));
        overlap.put("multi_source_overlap_count", anyMultiSource);
        overlap.put("multi_source_overlap_pct", pct(anyMultiSource, total));

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("evaluation_timestamp", Instant.now().toString());
        data.put("qs_the_average_rank_difference", qsTheOverlap == 0 ? null : round(qsTheDiffSum / qsTheOverlap));
        data.put("universities_with_largest_disagreement", outliers.stream().limit(10).toList());
        data.put("missing_source_coverage", missingCoverage(missingCounts, total));
        data.put("source_overlap", overlap);
        data.put("confidence_buckets", confidenceBuckets);
        data.put("thresholds", Map.of(
                "agreement_rank_spread", AGREEMENT_THRESHOLD,
                "severe_disagreement_rank_spread", SEVERE_DISAGREEMENT_THRESHOLD
        ));
        return data;
    }

    private Map<String, Object> latestAggregate(Long canonicalUniversityId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT ar.canonical_university_id,
                       cu.display_name AS university_name,
                       cu.canonical_slug AS slug,
                       ar.ranking_year,
                       ar.display_rank,
                       ar.composite_score,
                       ar.coverage_ratio,
                       ar.source_ranks_json,
                       ar.source_normalized_scores_json,
                       ar.source_weights_used_json,
                       ar.aggregation_method_version,
                       ar.updated_at
                FROM analytics.v_aggregated_rankings_latest ar
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ar.canonical_university_id
                WHERE ar.canonical_university_id = ?
                  AND ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                ORDER BY ar.ranking_year DESC
                LIMIT 1
                """, canonicalUniversityId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private Map<String, Double> sourceScores(Long canonicalUniversityId, Integer rankingYear) {
        if (rankingYear == null) {
            return Map.of();
        }
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                WITH ranked_source_rows AS (
                    SELECT rs.source_code,
                           rr.score,
                           ROW_NUMBER() OVER (
                               PARTITION BY rs.source_code
                               ORDER BY rr.rank_position ASC NULLS LAST, rr.score DESC NULLS LAST
                           ) AS row_num
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.ranking_source rs
                      ON rs.ranking_source_id = rr.ranking_source_id
                    WHERE rr.canonical_university_id = ?
                      AND rr.ranking_year = ?
                      AND rr.ranking_type = 'world'
                      AND rr.universe_type = 'global'
                      AND rr.universe_key = 'global'
                      AND rr.rank_position IS NOT NULL
                )
                SELECT source_code, score
                FROM ranked_source_rows
                WHERE row_num = 1
                """, canonicalUniversityId, rankingYear);
        Map<String, Double> scores = new LinkedHashMap<>();
        for (Map<String, Object> row : rows) {
            Double score = numericValue(row.get("score"));
            if (score != null) {
                scores.put(String.valueOf(row.get("source_code")).toUpperCase(Locale.ROOT), score);
            }
        }
        return scores;
    }

    private Map<String, Object> baseAggregateFields(Map<String, Object> aggregate) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("canonical_university_id", aggregate.get("canonical_university_id"));
        data.put("university_name", aggregate.get("university_name"));
        data.put("slug", aggregate.get("slug"));
        data.put("ranking_year", aggregate.get("ranking_year"));
        data.put("aggregated_rank", aggregate.get("display_rank"));
        data.put("composite_score", numericValue(aggregate.get("composite_score")));
        data.put("coverage_ratio", numericValue(aggregate.get("coverage_ratio")));
        data.put("aggregation_method_version", aggregate.get("aggregation_method_version"));
        return data;
    }

    private List<Map<String, Object>> buildSources(
            Map<String, Object> ranks,
            Map<String, Object> normalizedScores,
            Map<String, Object> weights,
            Map<String, Double> rawScores
    ) {
        List<Map<String, Object>> sources = new ArrayList<>();
        for (String source : MAJOR_SOURCES) {
            Double rank = numericValue(ranks.get(source));
            if (rank == null) {
                continue;
            }
            Double normalizedScore = numericValue(normalizedScores.get(source));
            Double weight = numericValue(weights.get(source));
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", source);
            item.put("rank", toRankNumber(rank));
            item.put("score", rawScores.get(source));
            item.put("normalized_score", normalizedScore);
            item.put("weight", weight);
            item.put("weighted_input", normalizedScore != null && weight != null ? round(normalizedScore * weight) : null);
            sources.add(item);
        }
        return sources;
    }

    private List<Map<String, Object>> buildContributions(Map<String, Object> normalizedScores, Map<String, Object> weights) {
        List<Map<String, Object>> rows = new ArrayList<>();
        double weightedInputSum = 0.0;
        Map<String, Double> weightedInputs = new LinkedHashMap<>();
        for (String source : MAJOR_SOURCES) {
            Double normalizedScore = numericValue(normalizedScores.get(source));
            Double weight = numericValue(weights.get(source));
            if (normalizedScore == null || weight == null) {
                continue;
            }
            double weightedInput = normalizedScore * weight;
            weightedInputs.put(source, weightedInput);
            weightedInputSum += weightedInput;
        }
        for (String source : MAJOR_SOURCES) {
            Double normalizedScore = numericValue(normalizedScores.get(source));
            Double weight = numericValue(weights.get(source));
            Double weightedInput = weightedInputs.get(source);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", source);
            item.put("normalized_score", normalizedScore);
            item.put("weight", weight);
            item.put("weighted_input", weightedInput == null ? null : round(weightedInput));
            item.put("contribution_share", weightedInput == null || weightedInputSum <= 0 ? null : round(weightedInput / weightedInputSum));
            rows.add(item);
        }
        return rows;
    }

    private List<Map<String, Object>> buildWeightedInputs(
            Map<String, Object> ranks,
            Map<String, Object> normalizedScores,
            Map<String, Object> weights
    ) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (String source : MAJOR_SOURCES) {
            Double rank = numericValue(ranks.get(source));
            Double normalizedScore = numericValue(normalizedScores.get(source));
            Double weight = numericValue(weights.get(source));
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", source);
            item.put("rank", rank == null ? null : toRankNumber(rank));
            item.put("normalization", rank == null ? null : "1.0 / rank");
            item.put("normalized_score", normalizedScore);
            item.put("weight", weight);
            item.put("included", rank != null && normalizedScore != null && weight != null);
            rows.add(item);
        }
        return rows;
    }

    private List<Map<String, Object>> buildMissingSourcePenalties(Map<String, Object> weights) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (String source : MAJOR_SOURCES) {
            if (numericValue(weights.get(source)) != null) {
                continue;
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("source_code", source);
            item.put("penalty_type", "coverage_gap");
            item.put("reason", "Source missing from this university's latest global aggregation input.");
            rows.add(item);
        }
        return rows;
    }

    private Map<String, Object> disagreementMetrics(Map<String, Object> ranks) {
        List<Double> values = availableRanks(ranks);
        Map<String, Object> metrics = new LinkedHashMap<>();
        if (values.isEmpty()) {
            metrics.put("available_source_count", 0);
            metrics.put("rank_spread", null);
            metrics.put("average_pairwise_rank_difference", null);
            metrics.put("max_pairwise_rank_difference", null);
            metrics.put("qs_the_rank_difference", null);
            return metrics;
        }

        double min = values.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
        double max = values.stream().mapToDouble(Double::doubleValue).max().orElse(0.0);
        double pairwiseSum = 0.0;
        double pairwiseMax = 0.0;
        int pairwiseCount = 0;
        for (int i = 0; i < values.size(); i++) {
            for (int j = i + 1; j < values.size(); j++) {
                double diff = Math.abs(values.get(i) - values.get(j));
                pairwiseSum += diff;
                pairwiseMax = Math.max(pairwiseMax, diff);
                pairwiseCount += 1;
            }
        }
        Double qsRank = numericValue(ranks.get("QS"));
        Double theRank = numericValue(ranks.get("THE"));
        metrics.put("available_source_count", values.size());
        metrics.put("rank_spread", toRankNumber(max - min));
        metrics.put("average_pairwise_rank_difference", pairwiseCount == 0 ? null : round(pairwiseSum / pairwiseCount));
        metrics.put("max_pairwise_rank_difference", pairwiseCount == 0 ? null : round(pairwiseMax));
        metrics.put("qs_the_rank_difference", qsRank == null || theRank == null ? null : toRankNumber(Math.abs(qsRank - theRank)));
        return metrics;
    }

    private String classifyConfidence(Map<String, Object> ranks) {
        int available = countAvailableSources(ranks);
        if (available == 0) {
            return "low";
        }
        if (available == 1) {
            return "medium";
        }
        List<Double> values = availableRanks(ranks);
        double spread = values.stream().mapToDouble(Double::doubleValue).max().orElse(0.0)
                - values.stream().mapToDouble(Double::doubleValue).min().orElse(0.0);
        if (spread <= AGREEMENT_THRESHOLD) {
            return "high";
        }
        if (spread > SEVERE_DISAGREEMENT_THRESHOLD) {
            return "low";
        }
        return "medium";
    }

    private String confidenceReasoning(Map<String, Object> ranks, String confidence) {
        int available = countAvailableSources(ranks);
        Object spread = disagreementMetrics(ranks).get("rank_spread");
        return switch (confidence) {
            case "high" -> "At least two major sources are available and agree within " + AGREEMENT_THRESHOLD + " rank positions.";
            case "medium" -> available == 1
                    ? "Only one major source is available, so confidence is limited by coverage."
                    : "Multiple sources are available with moderate disagreement. Rank spread: " + spread + ".";
            default -> available == 0
                    ? "No major source ranking evidence is available."
                    : "Severe source disagreement or sparse coverage. Rank spread: " + spread + ".";
        };
    }

    private String whyRankExists(Map<String, Object> aggregate, Map<String, Object> sourceRanks) {
        int available = countAvailableSources(sourceRanks);
        return "This global aggregated rank is the latest stored aggregation for "
                + aggregate.get("university_name")
                + ", using " + available + " available major source"
                + (available == 1 ? "" : "s")
                + " and the existing aggregation output for year "
                + aggregate.get("ranking_year") + ".";
    }

    private List<String> missingSources(Map<String, Object> ranks) {
        return MAJOR_SOURCES.stream()
                .filter(source -> numericValue(ranks.get(source)) == null)
                .toList();
    }

    private Map<String, Object> missingCoverage(Map<String, Long> missingCounts, long total) {
        Map<String, Object> coverage = new LinkedHashMap<>();
        for (String source : MAJOR_SOURCES) {
            long missing = missingCounts.getOrDefault(source, 0L);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("missing_count", missing);
            item.put("missing_pct", pct(missing, total));
            item.put("covered_count", Math.max(total - missing, 0));
            item.put("covered_pct", pct(Math.max(total - missing, 0), total));
            coverage.put(source, item);
        }
        return coverage;
    }

    private Map<String, Object> emptyUniversityComparison(Long canonicalUniversityId) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("canonical_university_id", canonicalUniversityId);
        data.put("sources", List.of());
        data.put("missing_sources", MAJOR_SOURCES);
        data.put("rank_spread", null);
        data.put("confidence", "low");
        data.put("confidence_reasoning", "No latest global aggregation is available.");
        data.put("source_disagreement_metrics", disagreementMetrics(Map.of()));
        data.put("aggregation_contribution", List.of());
        return data;
    }

    private Map<String, Object> orderedNumericJson(Map<String, Object> raw) {
        Map<String, Object> ordered = new LinkedHashMap<>();
        for (String source : MAJOR_SOURCES) {
            ordered.put(source, numericValue(raw.get(source)));
        }
        return ordered;
    }

    private Map<String, Object> orderedRankJson(Map<String, Object> raw) {
        Map<String, Object> ordered = new LinkedHashMap<>();
        for (String source : MAJOR_SOURCES) {
            Double value = numericValue(raw.get(source));
            ordered.put(source, value == null ? null : toRankNumber(value));
        }
        return ordered;
    }

    private Map<String, Object> jsonMap(Object value) {
        if (value == null) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            Map<String, Object> normalized = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                normalized.put(entry.getKey().toUpperCase(Locale.ROOT), entry.getValue());
            }
            return normalized;
        } catch (Exception ex) {
            return new LinkedHashMap<>();
        }
    }

    private int countAvailableSources(Map<String, Object> ranks) {
        return (int) MAJOR_SOURCES.stream().filter(source -> numericValue(ranks.get(source)) != null).count();
    }

    private List<Double> availableRanks(Map<String, Object> ranks) {
        return MAJOR_SOURCES.stream()
                .map(source -> numericValue(ranks.get(source)))
                .filter(value -> value != null && value > 0)
                .toList();
    }

    private Double numericValue(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof BigDecimal decimal) {
            return decimal.doubleValue();
        }
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        try {
            return Double.parseDouble(value.toString());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Integer toInteger(Object value) {
        Double numeric = numericValue(value);
        return numeric == null ? null : (int) Math.round(numeric);
    }

    private Object toRankNumber(Double value) {
        if (value == null) {
            return null;
        }
        long rounded = Math.round(value);
        if (Math.abs(value - rounded) < 0.000001) {
            return rounded;
        }
        return round(value);
    }

    private double pct(long numerator, long denominator) {
        if (denominator <= 0) {
            return 0.0;
        }
        return round((double) numerator * 100.0 / denominator);
    }

    private double round(double value) {
        return Math.round(value * 1_000_000d) / 1_000_000d;
    }
}
