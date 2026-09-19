package clawer.auth.controller;

import clawer.auth.dto.AuthUserResponse;
import clawer.auth.dto.SigninRequest;
import clawer.auth.dto.SignupRequest;
import clawer.auth.service.AuthService;
import clawer.auth.service.DuplicateEmailException;
import clawer.auth.service.InvalidCredentialsException;
import clawer.auth.jwt.AuthenticatedUser;
import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import clawer.dto.ApiResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;
    private final JwtService jwtService;
    private final boolean cookieSecure;

    public AuthController(
            AuthService authService,
            JwtService jwtService,
            @org.springframework.beans.factory.annotation.Value("${crawlernest.jwt.cookie-secure:false}") boolean cookieSecure
    ) {
        this.authService = authService;
        this.jwtService = jwtService;
        // Off by default so a plain-http local run can sign in; a deployment sets
        // crawlernest.jwt.cookie-secure=true and the cookie never leaves TLS.
        this.cookieSecure = cookieSecure;
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
    public ResponseEntity<?> signin(@RequestBody SigninRequest request) {
        try {
            AuthUserResponse user = authService.signin(request);

            // The identity now travels in a signed token rather than a server-side
            // session, so any instance of the API accepts it. Session fixation has
            // no purchase on a token the server did not take from the request.
            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE, tokenCookie(jwtService.issue(user.getId(), user.getEmail())).toString())
                    .body(ApiResponse.success(user));
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(error("Invalid email or password."));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(error(e.getMessage()));
        }
    }

    /**
     * Clears the cookie. A token already in someone's hands stays valid until it
     * expires -- that is the trade a stateless token makes, and why the lifetime is
     * hours rather than weeks.
     */
    @PostMapping("/signout")
    public ResponseEntity<?> signout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, expiredTokenCookie().toString())
                .body(ApiResponse.success(Map.of("message", "Signed out.")));
    }

    /** Open on purpose: this is how the frontend asks whether anyone is signed in. */
    @GetMapping("/me")
    public ResponseEntity<?> me() {
        return AuthenticatedUser.current()
                .<ResponseEntity<?>>map(user -> {
                    Map<String, Object> payload = new LinkedHashMap<>();
                    payload.put("id", user.id());
                    payload.put("email", user.email());
                    return ResponseEntity.ok(ApiResponse.success(payload));
                })
                .orElseGet(() -> ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(error("Not signed in.")));
    }

    private ResponseCookie tokenCookie(String token) {
        return baseCookie(token).maxAge(jwtService.tokenTtl()).build();
    }

    private ResponseCookie expiredTokenCookie() {
        return baseCookie("").maxAge(0).build();
    }

    private ResponseCookie.ResponseCookieBuilder baseCookie(String value) {
        return ResponseCookie.from(JwtCookieAuthenticationFilter.COOKIE_NAME, value)
                // http-only: no script can read the token, which is the reason it
                // lives in a cookie rather than in storage the page can reach.
                .httpOnly(true)
                .secure(cookieSecure)
                // Strict is what removes cross-site request forgery here: the
                // browser attaches this cookie to no request another site starts.
                .sameSite("Strict")
                .path("/");
    }

    private static Map<String, Object> error(String message) {
        return Map.of("success", false, "error", message);
    }
}
