package clawer.security;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Answers 429 with {@code Retry-After} when a client is over one of {@link RateLimits}' limits.
 *
 * <p>A request from a trusted proxy that names no client ({@link ClientAddressResolver#INTERNAL}) is the
 * frontend's own server-side work, and is not limited by address: one key for all of it would throttle
 * every visitor at once. The Next.js auth proxy forwards the browser's address, so sign-in, sign-up and
 * reset requests from visitors are keyed by visitor. The per-account sign-in failure limit applies to
 * every caller regardless (AuthController).
 */
public class RateLimitFilter extends OncePerRequestFilter {

    private final RateLimits limits;

    public RateLimitFilter(RateLimits limits) {
        this.limits = limits;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !limits.enabled() || !path(request).startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String client = limits.addresses().resolve(request);
        if (ClientAddressResolver.INTERNAL.equals(client)) {
            chain.doFilter(request, response);
            return;
        }
        String path = path(request);
        boolean post = "POST".equalsIgnoreCase(request.getMethod());

        if (post && isAuthWrite(path)) {
            FixedWindowRateLimiter.Decision decision = limits.auth().tryAcquire(client);
            if (decision.allowed() && path.equals("/api/v1/auth/signup")) {
                decision = limits.signup().tryAcquire(client);
            }
            if (!decision.allowed()) {
                refuse(response, decision);
                return;
            }
        } else {
            FixedWindowRateLimiter.Decision decision = limits.api().tryAcquire(client);
            if (!decision.allowed()) {
                refuse(response, decision);
                return;
            }
        }
        chain.doFilter(request, response);
    }

    static boolean isAuthWrite(String path) {
        return path.equals("/api/v1/auth/signin")
                || path.equals("/api/v1/auth/signup")
                || path.startsWith("/api/v1/auth/password-reset/");
    }

    private static String path(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String context = request.getContextPath();
        return context != null && !context.isEmpty() && uri.startsWith(context) ? uri.substring(context.length()) : uri;
    }

    static void refuse(HttpServletResponse response, FixedWindowRateLimiter.Decision decision) throws IOException {
        response.setStatus(429);
        response.setHeader("Retry-After", Long.toString(decision.retryAfterSeconds()));
        response.setContentType("application/json");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.getWriter().write("{\"success\":false,\"error\":\"Too many requests. Try again in "
                + decision.retryAfterSeconds() + " seconds.\"}");
    }
}
