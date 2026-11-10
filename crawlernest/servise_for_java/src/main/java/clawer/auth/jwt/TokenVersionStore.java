package clawer.auth.jwt;

import java.util.List;
import java.util.OptionalInt;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * The token generation of each account ({@code warehouse.app_user.token_version}, V009).
 *
 * <p>A token is accepted only while its {@code ver} claim equals the account's current generation, so
 * incrementing it ends every token issued before -- the one revocation a stateless token allows without a
 * denylist. It costs one primary-key read per request that carries a token; anonymous requests read nothing.
 */
@Component
public class TokenVersionStore {

    private final JdbcTemplate jdbc;

    public TokenVersionStore(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** The account's current generation, or empty when it does not exist or is deactivated. */
    public OptionalInt currentVersion(long userId) {
        List<Integer> rows = jdbc.queryForList(
                "SELECT token_version FROM warehouse.app_user WHERE id = ? AND is_active",
                Integer.class, userId);
        return rows.isEmpty() || rows.get(0) == null ? OptionalInt.empty() : OptionalInt.of(rows.get(0));
    }

    /** Ends every token issued to this account so far. Returns the new generation, or empty if no such account. */
    public OptionalInt revokeAll(long userId) {
        List<Integer> rows = jdbc.queryForList(
                "UPDATE warehouse.app_user SET token_version = token_version + 1 WHERE id = ? RETURNING token_version",
                Integer.class, userId);
        return rows.isEmpty() ? OptionalInt.empty() : OptionalInt.of(rows.get(0));
    }
}
