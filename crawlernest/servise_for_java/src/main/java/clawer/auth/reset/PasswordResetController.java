package clawer.auth.reset;

import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Open endpoints, like signin: the person using them cannot sign in.
 * They sit under /api/v1/auth, which the filter chain leaves open.
 */
@RestController
@RequestMapping("/api/v1/auth/password-reset")
public class PasswordResetController {

    static final String CHANGED = "Your password has been changed. Sign in with the new one.";

    private final PasswordResetService resets;
    private final PasswordResetDelivery delivery;

    public PasswordResetController(PasswordResetService resets, PasswordResetDelivery delivery) {
        this.resets = resets;
        this.delivery = delivery;
    }

    /**
     * What the person is told after asking. The same words whether or not the
     * email has an account -- but true about where the link went: "we've emailed
     * you" from a server that sends no email would be a false promise.
     */
    String requestedMessage() {
        String validity = " The link works once, for " + resets.ttl().toMinutes() + " minutes.";
        return switch (delivery.mode()) {
            case "log" -> "If an account exists for that email, a reset link has been written to the server log "
                    + "(development mode: no email is sent)." + validity;
            case "none" -> "Password reset by email is not set up on this server yet, so no link was sent. "
                    + "Ask the site's administrator to reset your password.";
            default -> "If an account exists for that email, we've sent a link to reset its password." + validity;
        };
    }

    /** Body: {"email": "..."}. */
    @PostMapping("/request")
    public ResponseEntity<?> request(@RequestBody JsonNode body) {
        try {
            resets.request(body.path("email").asText(null));
        } catch (IllegalArgumentException e) {
            return error(HttpStatus.BAD_REQUEST, e.getMessage());
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("message", requestedMessage(), "delivery", delivery.mode())));
    }

    /** Body: {"token": "...", "newPassword": "..."}. */
    @PostMapping("/confirm")
    public ResponseEntity<?> confirm(@RequestBody JsonNode body) {
        try {
            resets.confirm(body.path("token").asText(null), body.path("newPassword").asText(null));
        } catch (PasswordResetService.InvalidTokenException | IllegalArgumentException e) {
            return error(HttpStatus.BAD_REQUEST, e.getMessage());
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("message", CHANGED)));
    }

    private static ResponseEntity<?> error(HttpStatus status, String message) {
        return ResponseEntity.status(status).body(Map.of("success", false, "error", message));
    }
}
