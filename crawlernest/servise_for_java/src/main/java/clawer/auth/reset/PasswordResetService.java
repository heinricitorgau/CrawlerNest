package clawer.auth.reset;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.regex.Pattern;

/**
 * "Forgot password": issue a one-time link, and change the password with it.
 *
 * <ul>
 *   <li>Asking for a link answers the same way whether or not the email has an
 *       account, so the form cannot be used to find out who is registered.</li>
 *   <li>The token is 32 random bytes. Only its SHA-256 is stored, and a token is
 *       good once, for {@code crawlernest.password-reset.ttl}.</li>
 *   <li>A new request, or a successful reset, ends every other open token for
 *       that user.</li>
 *   <li>At most {@link #MAX_REQUESTS_PER_HOUR} links per account per hour, so
 *       the form cannot be used to flood someone's inbox. Over the limit, the
 *       answer is unchanged and nothing is sent.</li>
 * </ul>
 *
 * <p>Known limit: tokens are stateless JWTs, so a session signed in before the
 * reset stays valid until it expires (crawlernest.jwt.ttl, 12 hours by default).
 * docs/AUTH_LIMITATIONS.md records it.
 */
@Service
public class PasswordResetService {

    static final int MAX_REQUESTS_PER_HOUR = 3;
    static final int PASSWORD_MIN_LENGTH = 8;
    private static final Pattern EMAIL = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    private static final Pattern TOKEN = Pattern.compile("^[A-Za-z0-9_-]{43}$");

    /** Thrown for a token that does not exist, was used, or has expired: the user is told the same for all three. */
    public static class InvalidTokenException extends RuntimeException {
        InvalidTokenException() {
            super("This reset link is invalid or has expired. Ask for a new one.");
        }
    }

    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final PasswordEncoder passwordEncoder;
    private final PasswordResetDelivery delivery;
    private final Duration ttl;
    private final String linkBase;
    private final SecureRandom random = new SecureRandom();

    public PasswordResetService(JdbcTemplate jdbc, TransactionTemplate tx, PasswordEncoder passwordEncoder,
                                PasswordResetDelivery delivery,
                                @Value("${crawlernest.password-reset.ttl:PT30M}") Duration ttl,
                                @Value("${crawlernest.password-reset.link-base:http://localhost:3000}") String linkBase) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.passwordEncoder = passwordEncoder;
        this.delivery = delivery;
        this.ttl = ttl;
        this.linkBase = linkBase.trim().replaceAll("/+$", "");
    }

    /**
     * Issues a link if the email belongs to an active account and the account is
     * under its hourly limit. Returns normally either way.
     *
     * @throws IllegalArgumentException only for something that is not an email at all
     */
    public void request(String rawEmail) {
        String email = rawEmail == null ? "" : rawEmail.trim().toLowerCase();
        if (!EMAIL.matcher(email).matches()) {
            throw new IllegalArgumentException("A valid email address is required.");
        }
        if (delivery.mode().equals("none")) {
            // No way to deliver it, so no token: one that nobody can receive is only a liability.
            delivery.deliver(email, null, ttl);
            return;
        }
        List<Long> users = jdbc.queryForList(
                "SELECT id FROM warehouse.app_user WHERE email = ? AND is_active", Long.class, email);
        if (users.isEmpty()) {
            return;
        }
        long userId = users.get(0);
        Integer recent = jdbc.queryForObject("""
                SELECT count(*) FROM warehouse.password_reset_token
                WHERE user_id = ? AND created_at > now() - interval '1 hour'
                """, Integer.class, userId);
        if (recent != null && recent >= MAX_REQUESTS_PER_HOUR) {
            return;
        }

        String token = newToken();
        Instant expires = Instant.now().plus(ttl);
        tx.executeWithoutResult(status -> {
            endOpenTokens(userId);
            jdbc.update("INSERT INTO warehouse.password_reset_token (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                    userId, sha256(token), Timestamp.from(expires));
        });
        delivery.deliver(email, linkBase + "/reset-password?token=" + token, ttl);
    }

    /** Sets the new password if the token is open, then ends it and every other open token for the user. */
    public void confirm(String token, String newPassword) {
        if (newPassword == null || newPassword.length() < PASSWORD_MIN_LENGTH) {
            throw new IllegalArgumentException("Password must be at least " + PASSWORD_MIN_LENGTH + " characters.");
        }
        if (token == null || !TOKEN.matcher(token).matches()) {
            throw new InvalidTokenException();
        }
        String hash = passwordEncoder.encode(newPassword);
        Boolean changed = tx.execute(status -> {
            // FOR UPDATE: two clicks on the same link cannot both get through.
            List<Long> users = jdbc.queryForList("""
                    SELECT user_id FROM warehouse.password_reset_token
                    WHERE token_hash = ? AND used_at IS NULL AND expires_at > now()
                    FOR UPDATE
                    """, Long.class, sha256(token));
            if (users.isEmpty()) {
                return false;
            }
            long userId = users.get(0);
            jdbc.update("UPDATE warehouse.app_user SET password_hash = ? WHERE id = ?", hash, userId);
            endOpenTokens(userId);
            return true;
        });
        if (!Boolean.TRUE.equals(changed)) {
            throw new InvalidTokenException();
        }
    }

    Duration ttl() {
        return ttl;
    }

    private void endOpenTokens(long userId) {
        jdbc.update("UPDATE warehouse.password_reset_token SET used_at = now() WHERE user_id = ? AND used_at IS NULL",
                userId);
    }

    private String newToken() {
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
