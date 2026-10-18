package clawer.desk.essay;

/**
 * One chat-completion call to whichever model scores essays. An interface so the
 * tests can stand in for the model without a network.
 */
public interface EssayModelClient {

    record Reply(String text, String modelName) {}

    /** Thrown when no model is configured, or the configured one cannot be reached. Nothing is stored. */
    class UnavailableException extends RuntimeException {
        public UnavailableException(String message) {
            super(message);
        }
    }

    Reply complete(String systemPrompt, String userPrompt);
}
