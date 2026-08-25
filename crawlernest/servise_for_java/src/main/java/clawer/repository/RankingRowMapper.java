package clawer.repository;

import clawer.dto.AggregationExplainDTO;
import clawer.dto.TrustExplainDTO;
import clawer.domain.ranking.ScopedRankedUniversity;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

class RankingRowMapper {
    private final SourceRankParser sourceRankParser;
    private final ObjectMapper objectMapper;
    private final Logger logger;
    /**
     * Fallback only: used when a row carries no source_weights_used_json. Kept in
     * step with db/analytics_bridge.py:WEIGHTS so the fallback describes the same
     * aggregation the stored rows came from.
     */
    private static final Map<String, Double> DEFAULT_SOURCE_WEIGHTS = Map.of(
            "QS", 0.222,
            "THE", 0.654,
            "ARWU", 0.124
    );

    RankingRowMapper(SourceRankParser sourceRankParser, ObjectMapper objectMapper, Logger logger) {
        this.sourceRankParser = sourceRankParser;
        this.objectMapper = objectMapper;
        this.logger = logger;
    }

    ScopedRankedUniversity map(ResultSet rs) throws SQLException {
        ScopedRankedUniversity row = new ScopedRankedUniversity();
        row.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
        row.setUniversityName(rs.getString("university_name"));
        row.setSlug(rs.getString("slug"));
        row.setCountry(rs.getString("country_name"));

        int rankingYear = rs.getInt("ranking_year");
        row.setRankingYear(rs.wasNull() ? null : rankingYear);

        int globalRank = rs.getInt("global_rank");
        row.setGlobalRank(rs.wasNull() ? null : globalRank);

        int scopeRank = rs.getInt("scope_rank");
        row.setScopeRank(rs.wasNull() ? null : scopeRank);

        double compositeScore = rs.getDouble("composite_score");
        row.setCompositeScore(rs.wasNull() ? null : compositeScore);

        double coverageRatio = rs.getDouble("coverage_ratio");
        row.setCoverageRatio(rs.wasNull() ? null : coverageRatio);

        double ieltsMin = rs.getDouble("ielts_min");
        row.setIeltsMin(rs.wasNull() ? null : ieltsMin);

        int toeflMin = rs.getInt("toefl_min");
        row.setToeflMin(rs.wasNull() ? null : toeflMin);

        int duolingoMin = rs.getInt("duolingo_min");
        row.setDuolingoMin(rs.wasNull() ? null : duolingoMin);

        double gpaMin = rs.getDouble("gpa_min");
        row.setGpaMin(rs.wasNull() ? null : gpaMin);

        java.sql.Date applicationDeadline = rs.getDate("application_deadline");
        row.setApplicationDeadline(applicationDeadline == null ? null : applicationDeadline.toLocalDate().toString());

        row.setAggregationMethodVersion(rs.getString("aggregation_method_version"));
        Object rawSourceRanksJson = rs.getObject("source_ranks_json");
        Map<String, Integer> parsedSourceRanks = sourceRankParser.parse(rawSourceRanksJson);
        row.setSourceRanks(parsedSourceRanks);
        int sourceCount = rs.getInt("source_count");
        row.setSourceCount(rs.wasNull() ? parsedSourceRanks.size() : sourceCount);

        double trustScore = rs.getDouble("trust_score");
        row.setTrustScore(rs.wasNull() ? null : trustScore);
        row.setTrustLevel(rs.getString("trust_level"));
        row.setAggregationExplain(parseAggregationExplain(rs.getObject("aggregation_explain"), parsedSourceRanks, row));
        row.setTrustExplain(parseTrustExplain(rs.getObject("trust_explain"), parsedSourceRanks));
        logger.info(
                "scoped ranking row evidence debug: canonicalUniversityId={}, rawSourceRanksJson={}, parsedSourceRanks={}, sourceCount={}, trustScore={}, trustLevel={}",
                row.getCanonicalUniversityId(),
                rawSourceRanksJson,
                parsedSourceRanks,
                row.getSourceCount(),
                row.getTrustScore(),
                row.getTrustLevel()
        );
        return row;
    }

