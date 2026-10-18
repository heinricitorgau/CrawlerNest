package clawer.desk.support;

import org.springframework.http.HttpStatus;

/** A request the desk endpoints refuse, with the status and the message the caller sees. */
public class DeskException extends RuntimeException {

    private final HttpStatus status;

    private DeskException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }

    public static DeskException badRequest(String message) {
        return new DeskException(HttpStatus.BAD_REQUEST, message);
    }

    /** Also the answer for another user's row: absent and forbidden look alike on purpose. */
    public static DeskException notFound() {
        return new DeskException(HttpStatus.NOT_FOUND, "Not found.");
    }

    public static DeskException unauthenticated() {
        return new DeskException(HttpStatus.UNAUTHORIZED, "Authentication required.");
    }

    public static DeskException conflict(String message) {
        return new DeskException(HttpStatus.CONFLICT, message);
    }
}
