package clawer.auth.jwt;

import java.util.Optional;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * Who a request is from: the identity carried by its token.
 *
 * <p>Controllers read it here rather than from a session attribute, so there is one
 * answer to "which user is this" and it comes from something signed.
 */
public record AuthenticatedUser(long id, String email) {

    /** The current request's user, or empty when it carries no usable token. */
    public static Optional<AuthenticatedUser> current() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            return Optional.empty();
        }
        Object principal = authentication.getPrincipal();
        return principal instanceof AuthenticatedUser user ? Optional.of(user) : Optional.empty();
    }

    /** The current user's id, or null -- the shape the controllers already expect. */
    public static Long currentId() {
        return current().map(AuthenticatedUser::id).orElse(null);
    }
}
