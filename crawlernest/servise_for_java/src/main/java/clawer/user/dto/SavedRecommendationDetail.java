package clawer.user.dto;

import java.time.Instant;

public class SavedRecommendationDetail {
    private long id;
    private String title;
    private Object requestJson;
    private Object resultJson;
    private Instant createdAt;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public Object getRequestJson() { return requestJson; }
    public void setRequestJson(Object requestJson) { this.requestJson = requestJson; }

    public Object getResultJson() { return resultJson; }
    public void setResultJson(Object resultJson) { this.resultJson = resultJson; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
