package clawer.security;

import java.io.IOException;
import java.util.Map;
import java.util.Optional;

import org.springframework.web.filter.OncePerRequestFilter;

import clawer.auth.jwt.AuthenticatedUser;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Charges a signed-in user's model budget before an endpoint that calls the model runs.
 *
 * <p>The general limit is 600 requests a minute per address, which is right for reading rankings and far too wide for
 * a request that makes up to four model calls. These endpoints are charged by what they can cost: the weight is the
 * most model calls one request may make (an essay evaluation retries once; a Tassel chat turn runs up to three tool
 * rounds and an answer). The budget is the account's -- per minute and per day, over sliding windows -- so it follows
 * the user across addresses and cannot be doubled by timing requests around a window boundary.
 *
 * <p>Runs after the token filter, because it needs to know who is asking. An anonymous request is passed on
 * untouched: the endpoints are under /api/v1/user/**, and the chain answers it 401 without any model call.
 *
 * <p>A path added here must be an endpoint that calls the model; ModelCallBudgetFilterTest checks the list against
 * the controllers' mappings.
 */
public class ModelCallBudgetFilter extends OncePerRequestFilter {

    /** POST path to the most model calls one request may make. */
    public static final Map<String, Integer> MODEL_CALLS = Map.of(
            "/api/v1/user/desk/essays/evaluate", 2,
            "/api/v1/user/desk/story/generate", 2,
            "/api/v1/user/desk/story/themes/generate", 2,
            "/api/v1/user/desk/story/resonance/generate", 2,
            "/api/v1/user/desk/chat/message", 4);

    private final RateLimits limits;

    public ModelCallBudgetFilter(RateLimits limits) {
        this.limits = limits;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !limits.enabled() || !"POST".equalsIgnoreCase(request.getMethod()) || weightOf(request) == null;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Optional<AuthenticatedUser> user = AuthenticatedUser.current();
        if (user.isEmpty()) {
            chain.doFilter(request, response);
            return;
        }
        long userId = user.get().id();
        FixedWindowRateLimiter.Decision decision = limits.spendModelCalls(userId, weightOf(request));
        response.setHeader("X-Model-Calls-Left-Today", Integer.toString(limits.modelCallsLeftToday(userId)));
        if (!decision.allowed()) {
            RateLimitFilter.refuse(response, decision);
            return;
        }
        chain.doFilter(request, response);
    }

    private static Integer weightOf(HttpServletRequest request) {
        String uri = request.getRequestURI();
        String context = request.getContextPath();
        String path = context != null && !context.isEmpty() && uri.startsWith(context) ? uri.substring(context.length()) : uri;
        return MODEL_CALLS.get(path);
    }
}
