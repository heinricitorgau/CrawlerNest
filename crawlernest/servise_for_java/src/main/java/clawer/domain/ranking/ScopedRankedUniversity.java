package clawer.domain.ranking;

import clawer.dto.AggregationExplainDTO;
import clawer.dto.TrustExplainDTO;

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
    private Integer toeflMin;
    private Integer duolingoMin;
    private Double gpaMin;
    private String applicationDeadline;
    private String aggregationMethodVersion;
    private Double trustScore;
    private String trustLevel;
    private AggregationExplainDTO aggregationExplain;
    private TrustExplainDTO trustExplain;
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

    public Integer getToeflMin() {
        return toeflMin;
    }

    public void setToeflMin(Integer toeflMin) {
        this.toeflMin = toeflMin;
    }

    public Integer getDuolingoMin() {
        return duolingoMin;
    }

    public void setDuolingoMin(Integer duolingoMin) {
        this.duolingoMin = duolingoMin;
    }

    public Double getGpaMin() {
        return gpaMin;
    }

    public void setGpaMin(Double gpaMin) {
        this.gpaMin = gpaMin;
    }

    /** ISO-8601 date, or null when no source published one. */
    public String getApplicationDeadline() {
        return applicationDeadline;
    }

    public void setApplicationDeadline(String applicationDeadline) {
        this.applicationDeadline = applicationDeadline;
    }

    public String getAggregationMethodVersion() {
        return aggregationMethodVersion;
    }

    public void setAggregationMethodVersion(String aggregationMethodVersion) {
        this.aggregationMethodVersion = aggregationMethodVersion;
    }

    public Double getTrustScore() {
        return trustScore;
    }

    public void setTrustScore(Double trustScore) {
        this.trustScore = trustScore;
    }

    public String getTrustLevel() {
        return trustLevel;
    }

    public void setTrustLevel(String trustLevel) {
        this.trustLevel = trustLevel;
    }

    public AggregationExplainDTO getAggregationExplain() {
        return aggregationExplain;
    }

    public void setAggregationExplain(AggregationExplainDTO aggregationExplain) {
        this.aggregationExplain = aggregationExplain;
    }

    public TrustExplainDTO getTrustExplain() {
        return trustExplain;
    }

    public void setTrustExplain(TrustExplainDTO trustExplain) {
        this.trustExplain = trustExplain;
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
