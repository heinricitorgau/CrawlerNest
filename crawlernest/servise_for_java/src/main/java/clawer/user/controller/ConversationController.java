package clawer.user.controller;

import clawer.dto.ApiResponse;
import clawer.user.dto.SaveConversationRequest;
import clawer.user.dto.SavedConversationDetail;
import clawer.user.dto.SavedConversationSummary;
import clawer.user.service.ConversationService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Saved agent conversations, scoped to the signed-in user.
 *
 * <p>Sits alongside UserController under /api/v1/user and resolves identity the
 * same way: the user id comes from the session, never from the request body, so
 * a caller cannot name someone else's account. Every read and delete is
 * additionally filtered by that id in SQL, so an id guessed from another
 * account's transcript answers 404 rather than returning it.
 *
 * <p>This is a write path into warehouse.saved_conversation only. It reaches no
 * pipeline table, and the analytics and ranking read APIs are untouched by it.
 */
@RestController
@RequestMapping("/api/v1/user/conversations")
public class ConversationController {

    private static final String SESSION_KEY_USER_ID = "user_id";

    private final ConversationService conversationService;

    public ConversationController(ConversationService conversationService) {
        this.conversationService = conversationService;
    }

    @PostMapping
    public ResponseEntity<?> save(
            @RequestBody SaveConversationRequest request,
            HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }

        String sessionId = request.getSessionId();
        if (sessionId == null || sessionId.isBlank()) {
            return badRequest("Session id is required.");
        }
        sessionId = sessionId.trim();
        if (sessionId.length() > ConversationService.MAX_SESSION_ID_LENGTH) {
            return badRequest("Session id must be "
                    + ConversationService.MAX_SESSION_ID_LENGTH + " characters or fewer.");
        }

        if (request.getTitle() != null
                && request.getTitle().length() > ConversationService.MAX_TITLE_LENGTH) {
            return badRequest("Title must be "
                    + ConversationService.MAX_TITLE_LENGTH + " characters or fewer.");
        }

        String turnsError = ConversationService.validateTurns(request.getTurnsJson());
        if (turnsError != null) {
            return badRequest(turnsError);
        }

        long id;
        try {
            id = conversationService.save(
                    userId,
                    sessionId,
                    request.getTitle(),
                    request.getTurnsJson());
        } catch (IllegalArgumentException e) {
            // Size ceiling: a request the client can fix by sending less.
            return badRequest(e.getMessage());
        }
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(Map.of("id", id)));
    }

    @GetMapping
    public ResponseEntity<?> list(HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        List<SavedConversationSummary> items = conversationService.findSummariesByUserId(userId);
        return ResponseEntity.ok(ApiResponse.success(items));
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(
            @PathVariable long id,
            HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        Optional<SavedConversationDetail> detail =
                conversationService.findDetailByIdAndUserId(id, userId);
        if (detail.isEmpty()) {
            return notFound();
        }
        return ResponseEntity.ok(ApiResponse.success(detail.get()));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> delete(
            @PathVariable long id,
            HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        if (!conversationService.deleteByIdAndUserId(id, userId)) {
            return notFound();
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    private Long resolveUserId(HttpServletRequest httpRequest) {
        HttpSession session = httpRequest.getSession(false);
        if (session == null) {
            return null;
        }
        return (Long) session.getAttribute(SESSION_KEY_USER_ID);
    }

    private ResponseEntity<?> unauthorized() {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(Map.of("success", false, "error", "Authentication required."));
    }

    /** Also the answer for another user's row: absent and forbidden look alike on purpose. */
    private ResponseEntity<?> notFound() {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(Map.of("success", false, "error", "Not found."));
    }

    private ResponseEntity<?> badRequest(String error) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(Map.of("success", false, "error", error));
    }
}
