package clawer.dto;

public class AggregatedRankingDTO {
    private Integer displayRank;
    private Double compositeScore;
    private Integer rankingYear;
    private String aggregationMethodVersion;

    public Integer getDisplayRank() { return displayRank; }
    public void setDisplayRank(Integer displayRank) { this.displayRank = displayRank; }

    public Double getCompositeScore() { return compositeScore; }
    public void setCompositeScore(Double compositeScore) { this.compositeScore = compositeScore; }

    public Integer getRankingYear() { return rankingYear; }
    public void setRankingYear(Integer rankingYear) { this.rankingYear = rankingYear; }

    public String getAggregationMethodVersion() { return aggregationMethodVersion; }
    public void setAggregationMethodVersion(String aggregationMethodVersion) { this.aggregationMethodVersion = aggregationMethodVersion; }
}
