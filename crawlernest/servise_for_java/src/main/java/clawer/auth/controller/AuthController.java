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
import clawer.auth.jwt.TokenVersionStore;
import clawer.dto.ApiResponse;
import clawer.security.FixedWindowRateLimiter;
import clawer.security.RateLimits;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.OptionalInt;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;
    private final JwtService jwtService;
    private final boolean cookieSecure;
    private final TokenVersionStore tokenVersions;
    private final RateLimits rateLimits;

    /** For unit tests: no token generations and no sign-in throttle. */
    public AuthController(AuthService authService, JwtService jwtService, boolean cookieSecure) {
        this(authService, jwtService, cookieSecure, null, null);
    }

    public AuthController(AuthService authService, JwtService jwtService, boolean cookieSecure,
                          TokenVersionStore tokenVersions, RateLimits rateLimits) {
        this.authService = authService;
        this.jwtService = jwtService;
        this.cookieSecure = cookieSecure;
        this.tokenVersions = tokenVersions;
        this.rateLimits = rateLimits;
    }

    @Autowired
    public AuthController(
            AuthService authService,
            JwtService jwtService,
            @Value("${crawlernest.jwt.cookie-secure:auto}") String cookieSecure,
            @Value("${crawlernest.password-reset.link-base:http://localhost:3000}") String publicBaseUrl,
            ObjectProvider<TokenVersionStore> tokenVersions,
            ObjectProvider<RateLimits> rateLimits
    ) {
        this(authService, jwtService, resolveCookieSecure(cookieSecure, publicBaseUrl),
                tokenVersions.getIfAvailable(), rateLimits.getIfAvailable());
    }

    /**
     * {@code auto} (the default) sets {@code Secure} exactly when the site's public address
     * ({@code CRAWLERNEST_PUBLIC_BASE_URL}) is https, so a deployment behind TLS gets it without a second
     * setting and a plain-http local run can still sign in. {@code false} with an https address is refused:
     * that combination sends the token in the clear on any http hop and is never what anyone meant.
     */
    static boolean resolveCookieSecure(String setting, String publicBaseUrl) {
        String value = setting == null ? "" : setting.trim().toLowerCase(Locale.ROOT);
        boolean httpsSite = publicBaseUrl != null && publicBaseUrl.trim().toLowerCase(Locale.ROOT).startsWith("https://");
        switch (value) {
            case "", "auto":
                return httpsSite;
            case "true":
                return true;
            case "false":
                if (httpsSite) {
                    throw new IllegalStateException("crawlernest.jwt.cookie-secure=false while the public base URL "
                            + "is https (" + publicBaseUrl + "). Unset CRAWLERNEST_JWT_COOKIE_SECURE or set it to true.");
                }
                return false;
            default:
                throw new IllegalStateException("crawlernest.jwt.cookie-secure must be auto, true or false; got " + setting);
        }
    }

    boolean cookieSecure() {
        return cookieSecure;
    }

    /** What sign-up answers for a new email and for a taken one alike. */
    public static final String SIGNUP_ACCEPTED =
            "If this email was not already registered, its account is ready. Sign in to continue.";

    /**
     * 202 with the same body whether the email was new or already registered, so sign-up cannot be used
     * to find out who has an account. Sign-up issues no token either way; whoever owns the email signs in
     * with their own password (or resets it). Invalid input is still a 400, since it says nothing about
     * any account.
     */
    @PostMapping("/signup")
    public ResponseEntity<?> signup(@RequestBody SignupRequest request) {
        try {
            authService.signup(request);
        } catch (DuplicateEmailException | DataIntegrityViolationException e) {
            // Taken, or taken by a concurrent sign-up between the check and the insert: the same answer.
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(error(e.getMessage()));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success(Map.of("message", SIGNUP_ACCEPTED)));
    }

    @PostMapping("/signin")
    public ResponseEntity<?> signin(@RequestBody SigninRequest request) {
        String attempted = request.getEmail();
        if (rateLimits != null) {
            FixedWindowRateLimiter.Decision allowed = rateLimits.signinAllowed(attempted);
            if (!allowed.allowed()) {
                // Checked before the password: past the limit, a right guess is refused like a wrong one.
                return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                        .header(HttpHeaders.RETRY_AFTER, Long.toString(allowed.retryAfterSeconds()))
                        .body(error("Too many failed sign-ins for this account. Try again in "
                                + allowed.retryAfterSeconds() + " seconds."));
            }
        }
        try {
            AuthUserResponse user = authService.signin(request);
            if (rateLimits != null) {
                rateLimits.recordSigninSuccess(attempted);
            }
            int version = 0;
            if (tokenVersions != null) {
                OptionalInt current = tokenVersions.currentVersion(user.getId());
                if (current.isEmpty()) {
                    // Deactivated between the password check and here: no token for an account the filter refuses.
                    return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(error("Invalid email or password."));
                }
                version = current.getAsInt();
            }

            // The identity now travels in a signed token rather than a server-side
            // session, so any instance of the API accepts it. Session fixation has
            // no purchase on a token the server did not take from the request.
            return ResponseEntity.ok()
                    .header(HttpHeaders.SET_COOKIE,
                            tokenCookie(jwtService.issue(user.getId(), user.getEmail(), version)).toString())
                    .body(ApiResponse.success(user));
        } catch (InvalidCredentialsException e) {
            if (rateLimits != null) {
                rateLimits.recordSigninFailure(attempted);
            }
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(error("Invalid email or password."));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(error(e.getMessage()));
        }
    }

    /**
     * Clears this browser's cookie. Other tokens for the account -- other browsers,
     * or one copied out of this one -- stay valid; {@link #signoutEverywhere} ends them.
     */
    @PostMapping("/signout")
    public ResponseEntity<?> signout() {
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, expiredTokenCookie().toString())
                .body(ApiResponse.success(Map.of("message", "Signed out.")));
    }

    /**
     * Ends every token issued to the signed-in account, this one included, by moving the account to a new
     * token generation (V009). The answer also clears this browser's cookie.
     */
    @PostMapping("/signout-everywhere")
    public ResponseEntity<?> signoutEverywhere() {
        Optional<AuthenticatedUser> user = AuthenticatedUser.current();
        if (user.isEmpty()) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(error("Not signed in."));
        }
        if (tokenVersions == null || tokenVersions.revokeAll(user.get().id()).isEmpty()) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(error("Signing out everywhere is not available."));
        }
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, expiredTokenCookie().toString())
                .body(ApiResponse.success(Map.of("message", "Signed out on every device.")));
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
