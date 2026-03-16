package clawer.model;

/**
 * Represents a specific ranking entry for a University from a particular ranking source.
 */
public class Ranking {
    private String universityId;
    private String rankingSource; // e.g., "qs", "the", "arwu"
    private Integer rank;
    private Integer year;

    public Ranking() {
    }

    public Ranking(String universityId, String rankingSource, Integer rank, Integer year) {
        this.universityId = universityId;
        this.rankingSource = rankingSource;
        this.rank = rank;
        this.year = year;
    }

    public String getUniversityId() { return universityId; }
    public void setUniversityId(String universityId) { this.universityId = universityId; }

    public String getRankingSource() { return rankingSource; }
    public void setRankingSource(String rankingSource) { this.rankingSource = rankingSource; }

    public Integer getRank() { return rank; }
    public void setRank(Integer rank) { this.rank = rank; }

    public Integer getYear() { return year; }
    public void setYear(Integer year) { this.year = year; }
}
