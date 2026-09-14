package clawer.service;

import clawer.domain.ranking.RankedPosition;
import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.dto.RankingTrustDTO;
import clawer.model.RecommendationExplain;
import clawer.model.RecommendationExplainDimensions;
import clawer.model.RecommendationGroupResponse;
import clawer.model.RecommendationResult;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

@Service
public class RecommendationService {
    private static final Logger LOGGER = LoggerFactory.getLogger(RecommendationService.class);

    private static final List<String> SOURCE_ORDER = List.of("QS", "THE", "ARWU");
    private static final String DEFAULT_RISK_PROFILE = "balanced";
    private static final String DEFAULT_COUNTRY_POLICY = "hard_filter";
    private static final String CONFIG_VERSION = "decision_config_v1";
    private static final String SCORING_VERSION = "hybrid_scoring_v3";
    private static final String DECISION_POLICY_VERSION = "decision_policy_v2";
    private static final String EXPLANATION_VERSION = "explanation_templates_v2";

    private static final double V1_RANKING_WEIGHT = 0.75;
    private static final double V1_IELTS_FIT_WEIGHT = 0.20;
    private static final double V1_COMPLETENESS_WEIGHT = 0.05;
    private static final double V2_RANKING_WEIGHT = 0.45;
    private static final double V2_IELTS_FIT_WEIGHT = 0.20;
    private static final double V2_CONFIDENCE_WEIGHT = 0.20;
    private static final double V2_RISK_ALIGNMENT_WEIGHT = 0.15;
    private static final double V3_RANKING_WEIGHT = 0.50;
    private static final double V3_IELTS_FIT_WEIGHT = 0.20;
    private static final double V3_CONFIDENCE_WEIGHT = 0.20;
    private static final double V3_COUNTRY_MATCH_WEIGHT = 0.10;
    private static final double V3_RANKING_MIN_WEIGHT = 0.40;
    private static final int RANKING_RANK_CAP = 500;
    private static final double RANKING_TOP10_FLOOR = 90.0;
    private static final double RANKING_TOP50_FLOOR = 55.0;
    private static final double RANKING_TAIL_DECAY = 0.01;
    private static final double IELTS_OPTIMAL_BAND = 0.5;
    private static final double IELTS_SATURATION_GAP = 1.0;
    private static final double IELTS_SATURATION_SCORE = 94.0;
    private static final double REACH_RATIO_UPPER = 0.7;
    private static final double TARGET_RATIO_UPPER = 1.35;
    private static final double CONSERVATIVE_REACH_ADJUSTMENT = -0.1;
    private static final double CONSERVATIVE_TARGET_ADJUSTMENT = -0.15;
    private static final double AGGRESSIVE_REACH_ADJUSTMENT = 0.12;
    private static final double AGGRESSIVE_TARGET_ADJUSTMENT = 0.2;
    private static final double IELTS_SHORTFALL_RISK_SHIFT_THRESHOLD = 0.25;
    private static final double LOW_CONFIDENCE_THRESHOLD = 60.0;
    private static final double VERY_LOW_CONFIDENCE_THRESHOLD = 45.0;
    private static final double MISSING_SOURCE_PENALTY = 12.0;
    private static final double COMPLETENESS_CONFIDENCE_WEIGHT = 0.65;
    private static final double SOURCE_AGREEMENT_WEIGHT = 0.35;
    private static final double CONSERVATIVE_SAFETY_BOOST = 1.5;
    private static final double CONSERVATIVE_TARGET_BOOST = 0.75;
    private static final double CONSERVATIVE_REACH_PENALTY = -2.0;
    private static final double BALANCED_REACH_BOOST = 0.5;
    private static final double BALANCED_TARGET_BOOST = 1.0;
    private static final double BALANCED_SAFETY_BOOST = 0.5;
    private static final double AGGRESSIVE_REACH_BOOST = 2.0;
    private static final double AGGRESSIVE_TARGET_BOOST = 0.75;
    private static final double AGGRESSIVE_SAFETY_PENALTY = -1.0;
    private static final int MAX_LIMIT = 50;
    private final ScopedRankingReadAdapter scopedRankingReadAdapter;
    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public RecommendationService(ScopedRankingReadAdapter scopedRankingReadAdapter, JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.scopedRankingReadAdapter = scopedRankingReadAdapter;
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    /**
     * CAVEAT_ADMISSION_DATA_STALE for the universities this response returns,
     * naming the oldest date behind any of their requirements. Empty when none of
     * them has an admission row. The per-university IELTS caveat is not repeated
     * here -- it names one university -- and travels with
     * {@code /recommendations/explain} instead.
     */
    private List<String> admissionCaveats(Map<String, List<RecommendationResult>> grouped) {
        List<Long> ids = grouped.values().stream()
                .flatMap(List::stream)
                .map(RecommendationResult::getCanonicalUniversityId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .toList();
        if (ids.isEmpty()) {
            return List.of();
        }
        String stale = jdbcTemplate.query(
                """
                SELECT bool_and(fetch_dates_recorded) AS fetch_dates_recorded,
                       MIN(oldest_fetched_on) AS oldest_fetched_on,
                       MIN(oldest_extracted_on) AS oldest_extracted_on
                FROM warehouse.v_admission_requirement_summary
                WHERE canonical_university_id = ANY(?::bigint[])
                """,
                rs -> rs.next()
                        ? AnalyticsService.admissionStaleCaveat(
                                rs.getBoolean("fetch_dates_recorded"),
                                rs.getObject("oldest_fetched_on", java.time.LocalDate.class),
                                rs.getObject("oldest_extracted_on", java.time.LocalDate.class))
                        : null,
                ids.stream().map(String::valueOf).collect(java.util.stream.Collectors.joining(",", "{", "}"))
        );
        return stale == null ? List.of() : List.of(stale);
    }

    public List<RecommendationResult> getRecommendations(
            String country,
            String scope,
            String region,
            String shortlist,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource,
            Integer rankingYear,
            Integer limit
    ) {
        RankingContext scopeContext = RankingContext.fromQuery(scope, region);
        List<Candidate> candidates = fetchCandidates(country, rankingYear, scopeContext);
        List<RecommendationResult> results = new ArrayList<>();
        for (Candidate candidate : candidates) {
            if (!passesV1Constraints(candidate, country, ieltsScore, targetRank, preferredRankingSource)) {
                continue;
            }
            RecommendationResult result = scoreCandidateV1(candidate, country, ieltsScore, targetRank, preferredRankingSource, scopeContext);
            if (result != null) {
                results.add(result);
            }
        }

        results.sort(
                Comparator.comparing(RecommendationResult::getMatchingScore, Comparator.nullsLast(Double::compareTo)).reversed()
                        .thenComparing(RecommendationResult::getAggregatedRank, Comparator.nullsLast(Integer::compareTo))
                        .thenComparing(RecommendationResult::getCanonicalUniversityId)
        );

        int safeLimit = safeLimit(limit, 10);
        return results.size() > safeLimit ? results.subList(0, safeLimit) : results;
    }

    public RecommendationGroupResponse getRecommendationsV2(
            String country,
            String scope,
            String region,
            String shortlist,
            Double ieltsScore,
            Integer targetRank,
            String riskProfile,
            String preferredRankingSource,
            Integer rankingYear,
            Integer limit
    ) {
        if (targetRank == null || targetRank <= 0) {
            throw new IllegalArgumentException("targetRank is required for recommendation v2.");
        }

        RankingContext scopeContext = RankingContext.fromQuery(scope, region);
        List<Candidate> candidates = fetchCandidates(country, rankingYear, scopeContext);
        Map<String, List<RecommendationResult>> grouped = new LinkedHashMap<>();
        grouped.put("reach", new ArrayList<>());
        grouped.put("target", new ArrayList<>());
        grouped.put("safety", new ArrayList<>());

        int candidateCount = 0;
        for (Candidate candidate : candidates) {
            if (!passesV2Constraints(candidate, country, preferredRankingSource)) {
                continue;
            }
            RecommendationResult result = scoreCandidateV2(candidate, country, ieltsScore, targetRank, riskProfile, preferredRankingSource, scopeContext);
            if (result == null || result.getCategory() == null) {
                continue;
            }
            candidateCount++;
            grouped.get(result.getCategory()).add(result);
        }

        Comparator<RecommendationResult> comparator = Comparator
                .comparing(RecommendationResult::getMatchingScore, Comparator.nullsLast(Double::compareTo)).reversed()
                .thenComparing(RecommendationResult::getAggregatedRank, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(RecommendationResult::getCanonicalUniversityId);
        int safeLimit = safeLimit(limit, 5);
        for (List<RecommendationResult> rows : grouped.values()) {
            rows.sort(comparator);
            List<RecommendationResult> deduped = dedupeRecommendationResults(rows);
            rows.clear();
            rows.addAll(deduped);
            if (rows.size() > safeLimit) {
                rows.subList(safeLimit, rows.size()).clear();
            }
        }

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("target_rank", targetRank);
        metadata.put("scope", scopeContext.apiScope());
        metadata.put("region", scopeContext.region());
        metadata.put("shortlist_count", shortlistCount(shortlist));
        metadata.put("risk_profile", normalizeRiskProfile(riskProfile));
        metadata.put("country", country);
        metadata.put("ielts_score", ieltsScore);
        metadata.put("candidate_count", candidateCount);
        metadata.put("counts", Map.of(
                "reach", grouped.get("reach").size(),
                "target", grouped.get("target").size(),
                "safety", grouped.get("safety").size()
        ));
        metadata.put("thresholds", Map.of(
                "balanced", Map.of("reach_upper", REACH_RATIO_UPPER, "target_upper", TARGET_RATIO_UPPER),
                "conservative", Map.of(
                        "reach_upper", REACH_RATIO_UPPER + CONSERVATIVE_REACH_ADJUSTMENT,
                        "target_upper", TARGET_RATIO_UPPER + CONSERVATIVE_TARGET_ADJUSTMENT
                ),
                "aggressive", Map.of(
                        "reach_upper", REACH_RATIO_UPPER + AGGRESSIVE_REACH_ADJUSTMENT,
                        "target_upper", TARGET_RATIO_UPPER + AGGRESSIVE_TARGET_ADJUSTMENT
                )
        ));
        metadata.put("admission_caveats", admissionCaveats(grouped));

        return new RecommendationGroupResponse(
                grouped.get("reach"),
                grouped.get("target"),
                grouped.get("safety"),
                metadata
        );
    }

    public RecommendationGroupResponse getRecommendationsV3(
            String country,
            String scope,
            String region,
            String shortlist,
            String countryPolicy,
            Double ieltsScore,
            Integer targetRank,
            String riskProfile,
            String preferenceWeights,
            String preferredRankingSource,
            String subjectKey,
            Integer rankingYear,
            Integer limit
    ) {
        if (targetRank == null || targetRank <= 0) {
            throw new IllegalArgumentException("targetRank is required for recommendation v3.");
        }

        RankingContext scopeContext = RankingContext.fromQuery(scope, region);
        String resolvedCountryPolicy = normalizeCountryPolicy(countryPolicy);
        List<Candidate> candidates = fetchCandidates(
                "hard_filter".equals(resolvedCountryPolicy) ? country : null,
                rankingYear,
                scopeContext
        );
        Map<String, Double> resolvedWeights = resolvePreferenceWeights(preferenceWeights);
        String normalizedSubjectKey = normalizeSubjectKey(subjectKey);
        SubjectScoringContext subjectContext = loadSubjectScoringContext(normalizedSubjectKey, rankingYear);
        Map<String, List<RecommendationResult>> grouped = new LinkedHashMap<>();
        grouped.put("reach", new ArrayList<>());
        grouped.put("target", new ArrayList<>());
        grouped.put("safety", new ArrayList<>());

        Map<Long, PoolContext> poolContexts = buildPoolContexts(candidates, targetRank, scopeContext);
        int candidateCount = 0;
        for (Candidate candidate : candidates) {
            if (!passesV3Constraints(candidate, country, resolvedCountryPolicy, preferredRankingSource)) {
                continue;
            }
            RecommendationResult result = scoreCandidateV3(
                    candidate,
                    country,
                    resolvedCountryPolicy,
                    ieltsScore,
                    targetRank,
                    riskProfile,
                    resolvedWeights,
                    preferredRankingSource,
                    subjectContext,
                    poolContexts.get(candidate.canonicalUniversityId),
                    scopeContext
            );
            if (result == null || result.getCategory() == null) {
                continue;
            }
            candidateCount++;
            grouped.get(result.getCategory()).add(result);
        }

        Comparator<RecommendationResult> comparator = Comparator
                .comparing(RecommendationResult::getMatchingScore, Comparator.nullsLast(Double::compareTo)).reversed()
                .thenComparing(RecommendationResult::getAggregatedRank, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(RecommendationResult::getCanonicalUniversityId);
        int safeLimit = safeLimit(limit, 5);
        for (List<RecommendationResult> rows : grouped.values()) {
            rows.sort(comparator);
            List<RecommendationResult> deduped = dedupeRecommendationResults(rows);
            rows.clear();
            rows.addAll(deduped);
            if (rows.size() > safeLimit) {
                rows.subList(safeLimit, rows.size()).clear();
            }
        }

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("version", "v3");
        metadata.put("scope", scopeContext.apiScope());
        metadata.put("region", scopeContext.region());
        metadata.put("shortlist_count", shortlistCount(shortlist));
        metadata.put("config_version", CONFIG_VERSION);
        metadata.put("scoring_version", SCORING_VERSION);
        metadata.put("decision_policy_version", DECISION_POLICY_VERSION);
        metadata.put("explanation_version", EXPLANATION_VERSION);
        metadata.put("target_rank", targetRank);
        metadata.put("risk_profile", normalizeRiskProfile(riskProfile));
        metadata.put("country", country);
        String metadataCountryPolicy = country == null || country.isBlank() ? "none" : resolvedCountryPolicy;
        metadata.put("country_policy", metadataCountryPolicy);
        metadata.put("country_preference_mode", metadataCountryPolicy);
        metadata.put("ielts_score", ieltsScore);
        metadata.put("candidate_count", candidateCount);
        metadata.put("preference_weights", resolvedWeights);
        metadata.put("subject", normalizedSubjectKey);
        metadata.put("subject_scoring", Map.of(
                "enabled", normalizedSubjectKey != null,
                "subject_key", normalizedSubjectKey == null ? "" : normalizedSubjectKey,
                "rows_loaded", subjectContext.records().size(),
                "neutral_fallback", "No subject ranking row produces subjectSignal=0.5 and adjustment=0."
        ));
        metadata.put("counts", Map.of(
                "reach", grouped.get("reach").size(),
                "target", grouped.get("target").size(),
                "safety", grouped.get("safety").size()
        ));
        metadata.put("thresholds", Map.of(
                "balanced", Map.of("reach_upper", REACH_RATIO_UPPER, "target_upper", TARGET_RATIO_UPPER),
                "conservative", Map.of(
                        "reach_upper", REACH_RATIO_UPPER + CONSERVATIVE_REACH_ADJUSTMENT,
                        "target_upper", TARGET_RATIO_UPPER + CONSERVATIVE_TARGET_ADJUSTMENT
                ),
                "aggressive", Map.of(
                        "reach_upper", REACH_RATIO_UPPER + AGGRESSIVE_REACH_ADJUSTMENT,
                        "target_upper", TARGET_RATIO_UPPER + AGGRESSIVE_TARGET_ADJUSTMENT
                )
        ));
        metadata.put("admission_caveats", admissionCaveats(grouped));
        if (grouped.get("reach").isEmpty() && grouped.get("target").isEmpty() && grouped.get("safety").isEmpty()) {
            metadata.put(
                    "no_results_reason",
                    scopeContext.isRegion()
                            ? "No universities produced a valid decision result within the selected region."
                            : "No universities produced a valid decision result for the supplied target rank."
            );
        }

        LOGGER.info(
                "recommendation_v3_summary targetRank={} riskProfile={} country={} countryPolicy={} ielts={} before={} reach={} target={} safety={} configVersion={} scoringVersion={}",
                targetRank,
                normalizeRiskProfile(riskProfile),
                country,
                resolvedCountryPolicy,
                ieltsScore,
                candidates.size(),
                grouped.get("reach").size(),
                grouped.get("target").size(),
                grouped.get("safety").size(),
                CONFIG_VERSION,
                SCORING_VERSION
        );

        return new RecommendationGroupResponse(
                grouped.get("reach"),
                grouped.get("target"),
                grouped.get("safety"),
                metadata
        );
    }

    private List<Candidate> fetchCandidates(String country, Integer rankingYear, RankingContext scopeContext) {
        List<Candidate> candidates = scopedRankingReadAdapter.findRecommendationCandidates(scopeContext, rankingYear, country)
                .stream()
                .map(this::toCandidate)
                .toList();
        return dedupeCandidates(candidates, scopeContext);
    }

    private SubjectScoringContext loadSubjectScoringContext(String subjectKey, Integer rankingYear) {
        if (subjectKey == null) {
            return SubjectScoringContext.disabled();
        }

        String sql = """
                WITH filtered AS (
                    SELECT
                        srr.canonical_university_id,
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
                    WHERE subj.subject_key = ?
                      AND rs.source_code = 'QS'
                      AND (? IS NULL OR srr.ranking_year = ?)
                )
                SELECT DISTINCT ON (canonical_university_id)
                    canonical_university_id,
                    subject_key,
                    subject_name,
                    ranking_year,
                    rank_position,
                    rank_display,
                    score,
                    source_code
                FROM filtered
                ORDER BY canonical_university_id, ranking_year DESC, rank_position ASC NULLS LAST
                """;

        Map<Long, SubjectRankingSignalRecord> records = new LinkedHashMap<>();
        jdbcTemplate.query(
                sql,
                rs -> {
                    records.put(
                            rs.getLong("canonical_university_id"),
                            new SubjectRankingSignalRecord(
                                    rs.getString("subject_key"),
                                    rs.getString("subject_name"),
                                    (Integer) rs.getObject("ranking_year"),
                                    (Integer) rs.getObject("rank_position"),
                                    rs.getString("rank_display"),
                                    rs.getObject("score") == null ? null : ((Number) rs.getObject("score")).doubleValue(),
                                    rs.getString("source_code")
                            )
                    );
                },
                subjectKey,
                rankingYear,
                rankingYear
        );
        String subjectName = records.values().stream()
                .findFirst()
                .map(SubjectRankingSignalRecord::subjectName)
                .orElse(subjectKey);
        return new SubjectScoringContext(subjectKey, subjectName, records);
    }

    private SubjectSignal subjectSignalForCandidate(SubjectScoringContext context, Long canonicalUniversityId) {
        if (!context.enabled()) {
            return SubjectSignal.disabled();
        }
        SubjectRankingSignalRecord record = context.records().get(canonicalUniversityId);
        if (record == null) {
            return new SubjectSignal(
                    context.subjectKey(),
                    context.subjectName(),
                    null,
                    null,
                    null,
                    "QS",
                    50.0,
                    0.0,
                    false,
                    "No " + context.subjectName() + " subject ranking row found; neutral fallback applied."
            );
        }
        double signalRatio = subjectSignalRatio(record.rankPosition());
        double signalScore = signalRatio * 100.0;
        double adjustment = (signalRatio - 0.5) * 10.0;
        String displayRank = record.rankDisplay() == null || record.rankDisplay().isBlank()
                ? (record.rankPosition() == null ? "unranked" : "#" + record.rankPosition())
                : record.rankDisplay();
        return new SubjectSignal(
                record.subjectKey(),
                record.subjectName(),
                record.rankPosition(),
                displayRank,
                record.score(),
                record.sourceCode(),
                signalScore,
                adjustment,
                true,
                record.subjectName() + " rank " + displayRank
                        + " contributes " + (adjustment >= 0 ? "+" : "")
                        + String.format(Locale.ROOT, "%.1f", adjustment)
                        + " to the final fit score."
        );
    }

    private double subjectSignalRatio(Integer rankPosition) {
        if (rankPosition == null || rankPosition <= 0) {
            return 0.5;
        }
        return Math.max(0.0, Math.min(1.0, 1.0 - (rankPosition - 1) / 499.0));
    }

    private Map<String, Object> subjectFitPayload(SubjectSignal signal) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("subjectKey", signal.subjectKey());
        payload.put("subjectName", signal.subjectName());
        payload.put("rankPosition", signal.rankPosition());
        payload.put("rankDisplay", signal.rankDisplay());
        payload.put("score", signal.score());
        payload.put("sourceCode", signal.sourceCode());
        payload.put("signalScore", round(signal.signalScore()));
        payload.put("adjustment", round(signal.adjustment()));
        payload.put("hasData", signal.hasData());
        payload.put("reason", signal.reason());
        return payload;
    }

    private void appendSubjectExplain(RecommendationExplain explain, SubjectSignal signal) {
        if (explain == null) {
            return;
        }
        explain.setFitScore(clampScore((explain.getFitScore() == null ? 0.0 : explain.getFitScore()) + signal.adjustment()));
        if (signal.hasData()) {
            List<String> reasons = new ArrayList<>(explain.getReasons() == null ? List.of() : explain.getReasons());
            reasons.add(signal.reason());
            explain.setReasons(reasons);
        } else {
            List<String> warnings = new ArrayList<>(explain.getWarnings() == null ? List.of() : explain.getWarnings());
            warnings.add(signal.reason());
            explain.setWarnings(warnings);
        }
    }

    private Candidate toCandidate(ScopedRankedUniversity row) {
        Candidate candidate = new Candidate();
        candidate.canonicalUniversityId = row.getCanonicalUniversityId();
        candidate.universityName = row.getUniversityName();
        candidate.country = row.getCountry();
        candidate.rankingYear = row.getRankingYear();
        candidate.globalRank = row.getGlobalRank();
        candidate.scopeRank = row.getScopeRank();
        candidate.aggregatedRank = candidate.globalRank;
        candidate.aggregatedScore = row.getCompositeScore();
        candidate.coverageRatio = row.getCoverageRatio() == null ? 0.0 : row.getCoverageRatio();
        candidate.ieltsMin = row.getIeltsMin();
        candidate.toeflMin = row.getToeflMin();
        candidate.duolingoMin = row.getDuolingoMin();
        candidate.gpaMin = row.getGpaMin();
        candidate.applicationDeadline = row.getApplicationDeadline();
        candidate.aggregationMethodVersion = row.getAggregationMethodVersion();
        candidate.sourceRanks = row.getSourceRanks();
        return candidate;
    }

    private boolean passesV1Constraints(
            Candidate candidate,
            String country,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource
    ) {
        if (country != null && !country.isBlank() && (candidate.country == null || !candidate.country.equalsIgnoreCase(country.trim()))) {
            return false;
        }
        EffectiveRank effectiveRank = chooseEffectiveRank(candidate, preferredRankingSource);
        if (targetRank != null && (effectiveRank.rank == null || effectiveRank.rank > targetRank)) {
            return false;
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

    private boolean passesV2Constraints(Candidate candidate, String country, String preferredRankingSource) {
        if (country != null && !country.isBlank() && (candidate.country == null || !candidate.country.equalsIgnoreCase(country.trim()))) {
            return false;
        }
        return candidate.globalRank != null;
    }

    private boolean passesV3Constraints(
            Candidate candidate,
            String country,
            String countryPolicy,
            String preferredRankingSource
    ) {
        if ("hard_filter".equals(normalizeCountryPolicy(countryPolicy))
                && country != null
                && !country.isBlank()
                && (candidate.country == null || !candidate.country.equalsIgnoreCase(country.trim()))) {
            return false;
        }
        return candidate.globalRank != null;
    }

    private RecommendationResult scoreCandidateV1(
            Candidate candidate,
            String country,
            Double ieltsScore,
            Integer targetRank,
            String preferredRankingSource,
            RankingContext scopeContext
    ) {
        EffectiveRank effectiveRank = chooseEffectiveRank(candidate, preferredRankingSource);
        Double rankingScore = rankingScore(effectiveRank.rank, targetRank);
        Double ieltsFitScore = ieltsFitScore(candidate.ieltsMin, ieltsScore);
        Double completenessScore = completenessScore(candidate);

        Map<String, Double> weightsUsed = new LinkedHashMap<>();
        if (rankingScore != null) {
            weightsUsed.put("ranking", V1_RANKING_WEIGHT);
        }
        if (ieltsFitScore != null) {
            weightsUsed.put("ielts_fit", V1_IELTS_FIT_WEIGHT);
        }
        if (completenessScore != null) {
            weightsUsed.put("completeness", V1_COMPLETENESS_WEIGHT);
        }
        if (weightsUsed.isEmpty()) {
            return null;
        }

        Map<String, Double> scoreMap = Map.of(
                "ranking", rankingScore == null ? 0.0 : rankingScore,
                "ielts_fit", ieltsFitScore == null ? 0.0 : ieltsFitScore,
                "completeness", completenessScore == null ? 0.0 : completenessScore
        );
        double finalScore = weightedAverage(weightsUsed, scoreMap);
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

        Map<String, Object> scoreBreakdown = new LinkedHashMap<>();
        scoreBreakdown.put("ranking_score", rankingScore);
        scoreBreakdown.put("ielts_fit_score", ieltsFitScore);
        scoreBreakdown.put("completeness_score", completenessScore);
        scoreBreakdown.put("weights_used", weightsUsed);
        scoreBreakdown.put("contributions", componentContributions(weightsUsed, scoreMap));
        scoreBreakdown.put("effective_rank_used", effectiveRank.rank);
        scoreBreakdown.put("effective_rank_source", effectiveRank.source);

        RecommendationResult result = new RecommendationResult(
                candidate.canonicalUniversityId,
                candidate.universityName,
                candidate.country,
                displayRank(candidate, scopeContext),
                candidate.ieltsMin,
                round(finalScore),
                null,
                null,
                null,
                null,
                SCORING_VERSION,
                DECISION_POLICY_VERSION,
                EXPLANATION_VERSION,
                buildExplanationV1(candidate, ieltsScore, rankingScore, ieltsFitScore, completenessScore, finalScore, effectiveRank),
                candidate.aggregationMethodVersion,
                scoreBreakdown,
                rulesPassed
        );
        applyScopeContext(result, candidate, scopeContext);
        applyAdmissionRequirements(result, candidate);
        return result;
    }

    private RecommendationResult scoreCandidateV2(
            Candidate candidate,
            String country,
            Double ieltsScore,
            Integer targetRank,
            String riskProfile,
            String preferredRankingSource,
            RankingContext scopeContext
    ) {
        Integer decisionRank = decisionRank(candidate, scopeContext);
        if (decisionRank == null) {
            return null;
        }

        Double rankingScore = rankingScoreForContext(candidate, targetRank, scopeContext);
        Double ieltsFitScore = ieltsFitScoreV2(candidate.ieltsMin, ieltsScore);
        Double confidenceScore = confidenceScore(candidate, targetRank, ieltsScore);
        CategoryDecision categoryDecision = classifyCategory(candidate, decisionRank, targetRank, ieltsScore, riskProfile, confidenceScore, scopeContext);
        Double riskAlignmentScore = riskAlignmentScore(categoryDecision.category, riskProfile);
        Double completenessScore = completenessScore(candidate);
        Double ieltsMargin = ieltsMargin(candidate.ieltsMin, ieltsScore);
        String confidenceLabel = confidenceLabel(confidenceScore);

        Map<String, Double> weightsUsed = new LinkedHashMap<>();
        weightsUsed.put("ranking", V2_RANKING_WEIGHT);
        weightsUsed.put("ielts_fit", V2_IELTS_FIT_WEIGHT);
        weightsUsed.put("confidence", V2_CONFIDENCE_WEIGHT);
        weightsUsed.put("risk_alignment", V2_RISK_ALIGNMENT_WEIGHT);

        Map<String, Double> scoreMap = new LinkedHashMap<>();
        scoreMap.put("ranking", rankingScore);
        scoreMap.put("ielts_fit", ieltsFitScore);
        scoreMap.put("confidence", confidenceScore);
        scoreMap.put("risk_alignment", riskAlignmentScore);
        double finalScore = weightedAverage(weightsUsed, scoreMap);

        Map<String, Object> scoreBreakdown = new LinkedHashMap<>();
        scoreBreakdown.put("ranking_score", rankingScore);
        scoreBreakdown.put("ielts_fit_score", ieltsFitScore);
        scoreBreakdown.put("completeness_score", completenessScore);
        scoreBreakdown.put("confidence_score", confidenceScore);
        scoreBreakdown.put("risk_alignment_score", riskAlignmentScore);
        scoreBreakdown.put("weights_used", weightsUsed);
        scoreBreakdown.put("contributions", componentContributions(weightsUsed, scoreMap));
        scoreBreakdown.put("effective_rank_used", decisionRank);
        scoreBreakdown.put("effective_rank_source", scopeContext.isRegion() ? "REGION_SCOPE" : "AGGREGATED");
        scoreBreakdown.put("global_rank", candidate.globalRank);
        scoreBreakdown.put("scope_rank", candidate.scopeRank);
        scoreBreakdown.put("category", categoryDecision.category);
        scoreBreakdown.put("category_reason", categoryDecision.reason);
        scoreBreakdown.put("ielts_margin", ieltsMargin);
        scoreBreakdown.put("confidence_label", confidenceLabel);

        List<String> rulesPassed = new ArrayList<>();
        rulesPassed.add("category=" + categoryDecision.category);
        rulesPassed.add("risk_profile=" + normalizeRiskProfile(riskProfile));
        rulesPassed.add("confidence=" + confidenceLabel);
        if (country != null && !country.isBlank()) {
            rulesPassed.add("country=" + country);
        }
        if (ieltsMargin != null) {
            rulesPassed.add("ielts_margin=" + formatNumber(ieltsMargin));
        }

        RecommendationResult result = new RecommendationResult(
                candidate.canonicalUniversityId,
                candidate.universityName,
                candidate.country,
                displayRank(candidate, scopeContext),
                candidate.ieltsMin,
                round(finalScore),
                categoryDecision.category,
                null,
                round(confidenceScore),
                "Confidence is " + confidenceLabel + " based on ranking-source agreement and data completeness.",
                SCORING_VERSION,
                DECISION_POLICY_VERSION,
                EXPLANATION_VERSION,
                buildExplanationV2(candidate, ieltsScore, rankingScore, confidenceLabel, ieltsMargin, finalScore, categoryDecision.reason, scopeContext),
                candidate.aggregationMethodVersion,
                scoreBreakdown,
                rulesPassed
        );
        result.setRecommendationExplain(
                buildRecommendationExplain(
                        candidate,
                        targetRank,
                        riskProfile,
                        rankingScore,
                        riskAlignmentScore(categoryDecision.category, riskProfile),
                        ieltsFitScore,
                        RankingTrustLayer.buildTrustScore(candidate.sourceRanks),
                        ieltsScore,
                        scopeContext
                )
        );
        applyScopeContext(result, candidate, scopeContext);
        applyAdmissionRequirements(result, candidate);
        return result;
    }

    private RecommendationResult scoreCandidateV3(
            Candidate candidate,
            String country,
            String countryPolicy,
            Double ieltsScore,
            Integer targetRank,
            String riskProfile,
            Map<String, Double> resolvedWeights,
            String preferredRankingSource,
            SubjectScoringContext subjectContext,
            PoolContext poolContext,
            RankingContext scopeContext
    ) {
        Integer decisionRank = decisionRank(candidate, scopeContext);
        if (decisionRank == null) {
            return null;
        }

        Double rankingScore = rankingScoreForContext(candidate, targetRank, scopeContext);
        Double ieltsFitScore = ieltsFitScoreV2(candidate.ieltsMin, ieltsScore);
        Double completenessScore = completenessScore(candidate);
        Double confidenceScore = confidenceScore(candidate, targetRank, ieltsScore);
        CategoryDecision categoryDecision = classifyCategory(candidate, decisionRank, targetRank, ieltsScore, riskProfile, confidenceScore, scopeContext);
        if (poolContext != null && poolContext.elitePool()) {
            categoryDecision = classifyElitePoolCategory(candidate, decisionRank, targetRank, ieltsScore, riskProfile, poolContext, scopeContext);
        }
        Double ieltsMargin = ieltsMargin(candidate.ieltsMin, ieltsScore);
        String confidenceLabel = confidenceLabel(confidenceScore);
        Double countryMatchScore = countryMatchScore(candidate.country, country);
        Double riskAdjustment = riskAdjustment(categoryDecision.category, riskProfile);
        String preferenceAlignment = preferenceAlignment(countryMatchScore, riskAdjustment, country);

        Map<String, Double> scoreMap = new LinkedHashMap<>();
        scoreMap.put("ranking", rankingScore);
        scoreMap.put("ielts", ieltsFitScore);
        scoreMap.put("confidence", confidenceScore);
        scoreMap.put("country_match", countryMatchScore);
        double baseScore = weightedAverage(resolvedWeights, scoreMap);
        SubjectSignal subjectSignal = subjectSignalForCandidate(subjectContext, candidate.canonicalUniversityId);
        double preSubjectScore = clampScore(baseScore + riskAdjustment);
        double finalScore = clampScore(preSubjectScore + subjectSignal.adjustment());

        Map<String, Object> scoreBreakdown = new LinkedHashMap<>();
        scoreBreakdown.put("ranking_score", rankingScore);
        scoreBreakdown.put("ielts_fit_score", ieltsFitScore);
        scoreBreakdown.put("completeness_score", completenessScore);
        scoreBreakdown.put("confidence_score", confidenceScore);
        scoreBreakdown.put("country_match_score", countryMatchScore);
        scoreBreakdown.put("weights_used", resolvedWeights);
        scoreBreakdown.put("contributions", componentContributions(resolvedWeights, scoreMap));
        scoreBreakdown.put("effective_rank_used", decisionRank);
        scoreBreakdown.put("effective_rank_source", scopeContext.isRegion() ? "REGION_SCOPE" : "AGGREGATED");
        scoreBreakdown.put("global_rank", candidate.globalRank);
        scoreBreakdown.put("scope_rank", candidate.scopeRank);
        scoreBreakdown.put("category", categoryDecision.category);
        scoreBreakdown.put("category_reason", categoryDecision.reason);
        scoreBreakdown.put("ielts_margin", ieltsMargin);
        scoreBreakdown.put("confidence_label", confidenceLabel);
        scoreBreakdown.put("preference_alignment", preferenceAlignment);
        scoreBreakdown.put("recommendation_confidence", round(confidenceScore));
        scoreBreakdown.put("confidence_reason", "Confidence is " + confidenceLabel + " because data completeness and ranking-source agreement support this decision.");
        scoreBreakdown.put("scoring_version", SCORING_VERSION);
        scoreBreakdown.put("decision_policy_version", DECISION_POLICY_VERSION);
        scoreBreakdown.put("explanation_version", EXPLANATION_VERSION);
        scoreBreakdown.put("base_score", round(baseScore));
        scoreBreakdown.put("risk_adjustment", round(riskAdjustment));
        scoreBreakdown.put("pre_subject_score", round(preSubjectScore));
        scoreBreakdown.put("subject_signal_score", round(subjectSignal.signalScore()));
        scoreBreakdown.put("subject_adjustment", round(subjectSignal.adjustment()));
        scoreBreakdown.put("subject_has_data", subjectSignal.hasData());
        scoreBreakdown.put("subject_key", subjectContext.subjectKey());

        List<String> rulesPassed = new ArrayList<>();
        rulesPassed.add("version=v3");
        rulesPassed.add("category=" + categoryDecision.category);
        rulesPassed.add("risk_profile=" + normalizeRiskProfile(riskProfile));
        rulesPassed.add("preference_alignment=" + preferenceAlignment);
        if (country != null && !country.isBlank()) {
            rulesPassed.add("country_preference=" + country);
        }
        if (ieltsMargin != null) {
            rulesPassed.add("ielts_margin=" + formatNumber(ieltsMargin));
        }
        if (subjectContext.enabled()) {
            rulesPassed.add(subjectSignal.hasData() ? "subject_rank_signal" : "subject_neutral_fallback");
        }

        RecommendationResult result = new RecommendationResult(
                candidate.canonicalUniversityId,
                candidate.universityName,
                candidate.country,
                displayRank(candidate, scopeContext),
                candidate.ieltsMin,
                round(finalScore),
                categoryDecision.category,
                preferenceAlignment,
                round(confidenceScore),
                "Confidence is " + confidenceLabel + " because data completeness and ranking-source agreement support this decision.",
                SCORING_VERSION,
                DECISION_POLICY_VERSION,
                EXPLANATION_VERSION,
                buildExplanationV3(
                        country,
                        countryPolicy,
                        candidate.country,
                        categoryDecision.category,
                        decisionRank,
                        targetRank,
                        ieltsMargin,
                        confidenceLabel,
                        riskAdjustment,
                        preferenceAlignment,
                        categoryDecision.reason,
                        riskProfile,
                        candidate,
                        scopeContext
                ),
                candidate.aggregationMethodVersion,
                scoreBreakdown,
                rulesPassed
        );
        result.setRecommendationExplain(
                buildRecommendationExplain(
                        candidate,
                        targetRank,
                        riskProfile,
                        rankingScore,
                        riskAlignmentScore(categoryDecision.category, riskProfile),
                        ieltsFitScore,
                        RankingTrustLayer.buildTrustScore(candidate.sourceRanks),
                        ieltsScore,
                        scopeContext
                )
        );
        if (subjectContext.enabled()) {
            result.setSubjectFit(subjectFitPayload(subjectSignal));
            appendSubjectExplain(result.getRecommendationExplain(), subjectSignal);
            result.setExplanation(result.getExplanation() + " Subject signal: " + subjectSignal.reason());
        }
        applyScopeContext(result, candidate, scopeContext);
        applyAdmissionRequirements(result, candidate);
        return result;
    }

    private EffectiveRank chooseEffectiveRank(Candidate candidate, String preferredRankingSource) {
        String preferred = preferredRankingSource == null ? "" : preferredRankingSource.trim().toUpperCase(Locale.ROOT);
        if (!preferred.isBlank()) {
            Integer sourceRank = candidate.sourceRanks.get(preferred);
            if (sourceRank != null) {
                return new EffectiveRank(sourceRank, preferred);
            }
        }
        return new EffectiveRank(candidate.aggregatedRank, "AGGREGATED");
    }

    private RankedPosition rankedPosition(Candidate candidate, RankingContext scopeContext) {
        return RankedPosition.of(scopeContext, candidate.globalRank, candidate.scopeRank);
    }

    private Integer decisionRank(Candidate candidate, RankingContext scopeContext) {
        return rankedPosition(candidate, scopeContext).displayRank();
    }

    private Integer displayRank(Candidate candidate, RankingContext scopeContext) {
        return rankedPosition(candidate, scopeContext).compatibilityAggregatedRank();
    }

    private Double rankingScoreForContext(Candidate candidate, Integer targetRank, RankingContext scopeContext) {
        if (!scopeContext.isRegion()) {
            return rankingScore(candidate.globalRank, targetRank);
        }

        Double scopeScore = rankingScore(candidate.scopeRank, targetRank);
        Double globalReferenceScore = rankingScore(candidate.globalRank, targetRank);
        if (scopeScore == null && globalReferenceScore == null) {
            return null;
        }
        if (scopeScore == null) {
            return globalReferenceScore;
        }
        if (globalReferenceScore == null) {
            return scopeScore;
        }
        return round((0.75 * scopeScore) + (0.25 * globalReferenceScore));
    }

    private void applyScopeContext(RecommendationResult result, Candidate candidate, RankingContext scopeContext) {
        RankedPosition rankedPosition = rankedPosition(candidate, scopeContext);
        result.setScope(scopeContext.apiScope());
        result.setRegion(scopeContext.region());
        result.setGlobalRank(candidate.globalRank);
        result.setScopeRank(scopeContext.isRegion() ? rankedPosition.displayRank() : null);
        result.setAggregatedRank(rankedPosition.compatibilityAggregatedRank());
    }

    /**
     * Copies the crawled entry requirements onto the result.
     *
     * <p>Only ieltsMin participates in scoring; the rest ride along for display,
     * so a card can show the full picture without a second round trip. Any of
     * them may be null when the source published nothing, and null must not be
     * rendered as zero.
     */
    private void applyAdmissionRequirements(RecommendationResult result, Candidate candidate) {
        result.setIeltsMin(candidate.ieltsMin);
        result.setToeflMin(candidate.toeflMin);
        result.setDuolingoMin(candidate.duolingoMin);
        result.setGpaMin(candidate.gpaMin);
        result.setApplicationDeadline(candidate.applicationDeadline);
    }

    private Double rankingScore(Integer rankValue, Integer targetRank) {
        if (rankValue == null || rankValue <= 0) {
            return null;
        }
        double ratioScore = 0.0;
        if (targetRank != null && targetRank > 0) {
            double ratio = rankValue / (double) targetRank;
            ratioScore = Math.max(0.0, Math.min(100.0, 125.0 - 50.0 * ratio));
        }
        double globalScore;
        if (rankValue <= 10) {
            globalScore = 100.0 - 10.0 * Math.log10(rankValue);
        } else if (rankValue <= 50) {
            double midProgress = Math.log(rankValue / 10.0) / Math.log(5.0);
            globalScore = RANKING_TOP10_FLOOR - (RANKING_TOP10_FLOOR - RANKING_TOP50_FLOOR) * midProgress;
        } else {
            int cap = Math.max(Math.max(RANKING_RANK_CAP, targetRank == null ? 0 : targetRank), rankValue);
            globalScore = RANKING_TOP50_FLOOR * Math.exp(-RANKING_TAIL_DECAY * (rankValue - 50.0));
            if (rankValue >= cap) {
                globalScore = Math.min(globalScore, 1.0);
            }
        }
        if (targetRank == null || targetRank <= 0) {
            return round(Math.max(0.0, Math.min(100.0, globalScore)));
        }
        return round(Math.max(0.0, Math.min(100.0, (0.6 * ratioScore) + (0.4 * globalScore))));
    }

    private Double ieltsFitScore(Double requirement, Double ieltsScore) {
        if (ieltsScore == null || requirement == null) {
            return null;
        }
        if (ieltsScore + 1e-9 < requirement) {
            return null;
        }
        double gap = Math.max(0.0, ieltsScore - requirement);
        if (gap <= IELTS_OPTIMAL_BAND) {
            return 100.0;
        }
        if (gap <= IELTS_SATURATION_GAP) {
            double progress = (gap - IELTS_OPTIMAL_BAND) / (IELTS_SATURATION_GAP - IELTS_OPTIMAL_BAND);
            return round(100.0 - (100.0 - IELTS_SATURATION_SCORE) * progress);
        }
        return IELTS_SATURATION_SCORE;
    }

    private Double ieltsFitScoreV2(Double requirement, Double ieltsScore) {
        if (ieltsScore == null) {
            return 55.0;
        }
        if (requirement == null) {
            return 60.0;
        }
        if (ieltsScore + 1e-9 < requirement) {
            double deficit = requirement - ieltsScore;
            return round(Math.max(10.0, 55.0 - 35.0 * deficit));
        }
        return ieltsFitScore(requirement, ieltsScore);
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

    private Double confidenceScore(Candidate candidate, Integer targetRank, Double ieltsScore) {
        double completeness = completenessScore(candidate);
        List<Integer> sourceRanks = SOURCE_ORDER.stream()
                .map(candidate.sourceRanks::get)
                .filter(Objects::nonNull)
                .toList();
        double agreement;
        if (sourceRanks.isEmpty()) {
            agreement = 45.0;
        } else if (sourceRanks.size() == 1) {
            agreement = 68.0;
        } else {
            int spread = sourceRanks.stream().max(Integer::compareTo).orElse(0) - sourceRanks.stream().min(Integer::compareTo).orElse(0);
            int denominator = Math.max(sourceRanks.stream().max(Integer::compareTo).orElse(1), Math.max(targetRank == null ? 1 : targetRank, 1));
            double spreadRatio = spread / (double) denominator;
            agreement = Math.max(45.0, 100.0 - (spreadRatio * 100.0) - (MISSING_SOURCE_PENALTY * (SOURCE_ORDER.size() - sourceRanks.size())));
        }
        double confidence = (COMPLETENESS_CONFIDENCE_WEIGHT * completeness) + (SOURCE_AGREEMENT_WEIGHT * agreement);
        if (ieltsScore != null && candidate.ieltsMin == null) {
            confidence -= 8.0;
        }
        return round(Math.max(0.0, Math.min(100.0, confidence)));
    }

    private CategoryDecision classifyCategory(
            Candidate candidate,
            Integer effectiveRank,
            Integer targetRank,
            Double ieltsScore,
            String riskProfile,
            Double confidenceScore,
            RankingContext scopeContext
    ) {
        double ratio = effectiveRank / (double) Math.max(1, targetRank);
        Thresholds thresholds = thresholdsForRiskProfile(riskProfile);
        String category;
        if (ratio < thresholds.reachUpper) {
            category = "reach";
        } else if (ratio > thresholds.targetUpper) {
            category = "safety";
        } else {
            category = "target";
        }

        if (ieltsScore != null
                && candidate.ieltsMin != null
                && (candidate.ieltsMin - ieltsScore) >= IELTS_SHORTFALL_RISK_SHIFT_THRESHOLD) {
            category = shiftRiskier(category);
        }
        if (confidenceScore < VERY_LOW_CONFIDENCE_THRESHOLD) {
            category = shiftRiskier(category);
        } else if (confidenceScore < LOW_CONFIDENCE_THRESHOLD && "safety".equals(category)) {
            category = "target";
        }

        String reason;
        String rankLabel = scopeContext.isRegion()
                ? "regional rank #" + effectiveRank + " in " + scopeContext.region()
                : "rank #" + effectiveRank + " globally";
        if ("reach".equals(category)) {
            reason = "Reach: " + rankLabel + " is clearly above your target level of #" + targetRank + ".";
        } else if ("safety".equals(category)) {
            reason = "Safety: " + rankLabel + " is comfortably below your target level of #" + targetRank + ".";
        } else {
            reason = "Target: " + rankLabel + " is close to your target level of #" + targetRank + ".";
        }
        Double margin = ieltsMargin(candidate.ieltsMin, ieltsScore);
        if (margin != null) {
            if (margin <= -IELTS_SHORTFALL_RISK_SHIFT_THRESHOLD) {
                reason += " IELTS is short by " + formatNumber(Math.abs(margin)) + ", which makes it riskier.";
            } else if (margin < 0) {
                reason += " IELTS is slightly short by " + formatNumber(Math.abs(margin)) + ".";
            } else {
                reason += " IELTS margin is " + formatNumber(margin) + ".";
            }
        } else if (ieltsScore != null && candidate.ieltsMin == null) {
            reason += " IELTS requirement is missing, so confidence is reduced.";
        }
        if (confidenceScore < LOW_CONFIDENCE_THRESHOLD) {
            reason += " Confidence is only " + formatNumber(confidenceScore) + "/100.";
        }
        if (scopeContext.isRegion() && candidate.globalRank != null) {
            reason += " Global position: #" + candidate.globalRank + ".";
        }
        return new CategoryDecision(category, reason);
    }

    private CategoryDecision classifyElitePoolCategory(
            Candidate candidate,
            Integer effectiveRank,
            Integer targetRank,
            Double ieltsScore,
            String riskProfile,
            PoolContext poolContext,
            RankingContext scopeContext
    ) {
        String profile = normalizeRiskProfile(riskProfile);
        double reachShare;
        double targetShare;
        switch (profile) {
            case "conservative" -> {
                reachShare = 0.2;
                targetShare = 0.4;
            }
            case "aggressive" -> {
                reachShare = 0.6;
                targetShare = 0.25;
            }
            default -> {
                reachShare = 0.4;
                targetShare = 0.4;
            }
        }

        int poolSize = Math.max(1, poolContext.poolSize());
        int reachCutoff = Math.max(1, (int) Math.ceil(poolSize * reachShare));
        int targetCutoff = Math.min(poolSize, reachCutoff + Math.max(1, (int) Math.ceil(poolSize * targetShare)));

        String category;
        String reason;
        if (poolContext.position() < reachCutoff) {
            category = "reach";
            reason = "Reach: within this elite filtered pool, "
                    + (scopeContext.isRegion() ? scopeContext.region() + " rank #" : "rank #") + effectiveRank
                    + " sits in the most ambitious band for target #" + targetRank + ".";
        } else if (poolContext.position() < targetCutoff) {
            category = "target";
            reason = "Target: within this elite filtered pool, "
                    + (scopeContext.isRegion() ? scopeContext.region() + " rank #" : "rank #") + effectiveRank
                    + " sits in the balanced middle band for target #" + targetRank + ".";
        } else {
            category = "safety";
            reason = "Safety: within this elite filtered pool, "
                    + (scopeContext.isRegion() ? scopeContext.region() + " rank #" : "rank #") + effectiveRank
                    + " sits in the safer end of the shortlist for target #" + targetRank + ".";
        }

        Double margin = ieltsMargin(candidate.ieltsMin, ieltsScore);
        if (margin != null) {
            if (margin <= -IELTS_SHORTFALL_RISK_SHIFT_THRESHOLD) {
                reason += " IELTS is short by " + formatNumber(Math.abs(margin)) + ", which makes it riskier.";
            } else if (margin < 0) {
                reason += " IELTS is slightly short by " + formatNumber(Math.abs(margin)) + ".";
            } else {
                reason += " IELTS margin is " + formatNumber(margin) + ".";
            }
        } else if (ieltsScore != null && candidate.ieltsMin == null) {
            reason += " IELTS requirement is missing, so confidence is reduced.";
        }
        if (scopeContext.isRegion() && candidate.globalRank != null) {
            reason += " Global position: #" + candidate.globalRank + ".";
        }
        return new CategoryDecision(category, reason);
    }

    private Double riskAlignmentScore(String category, String riskProfile) {
        String profile = normalizeRiskProfile(riskProfile);
        return switch (profile) {
            case "conservative" -> switch (category) {
                case "reach" -> 55.0;
                case "target" -> 82.0;
                default -> 100.0;
            };
            case "aggressive" -> switch (category) {
                case "reach" -> 100.0;
                case "target" -> 88.0;
                default -> 70.0;
            };
            default -> switch (category) {
                case "reach" -> 72.0;
                case "target" -> 100.0;
                default -> 86.0;
            };
        };
    }

    private Double riskAdjustment(String category, String riskProfile) {
        String profile = normalizeRiskProfile(riskProfile);
        return switch (profile) {
            case "conservative" -> switch (category) {
                case "reach" -> CONSERVATIVE_REACH_PENALTY;
                case "target" -> CONSERVATIVE_TARGET_BOOST;
                default -> CONSERVATIVE_SAFETY_BOOST;
            };
            case "aggressive" -> switch (category) {
                case "reach" -> AGGRESSIVE_REACH_BOOST;
                case "target" -> AGGRESSIVE_TARGET_BOOST;
                default -> AGGRESSIVE_SAFETY_PENALTY;
            };
            default -> switch (category) {
                case "reach" -> BALANCED_REACH_BOOST;
                case "target" -> BALANCED_TARGET_BOOST;
                default -> BALANCED_SAFETY_BOOST;
            };
        };
    }

    private Map<Long, PoolContext> buildPoolContexts(
            List<Candidate> candidates,
            Integer targetRank,
            RankingContext scopeContext
    ) {
        if (targetRank == null || targetRank <= 0) {
            return Map.of();
        }

        List<PoolRank> ranked = new ArrayList<>();
        for (Candidate candidate : candidates) {
            Integer decisionRank = decisionRank(candidate, scopeContext);
            if (decisionRank != null) {
                ranked.add(new PoolRank(candidate, decisionRank));
            }
        }
        if (ranked.isEmpty()) {
            return Map.of();
        }

        ranked.sort(Comparator.comparing(PoolRank::rank).thenComparing(poolRank -> poolRank.candidate().canonicalUniversityId));
        int maxRank = ranked.get(ranked.size() - 1).rank();
        boolean elitePool = ranked.size() >= 4
                && targetRank <= 200
                && maxRank <= Math.round(targetRank * 0.5);

        Map<Long, PoolContext> contexts = new LinkedHashMap<>();
        for (int i = 0; i < ranked.size(); i++) {
            PoolRank poolRank = ranked.get(i);
            contexts.put(poolRank.candidate().canonicalUniversityId, new PoolContext(i, ranked.size(), elitePool));
        }
        return contexts;
    }

    private Thresholds thresholdsForRiskProfile(String riskProfile) {
        return switch (normalizeRiskProfile(riskProfile)) {
            case "conservative" -> new Thresholds(
                    Math.max(0.2, REACH_RATIO_UPPER + CONSERVATIVE_REACH_ADJUSTMENT),
                    Math.max(0.6, TARGET_RATIO_UPPER + CONSERVATIVE_TARGET_ADJUSTMENT)
            );
            case "aggressive" -> new Thresholds(
                    REACH_RATIO_UPPER + AGGRESSIVE_REACH_ADJUSTMENT,
                    TARGET_RATIO_UPPER + AGGRESSIVE_TARGET_ADJUSTMENT
            );
            default -> new Thresholds(REACH_RATIO_UPPER, TARGET_RATIO_UPPER);
        };
    }

    private String normalizeRiskProfile(String riskProfile) {
        String cleaned = riskProfile == null ? DEFAULT_RISK_PROFILE : riskProfile.trim().toLowerCase(Locale.ROOT);
        return switch (cleaned) {
            case "conservative", "aggressive", "balanced" -> cleaned;
            default -> DEFAULT_RISK_PROFILE;
        };
    }

    private String normalizeSubjectKey(String subjectKey) {
        if (subjectKey == null || subjectKey.isBlank()) {
            return null;
        }
        return subjectKey.trim().toLowerCase(Locale.ROOT);
    }

    private String normalizeCountryPolicy(String countryPolicy) {
        String cleaned = countryPolicy == null ? DEFAULT_COUNTRY_POLICY : countryPolicy.trim().toLowerCase(Locale.ROOT);
        return switch (cleaned) {
            case "hard_filter", "soft_preference" -> cleaned;
            default -> DEFAULT_COUNTRY_POLICY;
        };
    }

    private String shiftRiskier(String category) {
        return "safety".equals(category) ? "target" : "reach";
    }

    private Double ieltsMargin(Double requirement, Double ieltsScore) {
        if (requirement == null || ieltsScore == null) {
            return null;
        }
        return round(ieltsScore - requirement);
    }

    private String confidenceLabel(Double confidenceScore) {
        if (confidenceScore >= 80.0) {
            return "high";
        }
        if (confidenceScore >= 60.0) {
            return "medium";
        }
        return "low";
    }

    private Double countryMatchScore(String candidateCountry, String preferredCountry) {
        if (preferredCountry == null || preferredCountry.isBlank()) {
            return 55.0;
        }
        if (candidateCountry == null || candidateCountry.isBlank()) {
            return 25.0;
        }
        if (candidateCountry.equalsIgnoreCase(preferredCountry.trim())) {
            return 100.0;
        }
        return 10.0;
    }

    private String preferenceAlignment(Double countryMatchScore, Double riskAdjustment, String preferredCountry) {
        double total = 60.0 + (riskAdjustment == null ? 0.0 : riskAdjustment);
        int count = 1;
        if (preferredCountry != null && !preferredCountry.isBlank()) {
            total += countryMatchScore == null ? 0.0 : countryMatchScore;
            count += 1;
        }
        double average = total / count;
        if (average >= 78.0) {
            return "strong";
        }
        if (average >= 55.0) {
            return "moderate";
        }
        return "low";
    }

    private Map<String, Double> resolvePreferenceWeights(String preferenceWeights) {
        Map<String, Double> merged = new LinkedHashMap<>();
        merged.put("ranking", V3_RANKING_WEIGHT);
        merged.put("ielts", V3_IELTS_FIT_WEIGHT);
        merged.put("confidence", V3_CONFIDENCE_WEIGHT);
        merged.put("country_match", V3_COUNTRY_MATCH_WEIGHT);

        if (preferenceWeights != null && !preferenceWeights.isBlank()) {
            try {
                Map<String, Object> raw = objectMapper.readValue(preferenceWeights, new TypeReference<>() {});
                for (Map.Entry<String, Object> entry : raw.entrySet()) {
                    if (!merged.containsKey(entry.getKey()) || entry.getValue() == null) {
                        continue;
                    }
                    merged.put(entry.getKey(), Math.max(0.0, Double.parseDouble(entry.getValue().toString())));
                }
            } catch (Exception ex) {
                throw new IllegalArgumentException("Invalid preferenceWeights JSON.", ex);
            }
        }

        double total = merged.values().stream().mapToDouble(Double::doubleValue).sum();
        if (total <= 0.0) {
            merged.put("ranking", 0.5);
            merged.put("ielts", 0.2);
            merged.put("confidence", 0.2);
            merged.put("country_match", 0.1);
            total = 1.0;
        }
        Map<String, Double> normalized = new LinkedHashMap<>();
        for (Map.Entry<String, Double> entry : merged.entrySet()) {
            normalized.put(entry.getKey(), entry.getValue() / total);
        }

        double rankingWeight = normalized.get("ranking");
        double maxOther = Math.max(
                normalized.get("ielts"),
                Math.max(normalized.get("confidence"), normalized.get("country_match"))
        );
        double targetRanking = Math.min(0.85, Math.max(Math.max(rankingWeight, V3_RANKING_MIN_WEIGHT), maxOther + 0.01));
        if (targetRanking > rankingWeight) {
            double otherTotal = normalized.get("ielts") + normalized.get("confidence") + normalized.get("country_match");
            normalized.put("ranking", targetRanking);
            double remaining = Math.max(0.0, 1.0 - targetRanking);
            if (otherTotal <= 0.0) {
                normalized.put("ielts", 0.0);
                normalized.put("confidence", 0.0);
                normalized.put("country_match", remaining);
            } else {
                normalized.put("ielts", remaining * (normalized.get("ielts") / otherTotal));
                normalized.put("confidence", remaining * (normalized.get("confidence") / otherTotal));
                normalized.put("country_match", remaining * (normalized.get("country_match") / otherTotal));
            }
        }

        Map<String, Double> rounded = new LinkedHashMap<>();
        for (Map.Entry<String, Double> entry : normalized.entrySet()) {
            rounded.put(entry.getKey(), round(entry.getValue()));
        }
        return rounded;
    }

    private double weightedAverage(Map<String, Double> weightsUsed, Map<String, Double> scoreMap) {
        double weightedSum = 0.0;
        double weightSum = 0.0;
        for (Map.Entry<String, Double> entry : weightsUsed.entrySet()) {
            Double score = scoreMap.get(entry.getKey());
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

    private Map<String, Double> componentContributions(Map<String, Double> weightsUsed, Map<String, Double> scoreMap) {
        double weightSum = weightsUsed.values().stream().mapToDouble(Double::doubleValue).sum();
        Map<String, Double> contributions = new LinkedHashMap<>();
        if (weightSum <= 0.0) {
            return contributions;
        }
        for (Map.Entry<String, Double> entry : weightsUsed.entrySet()) {
            Double score = scoreMap.get(entry.getKey());
            if (score == null) {
                continue;
            }
            contributions.put(entry.getKey(), round((entry.getValue() / weightSum) * score));
        }
        return contributions;
    }

    private String buildExplanationV1(
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

    private String buildExplanationV2(
            Candidate candidate,
            Double ieltsScore,
            Double rankingScore,
            String confidenceLabel,
            Double ieltsMargin,
            double finalScore,
            String categoryReason,
            RankingContext scopeContext
    ) {
        List<String> recommendationBits = new ArrayList<>();
        recommendationBits.add(rankSummary(candidate, scopeContext));
        if (rankingScore != null) {
            recommendationBits.add("ranking score is " + formatScore(rankingScore));
        }
        recommendationBits.add("confidence is " + confidenceLabel);
        if (ieltsMargin != null) {
            if (ieltsMargin >= 0) {
                recommendationBits.add("IELTS requirement " + candidate.ieltsMin + " is covered by a " + formatNumber(ieltsMargin) + " margin");
            } else {
                recommendationBits.add("IELTS is short by " + formatNumber(Math.abs(ieltsMargin)));
            }
        } else if (ieltsScore != null && candidate.ieltsMin == null) {
            recommendationBits.add("IELTS requirement is missing");
        }
        recommendationBits.add("overall fit score is " + formatScore(finalScore));
        return categoryReason + " Recommended because " + String.join(", ", recommendationBits) + ".";
    }

    private String buildExplanationV3(
            String country,
            String countryPolicy,
            String candidateCountry,
            String category,
            Integer effectiveRank,
            Integer targetRank,
            Double ieltsMargin,
            String confidenceLabel,
            double riskAdjustment,
            String preferenceAlignment,
            String categoryReason,
            String riskProfile,
            Candidate candidate,
            RankingContext scopeContext
    ) {
        List<String> fitBits = new ArrayList<>();
        fitBits.add(rankSummary(candidate, scopeContext));
        if (effectiveRank != null && targetRank != null) {
            if (scopeContext.isRegion()) {
                fitBits.add(scopeContext.region() + " rank #" + effectiveRank + " is judged against target #" + targetRank);
            } else {
                fitBits.add("rank #" + effectiveRank + " is judged against target #" + targetRank);
            }
        }
        if (ieltsMargin != null) {
            if (ieltsMargin >= 0) {
                fitBits.add("IELTS clears the requirement by " + formatNumber(ieltsMargin));
            } else {
                fitBits.add("IELTS is short by " + formatNumber(Math.abs(ieltsMargin)));
            }
        }
        if (country != null && !country.isBlank()) {
            if ("hard_filter".equals(normalizeCountryPolicy(countryPolicy))) {
                fitBits.add("country is filtered to " + country);
            } else if (candidateCountry != null && candidateCountry.equalsIgnoreCase(country.trim())) {
                fitBits.add("country matches " + country);
            } else {
                fitBits.add("country mismatch is tolerated as a soft preference");
            }
        }
        if (confidenceLabel != null) {
            fitBits.add("confidence is " + confidenceLabel);
        }

        StringBuilder explanation = new StringBuilder(categoryReason);
        if (!fitBits.isEmpty()) {
            explanation.append(" Recommended because ").append(String.join(", ", fitBits)).append(".");
        }
        if (scopeContext.isRegion()) {
            explanation.append(" ").append(regionStrengthPhrase(candidate, scopeContext));
        }
        if (Math.abs(riskAdjustment) >= 1.0) {
            explanation.append(" The ")
                    .append(normalizeRiskProfile(riskProfile))
                    .append(" profile ")
                    .append(riskAdjustment >= 0 ? "boosted" : "reduced")
                    .append(" this ")
                    .append(category)
                    .append(" option.");
        }
        return explanation.toString();
    }

    private RecommendationExplain buildRecommendationExplain(
            Candidate candidate,
            Integer targetRank,
            String riskProfile,
            Double rankingFit,
            Double riskFit,
            Double languageFit,
            RankingTrustDTO trust,
            Double ieltsScore,
            RankingContext scopeContext
    ) {
        double resolvedRankingFit = rankingFit == null ? 0.0 : rankingFit;
        double resolvedRiskFit = riskFit == null ? 50.0 : riskFit;
        double resolvedLanguageFit = languageFit == null ? 40.0 : languageFit;
        double resolvedDataConfidence = trust == null ? 0.0 : trust.getTrustScore();

        RecommendationExplainDimensions dimensions = new RecommendationExplainDimensions();
        dimensions.setRankingFit(round(resolvedRankingFit));
        dimensions.setRiskFit(round(resolvedRiskFit));
        dimensions.setLanguageFit(round(resolvedLanguageFit));
        dimensions.setDataConfidence(round(resolvedDataConfidence));

        double fitScore = round(
                (resolvedRankingFit * 0.40)
                        + (resolvedRiskFit * 0.20)
                        + (resolvedLanguageFit * 0.20)
                        + (resolvedDataConfidence * 0.20)
        );

        List<String> reasons = new ArrayList<>();
        List<String> warnings = new ArrayList<>();

        Integer displayRank = displayRank(candidate, scopeContext);
        if (displayRank != null && targetRank != null) {
            if (resolvedRankingFit >= 80.0) {
                reasons.add("Rank #" + displayRank + " is close to your target #" + targetRank + ".");
            } else if (resolvedRankingFit >= 60.0) {
                reasons.add("Rank #" + displayRank + " is within a workable range of your target #" + targetRank + ".");
            } else {
                warnings.add("Rank #" + displayRank + " is far from your target #" + targetRank + ".");
            }
        }

        Double margin = ieltsMargin(candidate.ieltsMin, ieltsScore);
        if (ieltsScore == null) {
            warnings.add("No IELTS score provided, so language fit is estimated conservatively.");
        } else if (candidate.ieltsMin == null) {
            warnings.add("Language requirement data is missing.");
        } else if (margin != null && margin >= 0) {
            reasons.add("Your IELTS (" + formatNumber(ieltsScore) + ") meets the typical requirement of " + formatNumber(candidate.ieltsMin) + ".");
        } else if (margin != null) {
            warnings.add("IELTS may be below requirement by " + formatNumber(Math.abs(margin)) + ".");
        }

        String normalizedRiskProfile = normalizeRiskProfile(riskProfile);
        if (resolvedRiskFit >= 85.0) {
            reasons.add("This " + candidateFitLabel(candidate, scopeContext) + " aligns well with your " + normalizedRiskProfile + " risk profile.");
        } else if (resolvedRiskFit < 60.0) {
            warnings.add("This option is a weaker fit for your " + normalizedRiskProfile + " risk profile.");
        }

        if (trust != null && trust.getTrustExplain() != null) {
            List<String> trustNotes = trust.getTrustExplain().getNotes();
            for (String note : trustNotes) {
                if (note.toLowerCase(Locale.ROOT).contains("strong agreement")) {
                    reasons.add(note);
                } else {
                    warnings.add(note);
                }
            }
            if (trust.getTrustScore() < 60.0) {
                warnings.add("Ranking data has low confidence.");
            }
        } else {
            warnings.add("Ranking confidence data is unavailable.");
        }

        RecommendationExplain explain = new RecommendationExplain();
        explain.setFitScore(fitScore);
        explain.setDimensions(dimensions);
        explain.setReasons(deduplicate(reasons));
        explain.setWarnings(deduplicate(warnings));
        return explain;
    }

    private List<String> deduplicate(List<String> values) {
        List<String> out = new ArrayList<>();
        for (String value : values) {
            if (value == null || value.isBlank() || out.contains(value)) {
                continue;
            }
            out.add(value);
        }
        return out;
    }

    private List<Candidate> dedupeCandidates(List<Candidate> candidates, RankingContext scopeContext) {
        Map<Long, Candidate> deduped = new LinkedHashMap<>();
        for (Candidate candidate : candidates) {
            if (candidate == null || candidate.canonicalUniversityId == null) {
                continue;
            }
            Candidate existing = deduped.get(candidate.canonicalUniversityId);
            if (existing == null || compareCandidatePriority(candidate, existing, scopeContext) < 0) {
                deduped.put(candidate.canonicalUniversityId, candidate);
            }
        }
        return new ArrayList<>(deduped.values());
    }

    private int compareCandidatePriority(Candidate left, Candidate right, RankingContext scopeContext) {
        int decisionRankCompare = compareNullableInts(decisionRank(left, scopeContext), decisionRank(right, scopeContext));
        if (decisionRankCompare != 0) {
            return decisionRankCompare;
        }

        int globalRankCompare = compareNullableInts(left.globalRank, right.globalRank);
        if (globalRankCompare != 0) {
            return globalRankCompare;
        }

        int coverageCompare = -Double.compare(left.coverageRatio, right.coverageRatio);
        if (coverageCompare != 0) {
            return coverageCompare;
        }

        int sourceCountCompare = -Integer.compare(left.sourceRanks.size(), right.sourceRanks.size());
        if (sourceCountCompare != 0) {
            return sourceCountCompare;
        }

        return compareNullableDoubles(left.ieltsMin, right.ieltsMin);
    }

    private List<RecommendationResult> dedupeRecommendationResults(List<RecommendationResult> rows) {
        Map<Long, RecommendationResult> deduped = new LinkedHashMap<>();
        for (RecommendationResult row : rows) {
            if (row == null || row.getCanonicalUniversityId() == null) {
                continue;
            }
            deduped.putIfAbsent(row.getCanonicalUniversityId(), row);
        }
        return new ArrayList<>(deduped.values());
    }

    private int compareNullableInts(Integer left, Integer right) {
        if (left == null && right == null) {
            return 0;
        }
        if (left == null) {
            return 1;
        }
        if (right == null) {
            return -1;
        }
        return Integer.compare(left, right);
    }

    private int compareNullableDoubles(Double left, Double right) {
        if (left == null && right == null) {
            return 0;
        }
        if (left == null) {
            return 1;
        }
        if (right == null) {
            return -1;
        }
        return Double.compare(left, right);
    }

    private String candidateFitLabel(Candidate candidate, RankingContext scopeContext) {
        Integer displayRank = decisionRank(candidate, scopeContext);
        if (displayRank == null) {
            return "option";
        }
        if (displayRank <= 50) {
            return "higher-ranked option";
        }
        if (displayRank <= 150) {
            return "balanced option";
        }
        return "safer option";
    }

    private String rankSummary(Candidate candidate, RankingContext scopeContext) {
        return rankedPosition(candidate, scopeContext).primaryRankSummary();
    }

    private String regionStrengthPhrase(Candidate candidate, RankingContext scopeContext) {
        if (candidate.scopeRank == null || candidate.globalRank == null) {
            return "Regional context is used as the primary decision signal.";
        }
        int rankGap = candidate.globalRank - candidate.scopeRank;
        if (candidate.scopeRank <= 25 && candidate.globalRank <= 50) {
            return "Balanced regional and global strength makes this a strong regional option.";
        }
        if (rankGap >= 20) {
            return "Strong regional option with a slightly weaker global position.";
        }
        if (rankGap <= -20) {
            return "Strong globally but weaker within this region.";
        }
        return "Regional and global strength are broadly balanced.";
    }

    private int safeLimit(Integer limit, int defaultValue) {
        return Math.max(1, Math.min(limit == null ? defaultValue : limit, MAX_LIMIT));
    }

    private double clampScore(double value) {
        return Math.max(0.0, Math.min(100.0, value));
    }

    private Double round(double value) {
        return Math.round(value * 10000.0) / 10000.0;
    }

    private String formatScore(Double value) {
        if (value == null) {
            return "n/a";
        }
        return String.format(Locale.ROOT, "%.2f", value);
    }

    private String formatNumber(Double value) {
        if (value == null) {
            return "n/a";
        }
        if (Math.rint(value) == value) {
            return Integer.toString(value.intValue());
        }
        return String.format(Locale.ROOT, "%.2f", value);
    }

    private int shortlistCount(String shortlist) {
        if (shortlist == null || shortlist.isBlank()) {
            return 0;
        }
        return (int) Arrays.stream(shortlist.split(","))
                .map(String::trim)
                .filter(token -> !token.isEmpty())
                .count();
    }

    private static final class Candidate {
        private Long canonicalUniversityId;
        private String universityName;
        private String country;
        private Integer rankingYear;
        private Integer aggregatedRank;
        private Integer globalRank;
        private Integer scopeRank;
        private Double aggregatedScore;
        private double coverageRatio;
        private Double ieltsMin;
        private Integer toeflMin;
        private Integer duolingoMin;
        private Double gpaMin;
        private String applicationDeadline;
        private String aggregationMethodVersion;
        private Map<String, Integer> sourceRanks = new LinkedHashMap<>();
    }

    private record EffectiveRank(Integer rank, String source) {
    }

    private record Thresholds(double reachUpper, double targetUpper) {
    }

    private record CategoryDecision(String category, String reason) {
    }

    private record PoolRank(Candidate candidate, Integer rank) {
    }

    private record PoolContext(int position, int poolSize, boolean elitePool) {
    }

    private record SubjectRankingSignalRecord(
            String subjectKey,
            String subjectName,
            Integer rankingYear,
            Integer rankPosition,
            String rankDisplay,
            Double score,
            String sourceCode
    ) {
    }

    private record SubjectScoringContext(
            String subjectKey,
            String subjectName,
            Map<Long, SubjectRankingSignalRecord> records
    ) {
        private static SubjectScoringContext disabled() {
            return new SubjectScoringContext(null, null, Map.of());
        }

        private boolean enabled() {
            return subjectKey != null && !subjectKey.isBlank();
        }
    }

    private record SubjectSignal(
            String subjectKey,
            String subjectName,
            Integer rankPosition,
            String rankDisplay,
            Double score,
            String sourceCode,
            double signalScore,
            double adjustment,
            boolean hasData,
            String reason
    ) {
        private static SubjectSignal disabled() {
            return new SubjectSignal(null, null, null, null, null, null, 50.0, 0.0, false, "");
        }
    }
}
