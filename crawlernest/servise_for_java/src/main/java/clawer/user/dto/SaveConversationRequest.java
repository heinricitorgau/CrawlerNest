package clawer.user.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

/**
 * Body of {@code POST /api/v1/user/conversations}.
 *
 * <p>{@code sessionId} identifies the chat, not the row: saving the same session
 * twice updates the stored transcript rather than creating a second copy. The
 * browser generates it and keeps it for the life of the chat.
 *
 * <p>{@code title} is optional. When it is blank the service derives one from the
 * first user turn, so the save button never has to stop and prompt for a name.
 */
public class SaveConversationRequest {

    private String sessionId;
    private String title;

    @JsonProperty("turns")
    private JsonNode turnsJson;

    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    /** A JSON array of {@code {"role": "...", "content": "..."}} objects. */
    public JsonNode getTurnsJson() { return turnsJson; }
    public void setTurnsJson(JsonNode turnsJson) { this.turnsJson = turnsJson; }
}
