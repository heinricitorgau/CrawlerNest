package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;

import clawer.auth.jwt.AuthenticatedUser;
import clawer.desk.controller.ChatController;
import clawer.desk.controller.EssayController;
import clawer.desk.controller.NarrativeController;
import jakarta.servlet.FilterChain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Model endpoints are charged to the signed-in user by what they can cost; everything else is left alone. */
class ModelCallBudgetFilterTest {

    private static final class MovableClock extends Clock {
        private Instant now = Instant.parse("2026-11-12T00:00:00Z");
        void advance(Duration by) { now = now.plus(by); }
        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    private final MovableClock clock = new MovableClock();
    // 10 model calls a minute, 16 a day.
    private final RateLimits limits = new RateLimits(true, "127.0.0.1", 600, 20, 10, 10, 10, 16, clock);
    private final ModelCallBudgetFilter filter = new ModelCallBudgetFilter(limits);
    private final AtomicInteger reached = new AtomicInteger();
    private final FilterChain chain = (req, res) -> reached.incrementAndGet();

    @AfterEach
    void signOut() {
        SecurityContextHolder.clearContext();
    }

    private static void signIn(long userId) {
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                new AuthenticatedUser(userId, "user" + userId + "@example.com"), null,
                List.of(new SimpleGrantedAuthority("ROLE_USER"))));
    }

    private MockHttpServletResponse call(String method, String path) throws Exception {
        MockHttpServletResponse response = new MockHttpServletResponse();
        filter.doFilter(new MockHttpServletRequest(method, path), response, chain);
        return response;
    }

    @Test
    void aChatTurnCostsFourAndTheBudgetIsTheUsers() throws Exception {
        signIn(1);
        assertEquals(200, call("POST", "/api/v1/user/desk/chat/message").getStatus());
        MockHttpServletResponse second = call("POST", "/api/v1/user/desk/chat/message");
        assertEquals(200, second.getStatus());
        assertEquals("8", second.getHeader("X-Model-Calls-Left-Today"));   // 16 a day, 8 spent
        MockHttpServletResponse third = call("POST", "/api/v1/user/desk/chat/message");   // 8 + 4 > 10 a minute
        assertEquals(429, third.getStatus());
        assertTrue(Integer.parseInt(third.getHeader("Retry-After")) > 0);
        assertEquals(2, reached.get());
        // An essay evaluation (2) still fits this minute; another user has their own budget.
        assertEquals(200, call("POST", "/api/v1/user/desk/essays/evaluate").getStatus());
        signIn(2);
        assertEquals(200, call("POST", "/api/v1/user/desk/chat/message").getStatus());
    }

    @Test
    void theDailyBudgetHoldsAfterTheMinuteHasPassedAndARefusalThereCostsNothing() throws Exception {
        signIn(3);
        for (int i = 0; i < 4; i++) {   // 16 over four minutes: the whole day
            assertEquals(200, call("POST", "/api/v1/user/desk/chat/message").getStatus());
            clock.advance(Duration.ofMinutes(1));
        }
        MockHttpServletResponse refused = call("POST", "/api/v1/user/desk/essays/evaluate");
        assertEquals(429, refused.getStatus());
        assertEquals("0", refused.getHeader("X-Model-Calls-Left-Today"));
        // The minute budget was given back, so nothing is owed there once the day frees up.
        clock.advance(Duration.ofHours(24));
        assertEquals(200, call("POST", "/api/v1/user/desk/chat/message").getStatus());
    }

    @Test
    void otherRequestsAndAnonymousCallersAreNotCharged() throws Exception {
        signIn(4);
        for (int i = 0; i < 30; i++) {
            assertEquals(200, call("GET", "/api/v1/user/desk/chat/message").getStatus());
            assertEquals(200, call("POST", "/api/v1/user/desk/tasks").getStatus());
        }
        assertNull(call("POST", "/api/v1/user/desk/tasks").getHeader("X-Model-Calls-Left-Today"));
        SecurityContextHolder.clearContext();
        for (int i = 0; i < 30; i++) {   // the chain answers these 401; no budget exists to charge
            assertEquals(200, call("POST", "/api/v1/user/desk/chat/message").getStatus());
        }
    }

    @Test
    void everyChargedPathIsARealPostMapping() {
        Set<String> mappings = new HashSet<>();
        for (Class<?> controller : List.of(EssayController.class, NarrativeController.class, ChatController.class)) {
            String base = controller.getAnnotation(RequestMapping.class).value()[0];
            for (var method : controller.getDeclaredMethods()) {
                PostMapping post = method.getAnnotation(PostMapping.class);
                if (post != null) {
                    for (String path : post.value()) {
                        mappings.add(base + path);
                    }
                }
            }
        }
        for (String charged : ModelCallBudgetFilter.MODEL_CALLS.keySet()) {
            assertTrue(mappings.contains(charged), charged + " is charged but no controller maps it");
        }
    }
}
