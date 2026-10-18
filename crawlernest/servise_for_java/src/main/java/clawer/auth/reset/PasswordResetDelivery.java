package clawer.auth.reset;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Locale;

/**
 * Where a password reset link goes.
 *
 * <p>Only two modes exist so far, and neither sends email:
 * <ul>
 *   <li>{@code log}: the link is written to the server log. For local development
 *       only -- anyone who can read the log can use it to take over the account.</li>
 *   <li>{@code none} (the default): nothing is delivered. A deployment that forgot
 *       to configure delivery leaks no links; users simply get no email.</li>
 * </ul>
 * An email delivery goes here when the platform has a mail service.
 */
@Component
public class PasswordResetDelivery {

    private static final Logger log = LoggerFactory.getLogger(PasswordResetDelivery.class);

    private final String mode;

    public PasswordResetDelivery(@Value("${crawlernest.password-reset.delivery:none}") String mode) {
        this.mode = mode.trim().toLowerCase(Locale.ROOT);
        if (this.mode.equals("log")) {
            log.warn("Password reset links are written to this log (crawlernest.password-reset.delivery=log). "
                    + "Development only: anyone who can read the log can reset any account that requests a link.");
        }
    }

    String mode() {
        return mode;
    }

    void deliver(String email, String link, Duration ttl) {
        switch (mode) {
            case "log" -> log.warn("DEV ONLY password reset link for {} (valid {} minutes): {}", email, ttl.toMinutes(), link);
            case "none" -> log.info("A password reset was requested, but no delivery is configured "
                    + "(crawlernest.password-reset.delivery=none), so no link was sent.");
            default -> log.error("Unknown crawlernest.password-reset.delivery '{}'; no link was sent.", mode);
        }
    }
}
