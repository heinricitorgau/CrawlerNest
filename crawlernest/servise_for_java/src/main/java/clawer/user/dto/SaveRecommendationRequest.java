package clawer.user.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;

public class SaveRecommendationRequest {
    private String title;

    @JsonProperty("request")
    private JsonNode requestJson;

    @JsonProperty("result")
    private JsonNode resultJson;

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public JsonNode getRequestJson() { return requestJson; }
    public void setRequestJson(JsonNode requestJson) { this.requestJson = requestJson; }

    public JsonNode getResultJson() { return resultJson; }
    public void setResultJson(JsonNode resultJson) { this.resultJson = resultJson; }
}
