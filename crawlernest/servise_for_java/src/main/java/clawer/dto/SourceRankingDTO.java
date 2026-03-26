package clawer.dto;

public class SourceRankingDTO {
    private String source;
    private Integer year;
    private Integer rank;
    private Double score;

    public SourceRankingDTO() {}

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }

    public Integer getRank() { return rank; }
    public void setRank(Integer rank) { this.rank = rank; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
}
