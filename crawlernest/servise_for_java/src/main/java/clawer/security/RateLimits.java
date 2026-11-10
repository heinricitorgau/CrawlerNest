package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.util.Arrays;
import java.util.Locale;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * The request limits, configured once and shared by {@link RateLimitFilter} and the sign-in throttle.
 *
 * <ul>
 *   <li>every {@code /api/**} request: {@code api-per-minute} per client address;</li>
 *   <li>sign-in, sign-up and password reset: {@code auth-per-minute} per client address;</li>
 *   <li>sign-up: {@code signup-per-hour} per client address, because a 409 still tells whether an email
 *       has an account and this is what makes asking about many emails slow;</li>
 *   <li>failed sign-ins: {@code signin-failures-per-email} per account in 15 minutes, from any address,
 *       so spreading a password guess over many addresses does not help. Past it, sign-in to that account
 *       answers 429 until the window ends, the real owner included -- a lockout an attacker can trigger,
 *       bounded at 15 minutes, which is the usual price of this protection.</li>
 * </ul>
 *
 * <p>Not a {@code Filter}: SecurityConfig builds the filter from this, so test slices without it carry none.
 */
@Component
public class RateLimits {

    public static final Duration SIGNIN_FAILURE_WINDOW = Duration.ofMinutes(15);

    private final boolean enabled;
    private final ClientAddressResolver addresses;
    private final FixedWindowRateLimiter api;
    private final FixedWindowRateLimiter auth;
    private final FixedWindowRateLimiter signup;
    private final FixedWindowRateLimiter signinFailures;

    @Autowired
    public RateLimits(
            @Value("${crawlernest.rate-limit.enabled:true}") boolean enabled,
            @Value("${crawlernest.rate-limit.trusted-proxies:127.0.0.1,::1}") String trustedProxies,
            @Value("${crawlernest.rate-limit.api-per-minute:600}") int apiPerMinute,
            @Value("${crawlernest.rate-limit.auth-per-minute:20}") int authPerMinute,
            @Value("${crawlernest.rate-limit.signup-per-hour:10}") int signupPerHour,
            @Value("${crawlernest.rate-limit.signin-failures-per-email:10}") int signinFailuresPerEmail
    ) {
        this(enabled, trustedProxies, apiPerMinute, authPerMinute, signupPerHour, signinFailuresPerEmail,
                Clock.systemUTC());
    }

    public RateLimits(boolean enabled, String trustedProxies, int apiPerMinute, int authPerMinute,
                      int signupPerHour, int signinFailuresPerEmail, Clock clock) {
        this.enabled = enabled;
        this.addresses = new ClientAddressResolver(Arrays.asList(trustedProxies.split(",")));
        this.api = new FixedWindowRateLimiter(apiPerMinute, Duration.ofMinutes(1), clock);
        this.auth = new FixedWindowRateLimiter(authPerMinute, Duration.ofMinutes(1), clock);
        this.signup = new FixedWindowRateLimiter(signupPerHour, Duration.ofHours(1), clock);
        this.signinFailures = new FixedWindowRateLimiter(signinFailuresPerEmail, SIGNIN_FAILURE_WINDOW, clock);
    }

    public boolean enabled() {
        return enabled;
    }

    ClientAddressResolver addresses() {
        return addresses;
    }

    FixedWindowRateLimiter api() {
        return api;
    }

    FixedWindowRateLimiter auth() {
        return auth;
    }

    FixedWindowRateLimiter signup() {
        return signup;
    }

    /** Whether sign-in to this account is currently refused for too many failures. */
    public FixedWindowRateLimiter.Decision signinAllowed(String email) {
        return enabled ? signinFailures.peek(emailKey(email)) : new FixedWindowRateLimiter.Decision(true, 0);
    }

    public void recordSigninFailure(String email) {
        if (enabled) {
            signinFailures.tryAcquire(emailKey(email));
        }
    }

    public void recordSigninSuccess(String email) {
        if (enabled) {
            signinFailures.reset(emailKey(email));
        }
    }

    private static String emailKey(String email) {
        return email == null ? "" : email.trim().toLowerCase(Locale.ROOT);
    }
}
