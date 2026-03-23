package clawer.model;

import jakarta.persistence.*;

@Entity
@Table(name = "rankings", schema = "warehouse")
public class Ranking {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "ranking_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "university_id", nullable = false)
    private University university;

    @Column(name = "ranking_source", nullable = false)
    private String rankingSource;

    @Column(name = "ranking_type", nullable = false)
    private String rankingType;

    @Column(name = "ranking_year")
    private Integer rankingYear;

    @Column(name = "rank_start")
    private Integer rankStart;

    @Column(name = "rank_end")
    private Integer rankEnd;

    @Column(name = "score")
    private Double score;

    @Column(name = "metrics_json")
    private String metricsJson;

    @Column(name = "source_url")
    private String sourceUrl;

    public Ranking() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public University getUniversity() { return university; }
    public void setUniversity(University university) { this.university = university; }

    public String getRankingSource() { return rankingSource; }
    public void setRankingSource(String rankingSource) { this.rankingSource = rankingSource; }

    public String getRankingType() { return rankingType; }
    public void setRankingType(String rankingType) { this.rankingType = rankingType; }

    public Integer getRankingYear() { return rankingYear; }
    public void setRankingYear(Integer rankingYear) { this.rankingYear = rankingYear; }

    public Integer getRankStart() { return rankStart; }
    public void setRankStart(Integer rankStart) { this.rankStart = rankStart; }

    public Integer getRankEnd() { return rankEnd; }
    public void setRankEnd(Integer rankEnd) { this.rankEnd = rankEnd; }

    public Double getScore() { return score; }
    public void setScore(Double score) { this.score = score; }

    public String getMetricsJson() { return metricsJson; }
    public void setMetricsJson(String metricsJson) { this.metricsJson = metricsJson; }

    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }
}
