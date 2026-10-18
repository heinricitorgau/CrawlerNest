package clawer.desk.support;

import clawer.desk.model.DeskModelClient;
import clawer.desk.model.ModelJson;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.Map;

/**
 * Error bodies for the desk endpoints, in the {@code {"success": false, "error": "..."}}
 * shape the user controllers already answer with.
 *
 * <p>The services validate before they write, so the two database exceptions are
 * the backstop for a race (two tabs adding the same school) or a check the
 * service does not repeat. Their text is not passed on: it names constraints and
 * columns.
 */
@RestControllerAdvice(basePackages = "clawer.desk")
public class DeskExceptionHandler {

    @ExceptionHandler(DeskException.class)
    public ResponseEntity<Map<String, Object>> refused(DeskException e) {
        return body(e.status(), e.getMessage());
    }

    @ExceptionHandler(DuplicateKeyException.class)
    public ResponseEntity<Map<String, Object>> duplicate(DuplicateKeyException e) {
        return body(HttpStatus.CONFLICT, "That is already on your desk.");
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<Map<String, Object>> integrity(DataIntegrityViolationException e) {
        return body(HttpStatus.BAD_REQUEST, "The change conflicts with your existing data.");
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> unreadable(HttpMessageNotReadableException e) {
        return body(HttpStatus.BAD_REQUEST, "Body must be valid JSON.");
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Map<String, Object>> badParameter(MethodArgumentTypeMismatchException e) {
        return body(HttpStatus.BAD_REQUEST, "Invalid value for " + e.getName() + ".");
    }

    /** No model configured, or it could not be reached. Nothing was stored. */
    @ExceptionHandler(DeskModelClient.UnavailableException.class)
    public ResponseEntity<Map<String, Object>> modelUnavailable(DeskModelClient.UnavailableException e) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("success", false, "code", "MODEL_UNAVAILABLE", "error", e.getMessage()));
    }

    /** The model's reply could not be used, even after a retry. Nothing was stored. */
    @ExceptionHandler(ModelJson.UnreadableReplyException.class)
    public ResponseEntity<Map<String, Object>> modelReplyUnreadable(ModelJson.UnreadableReplyException e) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of("success", false, "code", "MODEL_REPLY_UNREADABLE", "error", e.getMessage()));
    }

    private static ResponseEntity<Map<String, Object>> body(HttpStatus status, String error) {
        return ResponseEntity.status(status).body(Map.of("success", false, "error", error));
    }
}
