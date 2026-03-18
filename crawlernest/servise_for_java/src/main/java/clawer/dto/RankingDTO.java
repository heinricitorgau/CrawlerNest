package clawer.dto;

public class RankingDTO {
    private String source;
    private String type;
    private Integer year;
    private Integer rankStart;
    private Integer rankEnd;
    private Double score;

    public RankingDTO() {}

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public String getType() { return type; }
    public void setType(String type) { this.type = type; }

    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }

    public Integer getRankStart() { return rankStart; }
    public void setRankStart(Integer rankStart) { this.rankStart = rankStart; }

    public Integer getRankEnd() { return rankEnd; }
    public void setRankEnd(Integer rankEnd) { this.rankEnd = rankEnd; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }
}
