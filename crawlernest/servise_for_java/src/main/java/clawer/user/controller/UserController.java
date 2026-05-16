package clawer.user.controller;

import clawer.dto.ApiResponse;
import clawer.user.dto.SavedUniversityResponse;
import clawer.user.service.SavedUniversityService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/user")
public class UserController {

    private static final String SESSION_KEY_USER_ID = "user_id";

    private final SavedUniversityService savedUniversityService;

    public UserController(SavedUniversityService savedUniversityService) {
        this.savedUniversityService = savedUniversityService;
    }

    @PostMapping("/saved-universities/{canonicalUniversityId}")
    public ResponseEntity<?> save(
            @PathVariable long canonicalUniversityId,
            HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        savedUniversityService.save(userId, canonicalUniversityId);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(Map.of("saved", true)));
    }

    @DeleteMapping("/saved-universities/{canonicalUniversityId}")
    public ResponseEntity<?> delete(
            @PathVariable long canonicalUniversityId,
            HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        savedUniversityService.delete(userId, canonicalUniversityId);
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }

    @GetMapping("/saved-universities")
    public ResponseEntity<?> list(HttpServletRequest httpRequest) {
        Long userId = resolveUserId(httpRequest);
        if (userId == null) {
            return unauthorized();
        }
        List<SavedUniversityResponse> items = savedUniversityService.findByUserId(userId);
        return ResponseEntity.ok(ApiResponse.success(items));
    }

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
}
