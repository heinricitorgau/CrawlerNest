package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import jakarta.servlet.FilterChain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The limits, the address they are keyed by, and what a refused request looks like. */
class RateLimitFilterTest {

    /** A clock the test moves. */
    private static final class MovableClock extends Clock {
        private Instant now = Instant.parse("2026-11-11T00:00:00Z");

        void advance(Duration by) {
            now = now.plus(by);
        }

        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(java.time.ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    private final MovableClock clock = new MovableClock();
    private final RateLimits limits = new RateLimits(true, "127.0.0.1,::1,10.0.0.0/8", 5, 3, 2, 2, clock);
    private final RateLimitFilter filter = new RateLimitFilter(limits);
    private final AtomicInteger passed = new AtomicInteger();
    private final FilterChain chain = (req, res) -> passed.incrementAndGet();

    private MockHttpServletResponse call(String method, String path, String remote, String forwardedFor) throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest(method, path);
        request.setRemoteAddr(remote);
        if (forwardedFor != null) {
            request.addHeader("X-Forwarded-For", forwardedFor);
        }
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(request, response, chain);
        return response;
    }

    @Test
    void theGeneralLimitRefusesWith429AndRetryAfter() throws Exception {
        for (int i = 0; i < 5; i++) {
            assertEquals(200, call("GET", "/api/v1/rankings", "203.0.113.7", null).getStatus());
        }
        MockHttpServletResponse refused = call("GET", "/api/v1/rankings", "203.0.113.7", null);
        assertEquals(429, refused.getStatus());
        assertEquals("60", refused.getHeader("Retry-After"));
        assertTrue(refused.getContentAsString().contains("\"success\":false"), refused.getContentAsString());
        assertEquals(5, passed.get());

        // Another client has its own count; the first is free again once the window ends.
        assertEquals(200, call("GET", "/api/v1/rankings", "203.0.113.8", null).getStatus());
        clock.advance(Duration.ofMinutes(1));
        assertEquals(200, call("GET", "/api/v1/rankings", "203.0.113.7", null).getStatus());
    }

    @Test
    void signInRoutesHaveTheirOwnTighterLimitAndSignupAnHourlyOne() throws Exception {
        for (int i = 0; i < 3; i++) {
            assertEquals(200, call("POST", "/api/v1/auth/signin", "203.0.113.9", null).getStatus());
        }
        assertEquals(429, call("POST", "/api/v1/auth/signin", "203.0.113.9", null).getStatus());
        assertEquals(429, call("POST", "/api/v1/auth/password-reset/request", "203.0.113.9", null).getStatus());

        assertEquals(200, call("POST", "/api/v1/auth/signup", "203.0.113.10", null).getStatus());
        assertEquals(200, call("POST", "/api/v1/auth/signup", "203.0.113.10", null).getStatus());
        MockHttpServletResponse third = call("POST", "/api/v1/auth/signup", "203.0.113.10", null);
        assertEquals(429, third.getStatus());
        clock.advance(Duration.ofMinutes(2));
        // The per-minute window has passed; the hourly one has not.
        assertEquals(429, call("POST", "/api/v1/auth/signup", "203.0.113.10", null).getStatus());
    }

    @Test
    void aForwardedAddressIsBelievedOnlyFromATrustedProxy() throws Exception {
        // From the local Next.js server: keyed by the visitor it names.
        for (int i = 0; i < 3; i++) {
            call("POST", "/api/v1/auth/signin", "127.0.0.1", "198.51.100.1");
        }
        assertEquals(429, call("POST", "/api/v1/auth/signin", "127.0.0.1", "198.51.100.1").getStatus());
        assertEquals(200, call("POST", "/api/v1/auth/signin", "127.0.0.1", "198.51.100.2").getStatus());

        // The right-most untrusted hop counts; what the client wrote to its left does not.
        assertEquals(429, call("POST", "/api/v1/auth/signin", "127.0.0.1", "1.2.3.4, 198.51.100.1, 10.1.2.3").getStatus());

        // From anywhere else the header is ignored: rotating it does not reset the count.
        for (int i = 0; i < 3; i++) {
            call("POST", "/api/v1/auth/signin", "203.0.113.20", "192.0.2." + i);
        }
        assertEquals(429, call("POST", "/api/v1/auth/signin", "203.0.113.20", "192.0.2.99").getStatus());
    }

    @Test
    void theFrontendsOwnServerSideReadsAreNotLimitedByAddress() throws Exception {
        for (int i = 0; i < 50; i++) {
            assertEquals(200, call("GET", "/api/v1/rankings", "127.0.0.1", null).getStatus());
        }
    }

    @Test
    void nonApiPathsAndADisabledLimiterAreLeftAlone() throws Exception {
        for (int i = 0; i < 20; i++) {
            assertEquals(200, call("GET", "/actuator/health", "203.0.113.30", null).getStatus());
        }
        RateLimitFilter off = new RateLimitFilter(new RateLimits(false, "127.0.0.1", 1, 1, 1, 1, clock));
        for (int i = 0; i < 5; i++) {
            MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/v1/auth/signin");
            request.setRemoteAddr("203.0.113.31");
            MockHttpServletResponse response = new MockHttpServletResponse();
            off.doFilter(request, response, chain);
            assertEquals(200, response.getStatus());
        }
    }

    @Test
    void signinFailuresAreCountedPerAccountFromAnyAddressAndClearedBySuccess() {
        assertTrue(limits.signinAllowed("Someone@Example.com").allowed());
        limits.recordSigninFailure("someone@example.com");
        limits.recordSigninFailure(" SOMEONE@example.com ");
        FixedWindowRateLimiter.Decision locked = limits.signinAllowed("someone@example.com");
        assertFalse(locked.allowed());
        assertEquals(RateLimits.SIGNIN_FAILURE_WINDOW.toSeconds(), locked.retryAfterSeconds());

        limits.recordSigninSuccess("someone@example.com");
        assertTrue(limits.signinAllowed("someone@example.com").allowed());

        limits.recordSigninFailure("other@example.com");
        limits.recordSigninFailure("other@example.com");
        clock.advance(RateLimits.SIGNIN_FAILURE_WINDOW);
        assertTrue(limits.signinAllowed("other@example.com").allowed());
    }

    @Test
    void trustedProxiesAcceptAddressesAndRangesOnly() {
        ClientAddressResolver resolver = new ClientAddressResolver(List.of("172.16.0.0/12", "::1"));
        assertTrue(resolver.isTrusted("172.20.0.5"));
        assertFalse(resolver.isTrusted("172.32.0.1"));
        assertTrue(resolver.isTrusted("::1"));
        assertFalse(resolver.isTrusted("example.com"));
        assertFalse(resolver.isTrusted(null));
        assertThrows(IllegalArgumentException.class, () -> new ClientAddressResolver(List.of("localhost")));
        assertThrows(IllegalArgumentException.class, () -> new ClientAddressResolver(List.of("10.0.0.0/33")));
    }
}
