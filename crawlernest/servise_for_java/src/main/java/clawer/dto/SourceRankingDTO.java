package clawer.dto;

public class SourceRankingDTO {
    private String source;
    private Integer year;
    private Integer rank;
    private String rankDisplay;
    private Double score;
    /** Movement in this source since the prior held edition; null when withheld. Never composite. */
    private RankDeltaDTO rankDelta;
    /** Why {@link #rankDelta} is null, or {@code banded} when it is an interval; null for an exact delta. */
    private String rankDeltaReason;

    public SourceRankingDTO() {}

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }

    public Integer getRank() { return rank; }
    public void setRank(Integer rank) { this.rank = rank; }

    /** The rank as the source printed it ("=98", "201–250"); {@link #rank} is its lower bound. */
    public String getRankDisplay() { return rankDisplay; }
    public void setRankDisplay(String rankDisplay) { this.rankDisplay = rankDisplay; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }

    public RankDeltaDTO getRankDelta() { return rankDelta; }
    public void setRankDelta(RankDeltaDTO rankDelta) { this.rankDelta = rankDelta; }

    public String getRankDeltaReason() { return rankDeltaReason; }
    public void setRankDeltaReason(String rankDeltaReason) { this.rankDeltaReason = rankDeltaReason; }
}
