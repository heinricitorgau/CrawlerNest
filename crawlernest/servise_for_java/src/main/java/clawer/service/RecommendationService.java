package clawer.service;

import clawer.model.RecommendationResult;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class RecommendationService {

    private static final double RANKING_WEIGHT = 0.55;
    private static final double IELTS_FIT_WEIGHT = 0.35;
    private static final double COMPLETENESS_WEIGHT = 0.10;
    private static final int RANKING_RANK_CAP = 500;
    private static final double IELTS_GAP_TOLERANCE = 2.0;
    private static final int MAX_LIMIT = 50;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public RecommendationService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    public List<RecommendationResult> getRecommendations(
            String country,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource,
            Integer rankingYear,
            Integer limit
    ) {
        List<Candidate> candidates = fetchCandidates(country, rankingYear);
        List<RecommendationResult> results = new ArrayList<>();
        for (Candidate candidate : candidates) {
            if (!passesHardConstraints(candidate, country, ieltsScore, targetRank, preferredRankingSource)) {
                continue;
            }
            RecommendationResult result = scoreCandidate(candidate, country, ieltsScore, targetRank, preferredRankingSource);
            if (result != null) {
                results.add(result);
            }
        }

        results.sort(
                Comparator.comparing(RecommendationResult::getMatchingScore, Comparator.nullsLast(Double::compareTo)).reversed()
                        .thenComparing(RecommendationResult::getAggregatedRank, Comparator.nullsLast(Integer::compareTo))
                        .thenComparing(RecommendationResult::getCanonicalUniversityId)
        );

        int safeLimit = Math.max(1, Math.min(limit == null ? 10 : limit, MAX_LIMIT));
        if (results.size() > safeLimit) {
            return results.subList(0, safeLimit);
        }
        return results;
    }

    private List<Candidate> fetchCandidates(String country, Integer rankingYear) {
        StringBuilder sql = new StringBuilder("""
                SELECT
                    canonical_university_id,
                    university_name,
                    country,
                    ranking_year,
                    aggregated_rank,
                    composite_score,
                    coverage_ratio,
                    ielts_min,
                    source_ranks_json,
                    aggregation_method_version
                FROM analytics.v_recommendation_candidates_latest
                WHERE 1=1
                """);
        List<Object> params = new ArrayList<>();
        if (country != null && !country.isBlank()) {
            sql.append(" AND country = ?");
            params.add(country);
        }
        if (rankingYear != null) {
            sql.append(" AND ranking_year = ?");
            params.add(rankingYear);
        }
        sql.append(" ORDER BY aggregated_rank NULLS LAST, canonical_university_id");
        return jdbcTemplate.query(sql.toString(), this::mapCandidate, params.toArray());
    }

    private Candidate mapCandidate(ResultSet rs, int rowNum) throws SQLException {
        Candidate candidate = new Candidate();
        candidate.canonicalUniversityId = rs.getLong("canonical_university_id");
        candidate.universityName = rs.getString("university_name");
        candidate.country = rs.getString("country");
        int rankingYear = rs.getInt("ranking_year");
        candidate.rankingYear = rs.wasNull() ? null : rankingYear;
        int aggregatedRank = rs.getInt("aggregated_rank");
        candidate.aggregatedRank = rs.wasNull() ? null : aggregatedRank;
        double coverageRatio = rs.getDouble("coverage_ratio");
        candidate.coverageRatio = rs.wasNull() ? 0.0 : coverageRatio;
        double ieltsMin = rs.getDouble("ielts_min");
        candidate.ieltsMin = rs.wasNull() ? null : ieltsMin;
        candidate.aggregationMethodVersion = rs.getString("aggregation_method_version");
        candidate.sourceRanks = parseJsonMap(rs.getObject("source_ranks_json"));
        return candidate;
    }

    private boolean passesHardConstraints(
            Candidate candidate,
            String country,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource
    ) {
        if (country != null && !country.isBlank()) {
            if (candidate.country == null || !candidate.country.equalsIgnoreCase(country.trim())) {
                return false;
            }
        }

        EffectiveRank effectiveRank = chooseEffectiveRank(candidate, preferredRankingSource);
        if (targetRank != null) {
            if (effectiveRank.rank == null || effectiveRank.rank > targetRank) {
                return false;
            }
        }

        if (ieltsScore != null) {
            if (candidate.ieltsMin == null) {
                return false;
            }
            if (ieltsScore + 1e-9 < candidate.ieltsMin) {
                return false;
            }
        }
        return true;
    }

    private RecommendationResult scoreCandidate(
            Candidate candidate,
            String country,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource
    ) {
        EffectiveRank effectiveRank = chooseEffectiveRank(candidate, preferredRankingSource);
        Double rankingScore = rankingScore(effectiveRank.rank, targetRank);
        Double ieltsFitScore = ieltsFitScore(candidate.ieltsMin, ieltsScore);
        Double completenessScore = completenessScore(candidate);

        Map<String, Double> weightsUsed = new HashMap<>();
        if (rankingScore != null) {
            weightsUsed.put("ranking", RANKING_WEIGHT);
        }
        if (ieltsFitScore != null) {
            weightsUsed.put("ielts_fit", IELTS_FIT_WEIGHT);
        }
        if (completenessScore != null) {
            weightsUsed.put("completeness", COMPLETENESS_WEIGHT);
        }
        if (weightsUsed.isEmpty()) {
            return null;
        }

        double finalScore = weightedAverage(weightsUsed, rankingScore, ieltsFitScore, completenessScore);
        List<String> rulesPassed = new ArrayList<>();
        if (country != null && !country.isBlank()) {
            rulesPassed.add("country=" + country);
        }
        if (targetRank != null && effectiveRank.rank != null) {
            rulesPassed.add("rank<=" + targetRank + " via " + effectiveRank.source + " (" + effectiveRank.rank + ")");
        }
        if (ieltsScore != null && candidate.ieltsMin != null) {
            rulesPassed.add("IELTS " + ieltsScore + " >= required " + candidate.ieltsMin);
        } else if (ieltsScore == null) {
            rulesPassed.add("IELTS filter not applied");
        }

        Map<String, Object> scoreBreakdown = new HashMap<>();
        scoreBreakdown.put("ranking_score", rankingScore);
        scoreBreakdown.put("ielts_fit_score", ieltsFitScore);
        scoreBreakdown.put("completeness_score", completenessScore);
        scoreBreakdown.put("weights_used", weightsUsed);
        scoreBreakdown.put("effective_rank_used", effectiveRank.rank);
        scoreBreakdown.put("effective_rank_source", effectiveRank.source);

        String explanation = buildExplanation(candidate, ieltsScore, rankingScore, ieltsFitScore, completenessScore, finalScore, effectiveRank);

        return new RecommendationResult(
                candidate.canonicalUniversityId,
                candidate.universityName,
                candidate.country,
                candidate.aggregatedRank,
                candidate.ieltsMin,
                round(finalScore),
                explanation,
                candidate.aggregationMethodVersion,
                scoreBreakdown,
                rulesPassed
        );
    }

    private EffectiveRank chooseEffectiveRank(Candidate candidate, String preferredRankingSource) {
        String preferred = preferredRankingSource == null ? "" : preferredRankingSource.trim().toUpperCase();
        if (!preferred.isBlank()) {
            Integer sourceRank = candidate.sourceRanks.get(preferred);
            if (sourceRank != null) {
                return new EffectiveRank(sourceRank, preferred);
            }
        }
        return new EffectiveRank(candidate.aggregatedRank, "AGGREGATED");
    }

    private Double rankingScore(Integer rankValue, Integer targetRank) {
        if (rankValue == null || rankValue <= 0) {
            return null;
        }
        int cap = Math.max(Math.max(RANKING_RANK_CAP, targetRank == null ? 0 : targetRank), rankValue);
        return round(Math.max(0.0, Math.min(100.0, 100.0 * (cap - rankValue + 1.0) / cap)));
    }

    private Double ieltsFitScore(Double requirement, Double ieltsScore) {
        if (ieltsScore == null || requirement == null) {
            return null;
        }
        if (ieltsScore + 1e-9 < requirement) {
            return null;
        }
        double gap = Math.max(0.0, ieltsScore - requirement);
        return round(Math.max(0.0, 100.0 * (1.0 - Math.min(gap / IELTS_GAP_TOLERANCE, 1.0))));
    }

    private Double completenessScore(Candidate candidate) {
        double score = 0.0;
        if (candidate.aggregatedRank != null) {
            score += 40.0;
        }
        if (candidate.ieltsMin != null) {
            score += 30.0;
        }
        score += 30.0 * Math.max(0.0, Math.min(1.0, candidate.coverageRatio));
        return round(Math.min(100.0, score));
    }

    private double weightedAverage(Map<String, Double> weightsUsed, Double rankingScore, Double ieltsFitScore, Double completenessScore) {
        double weightedSum = 0.0;
        double weightSum = 0.0;
        for (Map.Entry<String, Double> entry : weightsUsed.entrySet()) {
            Double score = switch (entry.getKey()) {
                case "ranking" -> rankingScore;
                case "ielts_fit" -> ieltsFitScore;
                case "completeness" -> completenessScore;
                default -> null;
            };
            if (score == null) {
                continue;
            }
            weightedSum += entry.getValue() * score;
            weightSum += entry.getValue();
        }
        if (weightSum <= 0.0) {
            return 0.0;
        }
        return weightedSum / weightSum;
    }

    private String buildExplanation(
            Candidate candidate,
            Double ieltsScore,
            Double rankingScore,
            Double ieltsFitScore,
            Double completenessScore,
            double finalScore,
            EffectiveRank effectiveRank
    ) {
        List<String> parts = new ArrayList<>();
        if (effectiveRank.rank != null) {
            String rankLabel = "AGGREGATED".equals(effectiveRank.source) ? "aggregated rank" : effectiveRank.source + " rank";
            parts.add(rankLabel + " #" + effectiveRank.rank);
        }
        if (ieltsScore != null && candidate.ieltsMin != null) {
            parts.add("IELTS requirement " + candidate.ieltsMin + " matches profile " + ieltsScore);
        }
        if (candidate.country != null && !candidate.country.isBlank()) {
            parts.add("country match: " + candidate.country);
        }
        parts.add(
                "score breakdown: ranking=" + formatScore(rankingScore)
                        + ", ielts_fit=" + formatScore(ieltsFitScore)
                        + ", completeness=" + formatScore(completenessScore)
                        + ", final=" + formatScore(finalScore)
        );
        return String.join("; ", parts);
    }

    private Map<String, Integer> parseJsonMap(Object value) {
        if (value == null) {
            return new HashMap<>();
        }
        try {
            String json = value.toString();
            if (json == null || json.isBlank()) {
                return new HashMap<>();
            }
            Map<String, Object> raw = objectMapper.readValue(json, new TypeReference<>() {});
            Map<String, Integer> parsed = new HashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                if (entry.getValue() == null) {
                    continue;
                }
                parsed.put(entry.getKey().toUpperCase(), Integer.parseInt(entry.getValue().toString()));
            }
            return parsed;
        } catch (Exception e) {
            return new HashMap<>();
        }
    }

    private Double round(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private String formatScore(Double value) {
        if (value == null) {
            return "n/a";
        }
        return String.format("%.2f", value);
    }

    private static final class Candidate {
        private Long canonicalUniversityId;
        private String universityName;
        private String country;
        private Integer rankingYear;
        private Integer aggregatedRank;
        private Double ieltsMin;
        private double coverageRatio;
        private String aggregationMethodVersion;
        private Map<String, Integer> sourceRanks = new HashMap<>();
    }

    private record EffectiveRank(Integer rank, String source) {
    }
}
