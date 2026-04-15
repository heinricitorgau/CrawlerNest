package clawer.dto;

import java.util.List;

public class RankingPreviewSummaryDTO {
    private int rowCount;
    private int sourceCount;
    private List<String> sources = List.of();
    private List<Integer> rankingYears = List.of();
    private Integer bestRank;
    private String bestSource;
    private Integer bestRankingYear;

    public int getRowCount() {
        return rowCount;
    }

    public void setRowCount(int rowCount) {
        this.rowCount = rowCount;
    }

    public int getSourceCount() {
        return sourceCount;
    }

    public void setSourceCount(int sourceCount) {
        this.sourceCount = sourceCount;
    }

    public List<String> getSources() {
        return sources;
    }

    public void setSources(List<String> sources) {
        this.sources = sources;
    }

    public List<Integer> getRankingYears() {
        return rankingYears;
    }

    public void setRankingYears(List<Integer> rankingYears) {
        this.rankingYears = rankingYears;
    }

    public Integer getBestRank() {
        return bestRank;
    }

    public void setBestRank(Integer bestRank) {
        this.bestRank = bestRank;
    }

    public String getBestSource() {
        return bestSource;
    }

    public void setBestSource(String bestSource) {
        this.bestSource = bestSource;
    }

    public Integer getBestRankingYear() {
        return bestRankingYear;
    }

    public void setBestRankingYear(Integer bestRankingYear) {
        this.bestRankingYear = bestRankingYear;
    }
}
