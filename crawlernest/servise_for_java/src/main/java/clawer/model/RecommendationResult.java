package clawer.model;

/**
 * Represents the result of a recommendation process, including the recommended University
 * and a calculated match score.
 */
public class RecommendationResult {
    private University university;
    private Double matchScore;
    private String rationale;

    public RecommendationResult() {
    }

    public RecommendationResult(University university, Double matchScore, String rationale) {
        this.university = university;
        this.matchScore = matchScore;
        this.rationale = rationale;
    }

    public University getUniversity() { return university; }
    public void setUniversity(University university) { this.university = university; }

    public Double getMatchScore() { return matchScore; }
    public void setMatchScore(Double matchScore) { this.matchScore = matchScore; }

    public String getRationale() { return rationale; }
    public void setRationale(String rationale) { this.rationale = rationale; }
}
