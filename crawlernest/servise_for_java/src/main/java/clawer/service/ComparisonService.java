package clawer.service;

import clawer.dto.RankingTrustDTO;
import clawer.model.UniversityComparisonResult;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.OptionalInt;
import java.util.Set;
import java.util.stream.Collectors;

@Service
public class ComparisonService {

    private static final List<String> SOURCE_ORDER = List.of("QS", "THE", "ARWU");
    private static final int MISSING_RANK = 1_000_000_000;
    private static final double MISSING_SCORE = 1_000_000_000.0;
    private static final double MISSING_SOURCE_PENALTY = 200.0;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final DatasetScope datasetScope;

    @Autowired
    public ComparisonService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.datasetScope = datasetScope;
    }

    public ComparisonService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this(jdbcTemplate, objectMapper, DatasetScope.standard());
    }

    public UniversityComparisonResult compareUniversities(List<String> identifiers, Integer rankingYear) {
        List<String> distinctIdentifiers = identifiers.stream()
                .filter(Objects::nonNull)
                .map(String::trim)
                .filter(value -> !value.isBlank())
                .collect(Collectors.toCollection(ArrayList::new));
        if (distinctIdentifiers.size() < 2) {
            throw new IllegalArgumentException("Comparison requires at least two university identifiers.");
        }

        List<Candidate> candidates = resolveUniversities(distinctIdentifiers, rankingYear);
        List<Candidate> ordered = new ArrayList<>(candidates);
        ordered.sort(candidateComparator());

        List<Candidate> tiedWinners = ordered.stream()
                .filter(candidate -> candidateComparator().compare(candidate, ordered.get(0)) == 0)
                .toList();
        Candidate winner = tiedWinners.size() == 1 ? ordered.get(0) : null;

        Map<String, Object> universities = new LinkedHashMap<>();
        for (Candidate candidate : ordered) {
            universities.put(candidate.universityName, serializeUniversity(candidate));
        }

        Map<String, Object> ranking = buildRankingDimension(ordered);
        Map<String, Object> ielts = buildIeltsDimension(ordered);
        Map<String, Object> completeness = buildCompletenessDimension(ordered);
        Map<String, Object> sources = new LinkedHashMap<>();
        for (String source : SOURCE_ORDER) {
            sources.put(source, buildSourceDimension(ordered, source));
        }

        List<String> decisionFactors = new ArrayList<>();
        decisionFactors.add((String) ranking.get("explanation"));
        decisionFactors.add((String) ielts.get("explanation"));
        decisionFactors.add((String) completeness.get("explanation"));
        for (String source : SOURCE_ORDER) {
            decisionFactors.add((String) ((Map<?, ?>) sources.get(source)).get("explanation"));
        }

        Map<String, Object> comparison = new LinkedHashMap<>();
        comparison.put("universities", universities);
        comparison.put("ranking", ranking);
        comparison.put("ielts", ielts);
        comparison.put("dataCompleteness", completeness);
        comparison.put("sources", sources);
        comparison.put("decisionFactors", decisionFactors);

        Map<String, Object> betterUniv = null;
        if (winner != null) {
            betterUniv = Map.of(
                "canonicalUniversityId", winner.canonicalUniversityId,
                "universityName", winner.universityName
            );
        }

        return new UniversityComparisonResult(
                betterUniv,
                buildSummary(ordered, winner, ranking, ielts, completeness, sources),
                ordered.stream().map(candidate -> candidate.universityName).toList(),
                comparison
        );
    }

    private List<Candidate> resolveUniversities(List<String> identifiers, Integer rankingYear) {
        // Without an edition, a university held in two editions matched twice, and
        // the better-ranked edition's row won the tie -- a comparison that could
        // quietly set one university's current rank against another's old one.
        OptionalInt edition = datasetScope.resolveRankingYear(rankingYear);
        if (edition.isEmpty()) {
            throw new IllegalArgumentException("No ranking data is available for year " + rankingYear + ".");
        }
        List<Candidate> resolved = new ArrayList<>();
        Set<Long> seenIds = new LinkedHashSet<>();
        for (String identifier : identifiers) {
            Candidate candidate = resolveUniversity(identifier, edition.getAsInt());
            if (seenIds.add(candidate.canonicalUniversityId)) {
                resolved.add(candidate);
            }
        }
        if (resolved.size() < 2) {
            throw new IllegalArgumentException("Comparison requires at least two distinct universities.");
        }
        return resolved;
    }

    private Candidate resolveUniversity(String identifier, int rankingYear) {
        Long numericId = identifier.chars().allMatch(Character::isDigit) ? Long.parseLong(identifier) : null;
        String normalized = normalizeLookup(identifier);
        String partialPattern = "%" + identifier + "%";
        List<ResolvedCandidate> matches = jdbcTemplate.query(
                """
                SELECT
                    v.canonical_university_id,
                    v.university_name,
                    v.country,
                    v.ranking_year,
                    v.aggregated_rank,
                    v.composite_score,
                    v.coverage_ratio,
                    v.ielts_min,
                    v.source_ranks_json,
                    v.source_scores_json,
                    v.aggregation_method_version,
                    CASE
                        WHEN CAST(? AS BIGINT) IS NOT NULL AND v.canonical_university_id = CAST(? AS BIGINT) THEN 0
                        WHEN lower(v.university_name) = lower(?) THEN 1
                        WHEN regexp_replace(lower(v.university_name), '[^a-z0-9]+', ' ', 'g') = ? THEN 2
                        WHEN lower(v.university_name) LIKE lower(?) THEN 3
                        ELSE 100
                    END AS match_priority
                FROM analytics.v_recommendation_candidates_latest v
                WHERE v.ranking_year = CAST(? AS INTEGER)
                  AND (
                      (CAST(? AS BIGINT) IS NOT NULL AND v.canonical_university_id = CAST(? AS BIGINT))
                      OR lower(v.university_name) = lower(?)
                      OR regexp_replace(lower(v.university_name), '[^a-z0-9]+', ' ', 'g') = ?
                      OR lower(v.university_name) LIKE lower(?)
                  )
                ORDER BY match_priority, v.aggregated_rank NULLS LAST, v.canonical_university_id
                LIMIT 5
                """,
                (rs, rowNum) -> mapResolvedCandidate(rs),
                numericId,
                numericId,
                identifier,
                normalized,
                partialPattern,
                rankingYear,
                numericId,
                numericId,
                identifier,
                normalized,
                partialPattern
        );
        if (matches.isEmpty()) {
            throw new IllegalArgumentException("University not found for identifier: " + identifier);
        }

        int topPriority = matches.get(0).matchPriority;
        List<ResolvedCandidate> bestMatches = matches.stream()
                .filter(match -> match.matchPriority == topPriority)
                .toList();
        long distinctCount = bestMatches.stream()
                .map(match -> match.candidate.canonicalUniversityId)
                .distinct()
                .count();
        if (distinctCount > 1) {
            String labels = bestMatches.stream()
                    .map(match -> match.candidate.universityName)
                    .limit(3)
                    .collect(Collectors.joining(", "));
            throw new IllegalArgumentException("University identifier is ambiguous: " + identifier + ". Matches: " + labels);
        }
        return matches.get(0).candidate;
    }

    private ResolvedCandidate mapResolvedCandidate(ResultSet rs) throws SQLException {
        Candidate candidate = new Candidate();
        candidate.canonicalUniversityId = rs.getLong("canonical_university_id");
        candidate.universityName = rs.getString("university_name");
        candidate.country = rs.getString("country");
        int rankingYear = rs.getInt("ranking_year");
        candidate.rankingYear = rs.wasNull() ? null : rankingYear;
        int aggregatedRank = rs.getInt("aggregated_rank");
        candidate.aggregatedRank = rs.wasNull() ? null : aggregatedRank;
        double compositeScore = rs.getDouble("composite_score");
        candidate.aggregatedScore = rs.wasNull() ? null : compositeScore;
        double coverageRatio = rs.getDouble("coverage_ratio");
        candidate.coverageRatio = rs.wasNull() ? 0.0 : coverageRatio;
        double ieltsMin = rs.getDouble("ielts_min");
        candidate.ieltsMin = rs.wasNull() ? null : ieltsMin;
        candidate.aggregationMethodVersion = rs.getString("aggregation_method_version");
        candidate.sourceRanks = parseIntegerMap(rs.getObject("source_ranks_json"));
        candidate.sourceScores = parseDoubleMap(rs.getObject("source_scores_json"));
        return new ResolvedCandidate(candidate, rs.getInt("match_priority"));
    }

    private Comparator<Candidate> candidateComparator() {
        return Comparator
                .comparing((Candidate candidate) -> candidate.aggregatedRank == null)
                .thenComparing(candidate -> candidate.aggregatedRank == null ? MISSING_RANK : candidate.aggregatedRank)
                .thenComparing(candidate -> averageSourceRank(candidate) >= MISSING_SCORE)
                .thenComparing(this::averageSourceRank)
                .thenComparing(candidate -> candidate.ieltsMin == null)
                .thenComparing(candidate -> candidate.ieltsMin == null ? MISSING_SCORE : candidate.ieltsMin)
                .thenComparing((Candidate candidate) -> completenessCount(candidate), Comparator.reverseOrder())
                .thenComparing(candidate -> candidate.universityName.toLowerCase(Locale.ROOT))
                .thenComparing(candidate -> candidate.canonicalUniversityId);
    }

    private String buildSummary(
            List<Candidate> ordered,
            Candidate winner,
            Map<String, Object> ranking,
            Map<String, Object> ielts,
            Map<String, Object> completeness,
            Map<String, Object> sources
    ) {
        if (winner == null) {
            return "No single university is deterministically ahead because the compared schools are tied on the configured comparison order.";
        }
        Candidate runnerUp = ordered.get(1);
        if (winner.universityName.equals(ranking.get("winner"))) {
            return (String) ranking.get("explanation");
        }
        boolean hasSourceWin = SOURCE_ORDER.stream().anyMatch(source -> winner.universityName.equals(((Map<?, ?>) sources.get(source)).get("winner")));
        if (hasSourceWin) {
            return winner.universityName + " edges ahead of " + runnerUp.universityName + " because aggregated rank does not separate them, but its per-source rankings are stronger.";
        }
        if (winner.universityName.equals(ielts.get("winner"))) {
            return winner.universityName + " is preferred over " + runnerUp.universityName + " because ranking is tied or incomplete, and it has the lower IELTS requirement.";
        }
        if (winner.universityName.equals(completeness.get("winner"))) {
            return winner.universityName + " is preferred over " + runnerUp.universityName + " because ranking is tied or incomplete, and it has more complete evidence across ranking and admission fields.";
        }
        return winner.universityName + " is the deterministic winner after applying aggregated rank, source ranks, IELTS requirement, and data completeness in order.";
    }

    private Map<String, Object> buildRankingDimension(List<Candidate> universities) {
        Map<String, Object> values = new LinkedHashMap<>();
        for (Candidate candidate : universities) {
            values.put(candidate.universityName, candidate.aggregatedRank);
        }
        List<Candidate> available = universities.stream().filter(candidate -> candidate.aggregatedRank != null).toList();
        if (available.isEmpty()) {
            return dimension(values, "Tie", "Aggregated ranking is missing for all compared universities, so ranking cannot separate them.");
        }
        int bestRank = available.stream().map(candidate -> candidate.aggregatedRank).min(Integer::compareTo).orElse(MISSING_RANK);
        List<Candidate> winners = available.stream().filter(candidate -> candidate.aggregatedRank == bestRank).toList();
        if (available.size() == 1) {
            List<String> missing = universities.stream()
                    .filter(candidate -> candidate.aggregatedRank == null)
                    .map(candidate -> candidate.universityName)
                    .toList();
            Candidate only = available.get(0);
            return dimension(values, only.universityName,
                    only.universityName + " has aggregated rank #" + only.aggregatedRank + ", while " + String.join(", ", missing) + " has no aggregated rank data.");
        }
        if (winners.size() > 1) {
            return dimension(values, "Tie",
                    joinNames(winners.stream().map(candidate -> candidate.universityName).toList()) + " share the best aggregated rank at #" + bestRank + ", so aggregated ranking does not separate them.");
        }
        Candidate winner = winners.get(0);
        Candidate runnerUp = available.stream()
                .filter(candidate -> !candidate.universityName.equals(winner.universityName))
                .min(Comparator.comparing(candidate -> candidate.aggregatedRank))
                .orElseThrow();
        int gap = runnerUp.aggregatedRank - bestRank;
        return dimension(values, winner.universityName,
                winner.universityName + " ranks #" + bestRank + " overall versus " + runnerUp.universityName + " at #" + runnerUp.aggregatedRank + ", giving it a " + gap + "-place aggregated ranking advantage.");
    }

    private Map<String, Object> buildIeltsDimension(List<Candidate> universities) {
        Map<String, Object> values = new LinkedHashMap<>();
        for (Candidate candidate : universities) {
            values.put(candidate.universityName, candidate.ieltsMin);
        }
        List<Candidate> available = universities.stream().filter(candidate -> candidate.ieltsMin != null).toList();
        if (available.isEmpty()) {
            return dimension(values, "Tie", "IELTS requirement data is missing for all compared universities.");
        }
        double bestRequirement = available.stream().map(candidate -> candidate.ieltsMin).min(Double::compareTo).orElse(MISSING_SCORE);
        List<Candidate> winners = available.stream().filter(candidate -> Double.compare(candidate.ieltsMin, bestRequirement) == 0).toList();
        if (available.size() == 1) {
            Candidate only = available.get(0);
            return dimension(values, only.universityName,
                    only.universityName + " lists IELTS " + formatNumber(only.ieltsMin) + ", while at least one compared university is missing IELTS data.");
        }
        if (winners.size() > 1) {
            return dimension(values, "Tie",
                    joinNames(winners.stream().map(candidate -> candidate.universityName).toList()) + " share the lowest listed IELTS requirement at " + formatNumber(bestRequirement) + ", so IELTS does not separate them.");
        }
        Candidate winner = winners.get(0);
        Candidate runnerUp = available.stream()
                .filter(candidate -> !candidate.universityName.equals(winner.universityName))
                .min(Comparator.comparing(candidate -> candidate.ieltsMin))
                .orElseThrow();
        double gap = round(runnerUp.ieltsMin - bestRequirement);
        return dimension(values, winner.universityName,
                winner.universityName + " requires IELTS " + formatNumber(bestRequirement) + " versus " + runnerUp.universityName + " at " + formatNumber(runnerUp.ieltsMin) + ", making it more accessible by " + formatNumber(gap) + " band points.");
    }

    private Map<String, Object> buildCompletenessDimension(List<Candidate> universities) {
        Map<String, Object> values = new LinkedHashMap<>();
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (Candidate candidate : universities) {
            values.put(candidate.universityName, completenessSnapshot(candidate));
            counts.put(candidate.universityName, completenessCount(candidate));
        }
        int bestCount = counts.values().stream().max(Integer::compareTo).orElse(0);
        List<String> winners = counts.entrySet().stream()
                .filter(entry -> entry.getValue() == bestCount)
                .map(Map.Entry::getKey)
                .toList();
        if (winners.size() > 1) {
            return dimension(values, "Tie", "The compared universities have the same level of data completeness in the tracked fields.");
        }
        String winner = winners.get(0);
        String runnerUp = counts.entrySet().stream()
                .filter(entry -> !entry.getKey().equals(winner))
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed().thenComparing(Map.Entry.comparingByKey()))
                .map(Map.Entry::getKey)
                .findFirst()
                .orElseThrow();
        return dimension(values, winner,
                winner + " has " + counts.get(winner) + " of 5 tracked evidence points available, versus " + runnerUp + " with " + counts.get(runnerUp) + ", so it has the more complete comparison record.");
    }

    private Map<String, Object> buildSourceDimension(List<Candidate> universities, String source) {
        Map<String, Object> values = new LinkedHashMap<>();
        List<Map.Entry<String, Integer>> available = new ArrayList<>();
        for (Candidate candidate : universities) {
            Integer rank = candidate.sourceRanks.get(source);
            values.put(candidate.universityName, rank);
            if (rank != null) {
                available.add(Map.entry(candidate.universityName, rank));
            }
        }
        if (available.isEmpty()) {
            return dimension(values, "Tie", source + " rank data is missing for all compared universities.");
        }
        int bestRank = available.stream().map(Map.Entry::getValue).min(Integer::compareTo).orElse(MISSING_RANK);
        List<Map.Entry<String, Integer>> winners = available.stream().filter(entry -> entry.getValue() == bestRank).toList();
        if (available.size() == 1) {
            return dimension(values, available.get(0).getKey(), "Only " + available.get(0).getKey() + " has " + source + " rank data, so " + source + " favors it by default.");
        }
        if (winners.size() > 1) {
            return dimension(values, "Tie", joinNames(winners.stream().map(Map.Entry::getKey).toList()) + " share the best " + source + " rank at #" + bestRank + ".");
        }
        Map.Entry<String, Integer> winner = winners.get(0);
        Map.Entry<String, Integer> runnerUp = available.stream()
                .filter(entry -> !entry.getKey().equals(winner.getKey()))
                .min(Comparator.comparing(Map.Entry::getValue))
                .orElseThrow();
        int gap = runnerUp.getValue() - bestRank;
        return dimension(values, winner.getKey(),
                winner.getKey() + " is stronger in " + source + " at #" + bestRank + " versus " + runnerUp.getKey() + " at #" + runnerUp.getValue() + ", a " + gap + "-place source advantage.");
    }

    private Map<String, Object> serializeUniversity(Candidate candidate) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("canonicalUniversityId", candidate.canonicalUniversityId);
        payload.put("universityName", candidate.universityName);
        payload.put("country", candidate.country);
        payload.put("aggregatedRank", candidate.aggregatedRank);
        payload.put("aggregatedScore", candidate.aggregatedScore);
        payload.put("ieltsMin", candidate.ieltsMin);
        Map<String, Object> sourceRanks = new LinkedHashMap<>();
        for (String source : SOURCE_ORDER) {
            if (candidate.sourceRanks.get(source) != null) {
                sourceRanks.put(source, candidate.sourceRanks.get(source));
            }
        }
        payload.put("sourceRanks", sourceRanks);
        payload.put("dataCompleteness", completenessSnapshot(candidate));
        payload.put("aggregationMethodVersion", candidate.aggregationMethodVersion);
        payload.put("evidenceSummary", buildEvidenceSummary(candidate));
        RankingTrustDTO trust = RankingTrustLayer.buildTrustScore(candidate.sourceRanks);
        payload.put("trustScore", trust.getTrustScore());
        payload.put("trustLevel", trust.getTrustLevel());
        payload.put("trustExplain", trust.getTrustExplain());
        payload.put("warnings", buildWarnings(candidate, trust));
        return payload;
    }

    private Map<String, Object> buildEvidenceSummary(Candidate candidate) {
        List<Integer> available = SOURCE_ORDER.stream()
                .map(candidate.sourceRanks::get)
                .filter(Objects::nonNull)
                .toList();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("availableSourceCount", available.size());

        if (available.isEmpty()) {
            payload.put("bestRank", null);
            payload.put("worstRank", null);
            payload.put("spread", null);
            payload.put("agreementLevel", "limited");
            payload.put("note", "No ranking evidence is available for this comparison record.");
            return payload;
        }

        int bestRank = available.stream().min(Integer::compareTo).orElse(MISSING_RANK);
        int worstRank = available.stream().max(Integer::compareTo).orElse(MISSING_RANK);
        int spread = worstRank - bestRank;
        String agreementLevel;
        String note;

        if (available.size() == 1) {
            agreementLevel = "limited";
            note = "Only one ranking source is available for this university.";
        } else if (spread <= 5) {
            agreementLevel = "strong";
            note = "Multiple ranking sources broadly agree.";
        } else if (spread <= 20) {
            agreementLevel = "moderate";
            note = "Ranking sources show moderate variation.";
        } else {
            agreementLevel = "weak";
            note = "Large disagreement across sources — interpret carefully.";
        }

        payload.put("bestRank", bestRank);
        payload.put("worstRank", worstRank);
        payload.put("spread", spread);
        payload.put("agreementLevel", agreementLevel);
        payload.put("note", note);
        return payload;
    }

    private List<String> buildWarnings(Candidate candidate, RankingTrustDTO trust) {
        List<String> warnings = new ArrayList<>();
        if (candidate.ieltsMin == null) {
            warnings.add("No structured admissions data available");
        }
        if (candidate.sourceRanks.size() <= 1) {
            warnings.add("Limited evidence");
        }
        if ("low".equalsIgnoreCase(trust.getTrustLevel())) {
            warnings.add("Low trust ranking evidence");
        }
        return warnings;
    }

    private Map<String, Object> completenessSnapshot(Candidate candidate) {
        int availableSources = (int) SOURCE_ORDER.stream().filter(source -> candidate.sourceRanks.get(source) != null).count();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("hasAggregatedRank", candidate.aggregatedRank != null);
        payload.put("hasIeltsRequirement", candidate.ieltsMin != null);
        payload.put("availableSourceCount", availableSources);
        payload.put("sourceCoverageRatio", round((double) availableSources / SOURCE_ORDER.size()));
        payload.put("coverageRatio", round(candidate.coverageRatio));
        return payload;
    }

    private int completenessCount(Candidate candidate) {
        return (candidate.aggregatedRank != null ? 1 : 0)
                + (candidate.ieltsMin != null ? 1 : 0)
                + (int) SOURCE_ORDER.stream().filter(source -> candidate.sourceRanks.get(source) != null).count();
    }

    private double averageSourceRank(Candidate candidate) {
        List<Integer> available = SOURCE_ORDER.stream()
                .map(candidate.sourceRanks::get)
                .filter(Objects::nonNull)
                .toList();
        if (available.isEmpty()) {
            return MISSING_SCORE;
        }
        double mean = available.stream().mapToInt(Integer::intValue).average().orElse(MISSING_SCORE);
        int missingCount = SOURCE_ORDER.size() - available.size();
        return mean + (missingCount * MISSING_SOURCE_PENALTY);
    }

    private Map<String, Integer> parseIntegerMap(Object value) {
        if (value == null) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            Map<String, Integer> parsed = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                if (entry.getValue() != null) {
                    parsed.put(entry.getKey().toUpperCase(Locale.ROOT), Integer.parseInt(entry.getValue().toString()));
                }
            }
            return parsed;
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private Map<String, Double> parseDoubleMap(Object value) {
        if (value == null) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            Map<String, Double> parsed = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                if (entry.getValue() != null) {
                    parsed.put(entry.getKey().toUpperCase(Locale.ROOT), Double.parseDouble(entry.getValue().toString()));
                }
            }
            return parsed;
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private Map<String, Object> dimension(Map<String, Object> values, String winner, String explanation) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("values", values);
        payload.put("winner", winner);
        payload.put("explanation", explanation);
        return payload;
    }

    private String joinNames(List<String> names) {
        if (names.size() <= 1) {
            return names.isEmpty() ? "" : names.get(0);
        }
        if (names.size() == 2) {
            return names.get(0) + " and " + names.get(1);
        }
        return String.join(", ", names.subList(0, names.size() - 1)) + ", and " + names.get(names.size() - 1);
    }

    private String normalizeLookup(String value) {
        String normalized = Normalizer.normalize(value.trim().toLowerCase(Locale.ROOT), Normalizer.Form.NFKD)
                .replaceAll("\\p{M}+", "")
                .replaceAll("[^a-z0-9]+", " ")
                .trim();
        return normalized.replaceAll("\\s+", " ");
    }

    private double round(double value) {
        return Math.round(value * 10000.0) / 10000.0;
    }

    private String formatNumber(double value) {
        if (Math.rint(value) == value) {
            return Integer.toString((int) value);
        }
        return Double.toString(value);
    }

    private static final class Candidate {
        private Long canonicalUniversityId;
        private String universityName;
        private String country;
        private Integer rankingYear;
        private Integer aggregatedRank;
        private Double aggregatedScore;
        private double coverageRatio;
        private Double ieltsMin;
        private String aggregationMethodVersion;
        private Map<String, Integer> sourceRanks = new LinkedHashMap<>();
        private Map<String, Double> sourceScores = new LinkedHashMap<>();
    }

    private record ResolvedCandidate(Candidate candidate, int matchPriority) {
    }
}
