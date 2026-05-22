package clawer.service;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Readonly evidence service for recommendation explanations.
 *
 * Reads stored data to explain WHY a university was recommended.
 * Does not recalculate scores, does not mutate any data.
 */
@Service
public class RecommendationEvidenceService {

    private static final List<String> SOURCES = List.of("QS", "THE", "ARWU");

    private static final List<String> RC1_STANDARD_CAVEATS = List.of(
            "QS ranking data was last ingested at RC-1 packaging. Data may not reflect the current published rankings.",
            "THE (Times Higher Education) data is not available at RC-1. Rankings reflect QS source only.",
            "ARWU (Academic Ranking of World Universities) data is not available at RC-1. Rankings reflect QS source only."
    );

    private final JdbcTemplate jdbcTemplate;

    public RecommendationEvidenceService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Gathers evidence for a single university from stored data.
     * Returns 404 if the university does not exist.
     */
    public Map<String, Object> getEvidence(
            long canonicalUniversityId,
            Double ieltsScore,
            Integer targetRank,
            String country,
            String subjectKey
    ) {
        Map<String, Object> identity = fetchIdentity(canonicalUniversityId);
        Map<String, Object> ranking = fetchRankingEvidence(canonicalUniversityId);
        Map<String, Object> sourceCoverage = buildSourceCoverage(ranking);
        Map<String, Object> ieltsEvidence = buildIeltsEvidence(canonicalUniversityId, ieltsScore);
        Map<String, Object> countryEvidence = buildCountryEvidence(identity, country);
        int sourceCount = (int) sourceCoverage.get("source_count");
        Map<String, Object> confidenceEvidence = buildConfidenceEvidence(ranking, ieltsEvidence, sourceCount);

        List<String> caveats = new ArrayList<>(RC1_STANDARD_CAVEATS);
        if (Boolean.TRUE.equals(ieltsEvidence.get("ielts_min_missing"))) {
            caveats.add("No IELTS requirement was found in stored admission data for this university. Language fit cannot be assessed.");
        }
        if (sourceCount <= 1) {
            caveats.add("This university has single-source ranking coverage (QS only). Multi-source agreement analysis is not available.");
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("university_identity", identity);
        response.put("ranking_evidence", ranking);
        response.put("source_coverage", sourceCoverage);
        response.put("ielts_evidence", ieltsEvidence);
        response.put("country_evidence", countryEvidence);
        response.put("confidence_evidence", confidenceEvidence);

        if (subjectKey != null && !subjectKey.isBlank()) {
            Map<String, Object> subjectEvidence = fetchSubjectEvidence(canonicalUniversityId, subjectKey.trim().toLowerCase());
            response.put("subject_evidence", subjectEvidence);
            if (Boolean.FALSE.equals(subjectEvidence.get("has_data"))) {
                caveats.add("No subject ranking row was found for this university and subject. A neutral fallback was applied.");
            }
            caveats.add("Subject rankings are QS-sourced only at RC-1. THE and ARWU subject data is not available.");
        }

        response.put("caveats", caveats);
        response.put("evaluation_timestamp", Instant.now().toString());
        return response;
    }

    // ── Private: identity ─────────────────────────────────────────────────────

    private Map<String, Object> fetchIdentity(long canonicalUniversityId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    cu.canonical_slug,
                    c.country_name,
                    c.country_code
                FROM warehouse.canonical_university cu
                LEFT JOIN warehouse.countries c ON c.country_id = cu.country_id
                WHERE cu.canonical_university_id = ?
                """, canonicalUniversityId);

        if (rows.isEmpty()) {
            throw new ResponseStatusException(
                    HttpStatus.NOT_FOUND,
                    "University not found: canonicalUniversityId=" + canonicalUniversityId
            );
        }
        Map<String, Object> row = rows.get(0);
        Map<String, Object> identity = new LinkedHashMap<>();
        identity.put("canonical_university_id", row.get("canonical_university_id"));
        identity.put("display_name", row.get("display_name"));
        identity.put("canonical_slug", row.get("canonical_slug"));
        identity.put("country_name", row.get("country_name"));
        identity.put("country_code", row.get("country_code"));
        return identity;
    }

    // ── Private: ranking ─────────────────────────────────────────────────────

    private Map<String, Object> fetchRankingEvidence(long canonicalUniversityId) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT
                    ar.display_rank,
                    ar.ranking_year,
                    ar.composite_score,
                    ar.coverage_ratio,
                    ar.aggregation_method_version,
                    ar.source_ranks_json
                FROM analytics.aggregated_rankings ar
                JOIN analytics.aggregation_runs run
                  ON run.aggregation_run_id = ar.aggregation_run_id
                WHERE run.status = 'finished'
                  AND ar.universe_type = 'global'
                  AND ar.universe_key = 'global'
                  AND ar.canonical_university_id = ?
                ORDER BY ar.ranking_year DESC, ar.display_rank ASC NULLS LAST
                LIMIT 1
                """, canonicalUniversityId);

        Map<String, Object> evidence = new LinkedHashMap<>();
        if (rows.isEmpty()) {
            evidence.put("available", false);
            evidence.put("display_rank", null);
            evidence.put("ranking_year", null);
            evidence.put("composite_score", null);
            evidence.put("coverage_ratio", null);
            evidence.put("aggregation_method_version", null);
            evidence.put("source_ranks_json", null);
        } else {
            Map<String, Object> row = rows.get(0);
            evidence.put("available", true);
            evidence.put("display_rank", row.get("display_rank"));
            evidence.put("ranking_year", row.get("ranking_year"));
            evidence.put("composite_score", row.get("composite_score"));
            evidence.put("coverage_ratio", row.get("coverage_ratio"));
            evidence.put("aggregation_method_version", row.get("aggregation_method_version"));
            evidence.put("source_ranks_json", row.get("source_ranks_json"));
        }
        return evidence;
    }

