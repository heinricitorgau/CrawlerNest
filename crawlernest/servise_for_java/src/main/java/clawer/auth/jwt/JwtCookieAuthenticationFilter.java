package clawer.auth.jwt;

import java.io.IOException;
import java.util.List;
import java.util.Optional;
import java.util.OptionalInt;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * Reads the token from its cookie and, if it verifies, marks the request authenticated.
 *
 * <p>The cookie is http-only, so no script can read the token -- which is why the
 * token lives there rather than in localStorage, where any injected script could
 * take it. An {@code Authorization: Bearer} header is accepted as well, for callers
 * that are not a browser.
 *
 * <p>A bad or missing token is not an error here: the request simply stays
 * anonymous, and the filter chain decides whether the endpoint allows that. Most of
 * this API is public and must keep answering without a token.
 *
 * <p>Deliberately not a bean: {@link clawer.config.SecurityConfig} constructs it for
 * the security chain. A {@code Filter} bean would also be registered with the servlet
 * container in its own right, and would be pulled into {@code @WebMvcTest} slices
 * that have no reason to carry a token service.
 */
public class JwtCookieAuthenticationFilter extends OncePerRequestFilter {

    public static final String COOKIE_NAME = "crawlernest_token";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtService jwtService;
    private final TokenVersionStore versions;

    public JwtCookieAuthenticationFilter(JwtService jwtService) {
        this(jwtService, null);
    }

    /**
     * With a store, a token is accepted only while its generation is the account's current one and the
     * account is active, which is what lets sign-out-everywhere and a password reset end a token early.
     * Without one (test slices with no database) the signature and expiry are the whole check.
     */
    public JwtCookieAuthenticationFilter(JwtService jwtService, TokenVersionStore versions) {
        this.jwtService = jwtService;
        this.versions = versions;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            tokenOf(request)
                    .flatMap(jwtService::verifyToken)
                    .filter(this::stillCurrent)
                    .map(JwtService.VerifiedToken::user)
                    .ifPresent(JwtCookieAuthenticationFilter::authenticate);
        }
        chain.doFilter(request, response);
    }

    private boolean stillCurrent(JwtService.VerifiedToken token) {
        if (versions == null) {
            return true;
        }
        OptionalInt current = versions.currentVersion(token.user().id());
        return current.isPresent() && current.getAsInt() == token.version();
    }

    private static void authenticate(AuthenticatedUser user) {
        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                user, null, List.of(new SimpleGrantedAuthority("ROLE_USER")));
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    private static Optional<String> tokenOf(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (COOKIE_NAME.equals(cookie.getName())) {
                    return Optional.ofNullable(cookie.getValue());
                }
            }
        }
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith(BEARER_PREFIX)) {
            return Optional.of(header.substring(BEARER_PREFIX.length()));
        }
        return Optional.empty();
    }
}
