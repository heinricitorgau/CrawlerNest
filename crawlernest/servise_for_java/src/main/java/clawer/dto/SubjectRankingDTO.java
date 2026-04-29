package clawer.dto;

public class SubjectRankingDTO {
    private Long canonicalUniversityId;
    private String canonicalSlug;
    private String universityName;
    private String countryCode;
    private String countryName;
    private String subjectKey;
    private String subjectName;
    private Integer rankingYear;
    private Integer rankPosition;
    private String rankDisplay;
    private Double score;
    private Double scoreScale;
    private String sourceCode;
    private String sourceName;
    private String sourceUrl;

    public Long getCanonicalUniversityId() {
        return canonicalUniversityId;
    }

    public void setCanonicalUniversityId(Long canonicalUniversityId) {
        this.canonicalUniversityId = canonicalUniversityId;
    }

    public String getCanonicalSlug() {
        return canonicalSlug;
    }

    public void setCanonicalSlug(String canonicalSlug) {
        this.canonicalSlug = canonicalSlug;
    }

    public String getUniversityName() {
        return universityName;
    }

    public void setUniversityName(String universityName) {
        this.universityName = universityName;
    }

    public String getCountryCode() {
        return countryCode;
    }

    public void setCountryCode(String countryCode) {
        this.countryCode = countryCode;
    }

    public String getCountryName() {
        return countryName;
    }

    public void setCountryName(String countryName) {
        this.countryName = countryName;
    }

    public String getSubjectKey() {
        return subjectKey;
    }

    public void setSubjectKey(String subjectKey) {
        this.subjectKey = subjectKey;
    }

    public String getSubjectName() {
        return subjectName;
    }

    public void setSubjectName(String subjectName) {
        this.subjectName = subjectName;
    }

    public Integer getRankingYear() {
        return rankingYear;
    }

    public void setRankingYear(Integer rankingYear) {
        this.rankingYear = rankingYear;
    }

    public Integer getRankPosition() {
        return rankPosition;
    }

    public void setRankPosition(Integer rankPosition) {
        this.rankPosition = rankPosition;
    }

    public String getRankDisplay() {
        return rankDisplay;
    }

    public void setRankDisplay(String rankDisplay) {
        this.rankDisplay = rankDisplay;
    }

    public Double getScore() {
        return score;
    }

    public void setScore(Double score) {
        this.score = score;
    }

    public Double getScoreScale() {
        return scoreScale;
    }

    public void setScoreScale(Double scoreScale) {
        this.scoreScale = scoreScale;
    }

    public String getSourceCode() {
        return sourceCode;
    }

    public void setSourceCode(String sourceCode) {
        this.sourceCode = sourceCode;
    }

    public String getSourceName() {
        return sourceName;
    }

    public void setSourceName(String sourceName) {
        this.sourceName = sourceName;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public void setSourceUrl(String sourceUrl) {
        this.sourceUrl = sourceUrl;
    }
}