    // ── Private: source coverage ─────────────────────────────────────────────

    private Map<String, Object> buildSourceCoverage(Map<String, Object> ranking) {
        Object jsonObj = ranking.get("source_ranks_json");
        String json = jsonObj == null ? "" : jsonObj.toString();

        Map<String, Object> coverage = new LinkedHashMap<>();
        int count = 0;
        for (String source : SOURCES) {
            boolean present = json.contains("\"" + source + "\"");
            coverage.put(source.toLowerCase() + "_available", present);
            if (present) count++;
        }
        coverage.put("source_count", count);
        coverage.put("coverage_label", count >= 3 ? "multi_source" : count == 1 ? "single_source" : count == 0 ? "no_source" : "partial_multi_source");
        return coverage;
    }

    // ── Private: IELTS ────────────────────────────────────────────────────────

    private Map<String, Object> buildIeltsEvidence(long canonicalUniversityId, Double ieltsScore) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT MIN(ar.ielts_min) AS ielts_min
                FROM warehouse.canonical_university_link cul
                JOIN warehouse.admission_requirements ar
                  ON ar.university_id = cul.university_id
                WHERE cul.canonical_university_id = ?
                  AND ar.ielts_min IS NOT NULL
                """, canonicalUniversityId);

        Double ieltsMin = null;
        if (!rows.isEmpty() && rows.get(0).get("ielts_min") != null) {
            ieltsMin = ((Number) rows.get(0).get("ielts_min")).doubleValue();
        }

        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("ielts_min", ieltsMin);
        evidence.put("ielts_min_missing", ieltsMin == null);
        evidence.put("ielts_provided", ieltsScore);

        if (ieltsMin == null) {
            evidence.put("ielts_fit", "no_data");
            evidence.put("ielts_margin", null);
        } else if (ieltsScore == null) {
            evidence.put("ielts_fit", "not_assessed");
            evidence.put("ielts_margin", null);
        } else {
            double margin = Math.round((ieltsScore - ieltsMin) * 100.0) / 100.0;
            evidence.put("ielts_margin", margin);
            evidence.put("ielts_fit", margin >= 0 ? "meets" : "shortfall");
        }
        return evidence;
    }

    // ── Private: country ─────────────────────────────────────────────────────

    private Map<String, Object> buildCountryEvidence(Map<String, Object> identity, String country) {
        Map<String, Object> evidence = new LinkedHashMap<>();
        String universityCountry = (String) identity.get("country_name");
        evidence.put("university_country", universityCountry);
        evidence.put("preferred_country", country);

        if (country == null || country.isBlank()) {
            evidence.put("country_match", "no_preference");
        } else if (universityCountry != null && universityCountry.equalsIgnoreCase(country.trim())) {
            evidence.put("country_match", "exact_match");
        } else {
            evidence.put("country_match", "mismatch");
        }
        return evidence;
    }

    // ── Private: confidence ───────────────────────────────────────────────────

    private Map<String, Object> buildConfidenceEvidence(
            Map<String, Object> ranking,
            Map<String, Object> ieltsEvidence,
            int sourceCount
    ) {
        double completeness = 0.0;
        if (ranking.get("display_rank") != null) completeness += 40.0;
        if (Boolean.FALSE.equals(ieltsEvidence.get("ielts_min_missing"))) completeness += 30.0;
        Number coverageRatioNum = (Number) ranking.get("coverage_ratio");
        double coverageRatio = coverageRatioNum == null ? 0.0 : coverageRatioNum.doubleValue();
        completeness += 30.0 * Math.max(0.0, Math.min(1.0, coverageRatio));

        double agreement = switch (sourceCount) {
            case 0 -> 45.0;
            case 1 -> 68.0;
            default -> {
                // Multi-source: simplified agreement score
                yield 85.0;
            }
        };

        double confidenceScore = Math.round(
                ((0.65 * completeness) + (0.35 * agreement)) * 10000.0
        ) / 10000.0;
        confidenceScore = Math.max(0.0, Math.min(100.0, confidenceScore));

        String label = confidenceScore >= 80.0 ? "high" : confidenceScore >= 60.0 ? "medium" : "low";
        String reason = buildConfidenceReason(label, sourceCount, ieltsEvidence);

        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("confidence_score", confidenceScore);
        evidence.put("confidence_label", label);
        evidence.put("confidence_reason", reason);
        evidence.put("completeness_component", Math.round(completeness * 100.0) / 100.0);
        evidence.put("source_agreement_component", agreement);
        return evidence;
    }

    private String buildConfidenceReason(String label, int sourceCount, Map<String, Object> ieltsEvidence) {
        List<String> parts = new ArrayList<>();
        switch (sourceCount) {
            case 0 -> parts.add("no ranking source data");
            case 1 -> parts.add("single-source ranking (QS only)");
            default -> parts.add("multi-source ranking data");
        }
        if (Boolean.TRUE.equals(ieltsEvidence.get("ielts_min_missing"))) {
            parts.add("IELTS requirement missing");
        }
        return "Confidence is " + label + " because: " + String.join("; ", parts) + ".";
    }

    // ── Private: subject ─────────────────────────────────────────────────────

    private Map<String, Object> fetchSubjectEvidence(long canonicalUniversityId, String subjectKey) {
        List<Map<String, Object>> rows = jdbcTemplate.queryForList("""
                SELECT DISTINCT ON (srr.canonical_university_id)
                    subj.subject_key,
                    subj.display_name AS subject_name,
                    srr.ranking_year,
                    srr.rank_position,
                    srr.rank_display,
                    srr.score,
                    rs.source_code
                FROM warehouse.subject_ranking_record srr
                JOIN warehouse.ranking_subject subj
                  ON subj.subject_id = srr.subject_id
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = srr.ranking_source_id
                WHERE srr.canonical_university_id = ?
                  AND subj.subject_key = ?
                  AND rs.source_code = 'QS'
                ORDER BY srr.canonical_university_id, srr.ranking_year DESC, srr.rank_position ASC NULLS LAST
                """, canonicalUniversityId, subjectKey);

        Map<String, Object> evidence = new LinkedHashMap<>();
        evidence.put("subject_key", subjectKey);

        if (rows.isEmpty()) {
            evidence.put("has_data", false);
            evidence.put("subject_name", subjectKey);
            evidence.put("ranking_year", null);
            evidence.put("rank_position", null);
            evidence.put("rank_display", null);
            evidence.put("score", null);
            evidence.put("source_code", "QS");
            evidence.put("reason", "No " + subjectKey + " subject ranking row found; neutral fallback applies.");
        } else {
            Map<String, Object> row = rows.get(0);
            evidence.put("has_data", true);
            evidence.put("subject_name", row.get("subject_name"));
            evidence.put("ranking_year", row.get("ranking_year"));
            evidence.put("rank_position", row.get("rank_position"));
            evidence.put("rank_display", row.get("rank_display"));
            evidence.put("score", row.get("score"));
            evidence.put("source_code", row.get("source_code"));
            Integer rankPos = (Integer) row.get("rank_position");
            String displayRank = row.get("rank_display") != null && !row.get("rank_display").toString().isBlank()
                    ? row.get("rank_display").toString()
                    : (rankPos != null ? "#" + rankPos : "unranked");
            evidence.put("reason", row.get("subject_name") + " rank " + displayRank + " (QS source).");
        }
        return evidence;
    }
}
