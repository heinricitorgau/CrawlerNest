package clawer.desk.model;

/**
 * One chat-completion call to the model behind the desk (essay scoring, narrative
 * themes, resonance). An interface so the
 * tests can stand in for the model without a network.
 */
public interface DeskModelClient {

    record Reply(String text, String modelName) {}

    /** Thrown when no model is configured, or the configured one cannot be reached. Nothing is stored. */
    class UnavailableException extends RuntimeException {
        public UnavailableException(String message) {
            super(message);
        }
    }

    Reply complete(String systemPrompt, String userPrompt);

    /**
     * The assistant's next message in a conversation that may call tools.
     *
     * @param message the assistant message as the provider returned it:
     *                {@code content} and, when it called tools, {@code tool_calls}
     */
    record ChatTurn(com.fasterxml.jackson.databind.JsonNode message, String modelName) {}

    /**
     * @param messages OpenAI-format messages, system first
     * @param tools    OpenAI-format tool definitions, sent as is
     */
    ChatTurn chat(com.fasterxml.jackson.databind.node.ArrayNode messages, com.fasterxml.jackson.databind.JsonNode tools);
}
