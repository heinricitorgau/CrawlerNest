package clawer.dto;

public class DataQualityDTO {
    private Double recommendationConfidence;
    private String confidenceLabel;
    private String confidenceReason;

    public Double getRecommendationConfidence() { return recommendationConfidence; }
    public void setRecommendationConfidence(Double recommendationConfidence) { this.recommendationConfidence = recommendationConfidence; }

    public String getConfidenceLabel() { return confidenceLabel; }
    public void setConfidenceLabel(String confidenceLabel) { this.confidenceLabel = confidenceLabel; }

    public String getConfidenceReason() { return confidenceReason; }
    public void setConfidenceReason(String confidenceReason) { this.confidenceReason = confidenceReason; }
}
