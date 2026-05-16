package clawer.auth.controller;

import clawer.auth.dto.AuthUserResponse;
import clawer.auth.dto.SigninRequest;
import clawer.auth.dto.SignupRequest;
import clawer.auth.service.AuthService;
import clawer.auth.service.DuplicateEmailException;
import clawer.auth.service.InvalidCredentialsException;
import clawer.dto.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private static final String SESSION_KEY_USER_ID = "user_id";
    private static final String SESSION_KEY_EMAIL   = "email";

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @PostMapping("/signup")
    public ResponseEntity<?> signup(@RequestBody SignupRequest request) {
        try {
            AuthUserResponse user = authService.signup(request);
            return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(user));
        } catch (DuplicateEmailException e) {
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(error("An account with this email already exists."));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(error(e.getMessage()));
        }
    }

    @PostMapping("/signin")
    public ResponseEntity<?> signin(
            @RequestBody SigninRequest request,
            HttpServletRequest httpRequest) {
        try {
            AuthUserResponse user = authService.signin(request);

            // Session-fixation prevention: discard any pre-existing session.
            HttpSession existing = httpRequest.getSession(false);
            if (existing != null) {
                existing.invalidate();
            }

            HttpSession session = httpRequest.getSession(true);
            session.setAttribute(SESSION_KEY_USER_ID, user.getId());
            session.setAttribute(SESSION_KEY_EMAIL, user.getEmail());

            return ResponseEntity.ok(ApiResponse.success(user));
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(error("Invalid email or password."));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(error(e.getMessage()));
        }
    }

    @PostMapping("/signout")
    public ResponseEntity<?> signout(HttpServletRequest httpRequest) {
        HttpSession session = httpRequest.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("message", "Signed out.")));
    }

    @GetMapping("/me")
    public ResponseEntity<?> me(HttpServletRequest httpRequest) {
        HttpSession session = httpRequest.getSession(false);
        if (session == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(error("No active session."));
        }

        Long userId = (Long) session.getAttribute(SESSION_KEY_USER_ID);
        String email = (String) session.getAttribute(SESSION_KEY_EMAIL);

        if (userId == null || email == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(error("No active session."));
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", userId);
        payload.put("email", email);

        return ResponseEntity.ok(ApiResponse.success(payload));
    }

    private static Map<String, Object> error(String message) {
        return Map.of("success", false, "error", message);
    }
}
