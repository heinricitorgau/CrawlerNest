package clawer.auth.controller;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

import clawer.auth.dto.AuthUserResponse;
import clawer.auth.dto.SigninRequest;
import clawer.auth.jwt.AuthenticatedUser;
import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import clawer.auth.service.AuthService;
import clawer.auth.service.InvalidCredentialsException;
import clawer.dto.ApiResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * How the token reaches the browser, and how it stops reaching it.
 *
 * <p>The cookie's flags are the security property here, not a detail: http-only
 * keeps the token out of reach of any injected script, and SameSite=Strict is
 * what makes disabling CSRF protection safe, since the browser attaches the
 * cookie to nothing another site starts.
 */
class AuthControllerCookieTest {

    private static final String SECRET = "a-controller-test-secret-long-enough-for-hs256";

    private final AuthService authService = mock(AuthService.class);
    private final JwtService jwtService = new JwtService(SECRET, Duration.ofHours(12));

    private AuthController controller(boolean cookieSecure) {
        return new AuthController(authService, jwtService, cookieSecure);
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    private static String setCookie(ResponseEntity<?> response) {
        return response.getHeaders().getFirst(HttpHeaders.SET_COOKIE);
    }

    private void credentialsAccepted() {
        when(authService.signin(any())).thenReturn(
                new AuthUserResponse(42L, "someone@example.com", Instant.now(), Instant.now()));
    }

    @Test
    void signinSetsAnHttpOnlyStrictCookieHoldingAVerifiableToken() {
        credentialsAccepted();

        ResponseEntity<?> response = controller(false).signin(new SigninRequest());
        String cookie = setCookie(response);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertNotNull(cookie);
        assertTrue(cookie.startsWith(JwtCookieAuthenticationFilter.COOKIE_NAME + "="), cookie);
        assertTrue(cookie.contains("HttpOnly"), cookie);
        assertTrue(cookie.contains("SameSite=Strict"), cookie);
        assertTrue(cookie.contains("Path=/"), cookie);

        String token = cookie.substring(cookie.indexOf('=') + 1, cookie.indexOf(';'));
        assertEquals(Optional.of(new AuthenticatedUser(42L, "someone@example.com")), jwtService.verify(token));
    }

    @Test
    void theCookieIsSecureOnlyWhenConfiguredSo() {
        credentialsAccepted();

        // A local plain-http run must be able to sign in; a TLS deployment sets
        // the flag and the token never travels in the clear.
        assertFalse(setCookie(controller(false).signin(new SigninRequest())).contains("Secure"));
        assertTrue(setCookie(controller(true).signin(new SigninRequest())).contains("Secure"));
    }

    @Test
    void badCredentialsGet401AndNoCookie() {
        when(authService.signin(any())).thenThrow(new InvalidCredentialsException());

        ResponseEntity<?> response = controller(false).signin(new SigninRequest());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        assertNull(setCookie(response), "a failed sign-in must not hand out a token");
    }

    @Test
    void signoutExpiresTheCookieRatherThanLeavingItInPlace() {
        String cookie = setCookie(controller(false).signout());

        assertNotNull(cookie);
        assertTrue(cookie.startsWith(JwtCookieAuthenticationFilter.COOKIE_NAME + "=;"), cookie);
        assertTrue(cookie.contains("Max-Age=0"), cookie);
        // Same flags, or the browser treats it as a different cookie and keeps the old one.
        assertTrue(cookie.contains("HttpOnly"), cookie);
        assertTrue(cookie.contains("SameSite=Strict"), cookie);
        assertTrue(cookie.contains("Path=/"), cookie);
    }

    @Test
    void meReportsTheTokenIdentity() {
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(
                        new AuthenticatedUser(42L, "someone@example.com"), null, List.of()));

        ResponseEntity<?> response = controller(false).me();

        assertEquals(HttpStatus.OK, response.getStatusCode());
        ApiResponse<?> body = (ApiResponse<?>) response.getBody();
        assertEquals(Map.of("id", 42L, "email", "someone@example.com"), body.getData());
    }

    @Test
    void meWithoutATokenIs401() {
        assertEquals(HttpStatus.UNAUTHORIZED, controller(false).me().getStatusCode());
    }
}
