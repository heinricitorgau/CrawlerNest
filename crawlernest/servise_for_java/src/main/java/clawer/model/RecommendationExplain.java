package clawer.model;

import java.util.List;

public class RecommendationExplain {
    private Double fitScore;
    private RecommendationExplainDimensions dimensions;
    private List<String> reasons;
    private List<String> warnings;

    public Double getFitScore() {
        return fitScore;
    }

    public void setFitScore(Double fitScore) {
        this.fitScore = fitScore;
    }

    public RecommendationExplainDimensions getDimensions() {
        return dimensions;
    }

    public void setDimensions(RecommendationExplainDimensions dimensions) {
        this.dimensions = dimensions;
    }

    public List<String> getReasons() {
        return reasons;
    }

    public void setReasons(List<String> reasons) {
        this.reasons = reasons;
    }

    public List<String> getWarnings() {
        return warnings;
    }

    public void setWarnings(List<String> warnings) {
        this.warnings = warnings;
    }
}
