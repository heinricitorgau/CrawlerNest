package clawer.model;

import java.util.List;
import java.util.Map;

public class RecommendationResult {
    private Long canonicalUniversityId;
    private String universityName;
    private String country;
    private Integer aggregatedRank;
    private Double ieltsMin;
    private Double matchingScore;
    private String category;
    private String preferenceAlignment;
    private String explanation;
    private String aggregationMethodVersion;
    private Map<String, Object> scoreBreakdown;
    private List<String> rulesPassed;

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
}
