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
}
