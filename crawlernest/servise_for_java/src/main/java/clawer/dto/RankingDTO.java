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
}
