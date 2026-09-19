package clawer.user.controller;

import clawer.dto.ApiResponse;
import clawer.auth.jwt.AuthenticatedUser;
import clawer.user.dto.SaveRecommendationRequest;
import clawer.user.dto.SavedRecommendationDetail;
import clawer.user.dto.SavedRecommendationSummary;
import clawer.user.dto.SavedUniversityResponse;
import clawer.user.service.SavedRecommendationService;
import clawer.user.service.SavedUniversityService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/user")
public class UserController {

    private final SavedUniversityService savedUniversityService;
    private final SavedRecommendationService savedRecommendationService;

    public UserController(
            SavedUniversityService savedUniversityService,
            SavedRecommendationService savedRecommendationService) {
        this.savedUniversityService = savedUniversityService;
        this.savedRecommendationService = savedRecommendationService;
    }

    @PostMapping("/saved-universities/{canonicalUniversityId}")
    public ResponseEntity<?> save(
            @PathVariable long canonicalUniversityId) {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        savedUniversityService.save(userId, canonicalUniversityId);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(Map.of("saved", true)));
    }

    @DeleteMapping("/saved-universities/{canonicalUniversityId}")
    public ResponseEntity<?> delete(
            @PathVariable long canonicalUniversityId) {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        savedUniversityService.delete(userId, canonicalUniversityId);
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }

    @GetMapping("/saved-universities")
    public ResponseEntity<?> list() {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        List<SavedUniversityResponse> items = savedUniversityService.findByUserId(userId);
        return ResponseEntity.ok(ApiResponse.success(items));
    }

    // ─── Saved Recommendations ────────────────────────────────────────────────

    @PostMapping("/saved-recommendations")
    public ResponseEntity<?> saveRecommendation(
            @RequestBody SaveRecommendationRequest request) {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        if (request.getTitle() == null || request.getTitle().isBlank()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("success", false, "error", "Title is required."));
        }
        if (request.getTitle().length() > 200) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("success", false, "error", "Title must be 200 characters or fewer."));
        }
        if (request.getRequestJson() == null || request.getResultJson() == null) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("success", false, "error", "Request and result are required."));
        }
        long id = savedRecommendationService.save(
                userId,
                request.getTitle().trim(),
                request.getRequestJson(),
                request.getResultJson());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(Map.of("id", id)));
    }

    @GetMapping("/saved-recommendations")
    public ResponseEntity<?> listRecommendations() {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        List<SavedRecommendationSummary> items = savedRecommendationService.findSummariesByUserId(userId);
        return ResponseEntity.ok(ApiResponse.success(items));
    }

    @GetMapping("/saved-recommendations/{id}")
    public ResponseEntity<?> getRecommendation(
            @PathVariable long id) {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        Optional<SavedRecommendationDetail> detail =
                savedRecommendationService.findDetailByIdAndUserId(id, userId);
        if (detail.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("success", false, "error", "Not found."));
        }
        return ResponseEntity.ok(ApiResponse.success(detail.get()));
    }

    @DeleteMapping("/saved-recommendations/{id}")
    public ResponseEntity<?> deleteRecommendation(
            @PathVariable long id) {
        Long userId = resolveUserId();
        if (userId == null) {
            return unauthorized();
        }
        boolean deleted = savedRecommendationService.deleteByIdAndUserId(id, userId);
        if (!deleted) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("success", false, "error", "Not found."));
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    /**
     * The signed-in user, from the request's verified token rather than a session
     * attribute. The filter chain already refuses an anonymous caller on these
     * paths; this stays so the controller keeps its own JSON 401 shape.
     */
    private Long resolveUserId() {
        return AuthenticatedUser.currentId();
    }

    private ResponseEntity<?> unauthorized() {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(Map.of("success", false, "error", "Authentication required."));
    }
}
