package clawer.domain.ranking;

import java.util.LinkedHashMap;
import java.util.Map;

public class ScopedRankedUniversity {
    private Long canonicalUniversityId;
    private String universityName;
    private String country;
    private String slug;
    private Integer rankingYear;
    private Integer globalRank;
    private Integer scopeRank;
    private Double compositeScore;
    private Integer sourceCount;
    private Double coverageRatio;
    private Double ieltsMin;
    private String aggregationMethodVersion;
    private Map<String, Integer> sourceRanks = new LinkedHashMap<>();

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

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public Integer getRankingYear() {
        return rankingYear;
    }

    public void setRankingYear(Integer rankingYear) {
        this.rankingYear = rankingYear;
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

    public Double getCompositeScore() {
        return compositeScore;
    }

    public void setCompositeScore(Double compositeScore) {
        this.compositeScore = compositeScore;
    }

    public Integer getSourceCount() {
        return sourceCount;
    }

    public void setSourceCount(Integer sourceCount) {
        this.sourceCount = sourceCount;
    }

    public Double getCoverageRatio() {
        return coverageRatio;
    }

    public void setCoverageRatio(Double coverageRatio) {
        this.coverageRatio = coverageRatio;
    }

    public Double getIeltsMin() {
        return ieltsMin;
    }

    public void setIeltsMin(Double ieltsMin) {
        this.ieltsMin = ieltsMin;
    }

    public String getAggregationMethodVersion() {
        return aggregationMethodVersion;
    }

    public void setAggregationMethodVersion(String aggregationMethodVersion) {
        this.aggregationMethodVersion = aggregationMethodVersion;
    }

    public Map<String, Integer> getSourceRanks() {
        return sourceRanks;
    }

    public void setSourceRanks(Map<String, Integer> sourceRanks) {
        this.sourceRanks = sourceRanks;
    }

    public RankedPosition rankedPosition(RankingContext context) {
        return RankedPosition.of(context, globalRank, scopeRank);
    }
}
