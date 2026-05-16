package clawer.user.dto;

import java.time.Instant;

public class SavedRecommendationSummary {
    private long id;
    private String title;
    private Instant createdAt;
    private String requestSummary;
    private String topRecommendationName;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public String getRequestSummary() { return requestSummary; }
    public void setRequestSummary(String requestSummary) { this.requestSummary = requestSummary; }

    public String getTopRecommendationName() { return topRecommendationName; }
    public void setTopRecommendationName(String topRecommendationName) { this.topRecommendationName = topRecommendationName; }
}