    private AggregationExplainDTO parseAggregationExplain(
            Object value,
            Map<String, Integer> parsedSourceRanks,
            ScopedRankedUniversity row
    ) {
        if (value == null) {
            return null;
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            AggregationExplainDTO dto = new AggregationExplainDTO();

            Map<String, Integer> sources = sourceRankParser.parse(raw.get("sources"));
            dto.setSources(sources.isEmpty() ? new LinkedHashMap<>(parsedSourceRanks) : sources);
            dto.setWeights(buildDefaultWeights(dto.getSources()));
            dto.setAggregatedRankValue(asDouble(raw.get("aggregated_rank")));
            dto.setAvailableSourceCount(asInteger(raw.get("source_count")));
            Object aggregationMethod = raw.get("aggregation_method");
            dto.setAggregationMethodVersion(aggregationMethod == null ? row.getAggregationMethodVersion() : aggregationMethod.toString());
            dto.setCoverageRatio(row.getCoverageRatio());
            dto.setCompositeScore(row.getCompositeScore());
            dto.setNote(buildAggregationNote(dto.getAvailableSourceCount()));
            return dto;
        } catch (Exception ex) {
            logger.warn("failed to parse aggregation_explain json", ex);
            return null;
        }
    }

    private TrustExplainDTO parseTrustExplain(Object value, Map<String, Integer> parsedSourceRanks) {
        if (value == null) {
            return null;
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            TrustExplainDTO dto = new TrustExplainDTO();
            dto.setSources(new LinkedHashMap<>(parsedSourceRanks));

            Double coverageScore = asDouble(raw.get("coverage_score"));
            dto.setCoverageScore(coverageScore == null ? 0.0 : coverageScore * 100.0);
            Double consistencyScore = asDouble(raw.get("consistency_score"));
            dto.setConsistencyScore(consistencyScore == null ? 0.0 : consistencyScore);
            Double stdDeviation = asDouble(raw.get("std_deviation"));
            dto.setStdDeviation(stdDeviation == null ? 0.0 : stdDeviation);
            dto.setNotes(asStringList(raw.get("notes")));
            return dto;
        } catch (Exception ex) {
            logger.warn("failed to parse trust_explain json", ex);
            return null;
        }
    }

    private Map<String, Double> buildDefaultWeights(Map<String, Integer> sources) {
        Map<String, Double> weights = new LinkedHashMap<>();
        for (String source : List.of("QS", "THE", "ARWU")) {
            if (sources.containsKey(source)) {
                weights.put(source, DEFAULT_SOURCE_WEIGHTS.getOrDefault(source, 0.0));
            }
        }
        if (weights.isEmpty()) {
            for (Map.Entry<String, Integer> entry : sources.entrySet()) {
                weights.put(entry.getKey(), DEFAULT_SOURCE_WEIGHTS.getOrDefault(entry.getKey(), 0.0));
            }
        }
        return weights;
    }

    private String buildAggregationNote(Integer availableSourceCount) {
        if (availableSourceCount == null) {
            return null;
        }
        return switch (availableSourceCount) {
            case 3 -> "Three ranking sources available.";
            case 2 -> "Two ranking sources available.";
            case 1 -> "Only one ranking source available.";
            default -> "No ranking source evidence available.";
        };
    }

    private Double asDouble(Object value) {
        if (value == null) {
            return null;
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

    private Integer asInteger(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return (int) Math.round(number.doubleValue());
        }
        try {
            return (int) Math.round(Double.parseDouble(value.toString()));
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private List<String> asStringList(Object value) {
        if (value instanceof List<?> list) {
            return list.stream().map(String::valueOf).toList();
        }
        return List.of();
    }
}
