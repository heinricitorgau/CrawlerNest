package clawer.model;

import java.util.List;
import java.util.Map;

public class RecommendationResult {
    private Long canonicalUniversityId;
    private String universityName;
    private String country;
    private Integer aggregatedRank;
    private String scope;
    private String region;
    private Integer globalRank;
    private Integer scopeRank;
    private Double ieltsMin;
    private Double matchingScore;
    private String category;
    private String preferenceAlignment;
    private Double recommendationConfidence;
    private String confidenceReason;
    private String scoringVersion;
    private String decisionPolicyVersion;
    private String explanationVersion;
    private String explanation;
    private String aggregationMethodVersion;
    private Map<String, Object> scoreBreakdown;
    private List<String> rulesPassed;
    private RecommendationExplain recommendationExplain;
    private Map<String, Object> subjectFit;

    public RecommendationResult() {
    }

    public RecommendationResult(
            Long canonicalUniversityId,
            String universityName,
            String country,
            Integer aggregatedRank,
            Double ieltsMin,
            Double matchingScore,
            String category,
            String preferenceAlignment,
            Double recommendationConfidence,
            String confidenceReason,
            String scoringVersion,
            String decisionPolicyVersion,
            String explanationVersion,
            String explanation,
            String aggregationMethodVersion,
            Map<String, Object> scoreBreakdown,
            List<String> rulesPassed
    ) {
        this.canonicalUniversityId = canonicalUniversityId;
        this.universityName = universityName;
        this.country = country;
        this.aggregatedRank = aggregatedRank;
        this.ieltsMin = ieltsMin;
        this.matchingScore = matchingScore;
        this.category = category;
        this.preferenceAlignment = preferenceAlignment;
        this.recommendationConfidence = recommendationConfidence;
        this.confidenceReason = confidenceReason;
        this.scoringVersion = scoringVersion;
        this.decisionPolicyVersion = decisionPolicyVersion;
        this.explanationVersion = explanationVersion;
        this.explanation = explanation;
        this.aggregationMethodVersion = aggregationMethodVersion;
        this.scoreBreakdown = scoreBreakdown;
        this.rulesPassed = rulesPassed;
    }

    public Long getCanonicalUniversityId() {
        return canonicalUniversityId;
    }

    public void setCanonicalUniversityId(Long canonicalUniversityId) {
        this.canonicalUniversityId = canonicalUniversityId;
    }

    public String getUniversityName() {
        return universityName;
    }

    public void setUniversityName(String universityName) {
        this.universityName = universityName;
    }

    public String getCountry() {
        return country;
    }

    public void setCountry(String country) {
        this.country = country;
    }

    public Integer getAggregatedRank() {
        return aggregatedRank;
    }

    public void setAggregatedRank(Integer aggregatedRank) {
        this.aggregatedRank = aggregatedRank;
    }

    public String getScope() {
        return scope;
    }

    public void setScope(String scope) {
        this.scope = scope;
    }

    public String getRegion() {
        return region;
    }

    public void setRegion(String region) {
        this.region = region;
    }

    public Integer getGlobalRank() {
        return globalRank;
    }

    public void setGlobalRank(Integer globalRank) {
        this.globalRank = globalRank;
    }

    public Integer getScopeRank() {
        return scopeRank;
    }

    public void setScopeRank(Integer scopeRank) {
        this.scopeRank = scopeRank;
    }

    public Double getIeltsMin() {
        return ieltsMin;
    }

    public void setIeltsMin(Double ieltsMin) {
        this.ieltsMin = ieltsMin;
    }

    public Double getMatchingScore() {
        return matchingScore;
    }

    public void setMatchingScore(Double matchingScore) {
        this.matchingScore = matchingScore;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getExplanation() {
        return explanation;
    }

    public String getPreferenceAlignment() {
        return preferenceAlignment;
    }

    public void setPreferenceAlignment(String preferenceAlignment) {
        this.preferenceAlignment = preferenceAlignment;
    }

    public Double getRecommendationConfidence() {
        return recommendationConfidence;
    }

    public void setRecommendationConfidence(Double recommendationConfidence) {
        this.recommendationConfidence = recommendationConfidence;
    }

    public String getConfidenceReason() {
        return confidenceReason;
    }

    public void setConfidenceReason(String confidenceReason) {
        this.confidenceReason = confidenceReason;
    }

    public String getScoringVersion() {
        return scoringVersion;
    }

    public void setScoringVersion(String scoringVersion) {
        this.scoringVersion = scoringVersion;
    }

    public String getDecisionPolicyVersion() {
        return decisionPolicyVersion;
    }

    public void setDecisionPolicyVersion(String decisionPolicyVersion) {
        this.decisionPolicyVersion = decisionPolicyVersion;
    }

    public String getExplanationVersion() {
        return explanationVersion;
    }

    public void setExplanationVersion(String explanationVersion) {
        this.explanationVersion = explanationVersion;
    }

    public void setExplanation(String explanation) {
        this.explanation = explanation;
    }

    public String getAggregationMethodVersion() {
        return aggregationMethodVersion;
    }

    public void setAggregationMethodVersion(String aggregationMethodVersion) {
        this.aggregationMethodVersion = aggregationMethodVersion;
    }

    public Map<String, Object> getScoreBreakdown() {
        return scoreBreakdown;
    }

    public void setScoreBreakdown(Map<String, Object> scoreBreakdown) {
        this.scoreBreakdown = scoreBreakdown;
    }

    public List<String> getRulesPassed() {
        return rulesPassed;
    }

    public void setRulesPassed(List<String> rulesPassed) {
        this.rulesPassed = rulesPassed;
    }

    public RecommendationExplain getRecommendationExplain() {
        return recommendationExplain;
    }

    public void setRecommendationExplain(RecommendationExplain recommendationExplain) {
        this.recommendationExplain = recommendationExplain;
    }

    public Map<String, Object> getSubjectFit() {
        return subjectFit;
    }

    public void setSubjectFit(Map<String, Object> subjectFit) {
        this.subjectFit = subjectFit;
    }
}
