package clawer.dto;

public class RankingDTO {
    private Long canonicalUniversityId;
    private String universityName;
    private String country;
    private Integer aggregatedRank;
    private Double compositeScore;
    private Integer rankingYear;
    private String primarySource;
    private Integer sourceCount;
    private String slug;
    private Integer globalRank;
    private Integer scopeRank;
    private AggregationExplainDTO aggregationExplain;
    private Double trustScore;
    private String trustLevel;
    private TrustExplainDTO trustExplain;

    public RankingDTO() {}

    public Long getCanonicalUniversityId() { return canonicalUniversityId; }
    public void setCanonicalUniversityId(Long canonicalUniversityId) { this.canonicalUniversityId = canonicalUniversityId; }

    public String getUniversityName() { return universityName; }
    public void setUniversityName(String universityName) { this.universityName = universityName; }

    public String getCountry() { return country; }
    public void setCountry(String country) { this.country = country; }

    public Integer getAggregatedRank() { return aggregatedRank; }
    public void setAggregatedRank(Integer aggregatedRank) { this.aggregatedRank = aggregatedRank; }

    public Double getCompositeScore() { return compositeScore; }
    public void setCompositeScore(Double compositeScore) { this.compositeScore = compositeScore; }

    public Integer getRankingYear() { return rankingYear; }
    public void setRankingYear(Integer rankingYear) { this.rankingYear = rankingYear; }

    public String getPrimarySource() { return primarySource; }
    public void setPrimarySource(String primarySource) { this.primarySource = primarySource; }

    public Integer getSourceCount() { return sourceCount; }
    public void setSourceCount(Integer sourceCount) { this.sourceCount = sourceCount; }

    public String getSlug() { return slug; }
    public void setSlug(String slug) { this.slug = slug; }

    public Integer getGlobalRank() { return globalRank; }
    public void setGlobalRank(Integer globalRank) { this.globalRank = globalRank; }

    public Integer getScopeRank() { return scopeRank; }
    public void setScopeRank(Integer scopeRank) { this.scopeRank = scopeRank; }

    public AggregationExplainDTO getAggregationExplain() { return aggregationExplain; }
    public void setAggregationExplain(AggregationExplainDTO aggregationExplain) { this.aggregationExplain = aggregationExplain; }

    public Double getTrustScore() { return trustScore; }
    public void setTrustScore(Double trustScore) { this.trustScore = trustScore; }

    public String getTrustLevel() { return trustLevel; }
    public void setTrustLevel(String trustLevel) { this.trustLevel = trustLevel; }

    public TrustExplainDTO getTrustExplain() { return trustExplain; }
    public void setTrustExplain(TrustExplainDTO trustExplain) { this.trustExplain = trustExplain; }
}
