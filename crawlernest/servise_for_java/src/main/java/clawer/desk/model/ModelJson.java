package clawer.desk.model;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/** Reading the JSON object out of a model's reply. */
public final class ModelJson {

    private ModelJson() {}

    /** The model answered, twice, with something that cannot be used. Nothing is stored. */
    public static class UnreadableReplyException extends RuntimeException {
        public UnreadableReplyException(String message) {
            super(message);
        }
    }

    /** The JSON object in the reply, tolerating a Markdown fence or a sentence around it. */
    public static JsonNode readObject(ObjectMapper objectMapper, String text) {
        if (text == null) {
            throw new UnreadableReplyException("The reply was empty.");
        }
        int open = text.indexOf('{');
        int close = text.lastIndexOf('}');
        if (open < 0 || close < open) {
            throw new UnreadableReplyException("The reply contained no JSON object.");
        }
        JsonNode node;
        try {
            node = objectMapper.readTree(text.substring(open, close + 1));
        } catch (Exception e) {
            throw new UnreadableReplyException("The reply was not valid JSON.");
        }
        if (!node.isObject()) {
            throw new UnreadableReplyException("The reply was not a JSON object.");
        }
        return node;
    }
}
