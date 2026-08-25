package clawer.user.dto;

import java.time.Instant;

/** A stored transcript in full, including every turn. */
public class SavedConversationDetail {
    private long id;
    private String sessionId;
    private String title;
    private Object turnsJson;
    private Instant createdAt;
    private Instant updatedAt;

    public long getId() { return id; }
    public void setId(long id) { this.id = id; }

    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public Object getTurnsJson() { return turnsJson; }
    public void setTurnsJson(Object turnsJson) { this.turnsJson = turnsJson; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
