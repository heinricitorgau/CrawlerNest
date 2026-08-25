package clawer.user.dto;

import java.time.Instant;

/** One row of the conversation list: enough to pick a transcript without loading it. */
public class SavedConversationSummary {
    private long id;
    private String sessionId;
    private String title;
    private int turnCount;
    /** First user message, truncated; null when the transcript has no user turn. */
    private String preview;
    private Instant createdAt;
    private Instant updatedAt;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public int getTurnCount() { return turnCount; }
    public void setTurnCount(int turnCount) { this.turnCount = turnCount; }

    public String getPreview() { return preview; }
    public void setPreview(String preview) { this.preview = preview; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
