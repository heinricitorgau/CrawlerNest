package clawer.auth.jwt;

import java.time.Duration;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The token is the whole identity, so what it refuses matters more than what it accepts.
 */
class JwtServiceTest {

    private static final String SECRET = "a-test-secret-that-is-long-enough-for-hs256";
    private static final String OTHER_SECRET = "a-different-secret-also-long-enough-for-hs256";

    private static JwtService service(String secret, Duration ttl) {
        return new JwtService(secret, ttl);
    }

    @Test
    void aTokenNamesTheUserItWasIssuedFor() {
        JwtService jwt = service(SECRET, Duration.ofHours(12));
        Optional<AuthenticatedUser> user = jwt.verify(jwt.issue(42L, "someone@example.com"));

        assertEquals(Optional.of(new AuthenticatedUser(42L, "someone@example.com")), user);
        assertFalse(jwt.isEphemeralSecret());
    }

    @Test
    void aTokenSignedWithAnotherKeyIsNotAccepted() {
        String foreign = service(OTHER_SECRET, Duration.ofHours(12)).issue(42L, "someone@example.com");
        assertEquals(Optional.empty(), service(SECRET, Duration.ofHours(12)).verify(foreign));
    }

    @Test
    void anExpiredTokenIsNotAccepted() {
        // Issued with a lifetime already behind it.
        JwtService expiring = service(SECRET, Duration.ofSeconds(-1));
        assertEquals(Optional.empty(), service(SECRET, Duration.ofHours(12)).verify(expiring.issue(1L, "a@b.com")));
    }

    @Test
    void rubbishIsNotAccepted() {
        JwtService jwt = service(SECRET, Duration.ofHours(12));
        for (String token : new String[]{null, "", "   ", "not-a-token", "a.b.c"}) {
            assertEquals(Optional.empty(), jwt.verify(token), "accepted: " + token);
        }
    }

    @Test
    void aTamperedPayloadIsNotAccepted() {
        JwtService jwt = service(SECRET, Duration.ofHours(12));
        String token = jwt.issue(42L, "someone@example.com");
        String[] parts = token.split("\\.");
        // Same signature, different claims: the signature no longer matches them.
        String tampered = parts[0] + "." + java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(
                "{\"sub\":\"1\",\"email\":\"attacker@example.com\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8))
                + "." + parts[2];

        assertEquals(Optional.empty(), jwt.verify(tampered));
    }

    @Test
    void aSecretTooShortForHs256IsRefusedAtStartupRatherThanPadded() {
        IllegalStateException refused = assertThrows(IllegalStateException.class,
                () -> service("too-short", Duration.ofHours(12)));
        assertTrue(refused.getMessage().contains("32"), refused.getMessage());
    }

    @Test
    void noSecretMeansAKeyForThisProcessOnly() {
        // A checkout runs without configuration, but nothing ships with a default
        // key: two instances cannot verify each other's tokens, and it says so.
        JwtService first = service("  ", Duration.ofHours(12));
        JwtService second = service(null, Duration.ofHours(12));

        assertTrue(first.isEphemeralSecret());
        assertEquals(Optional.empty(), second.verify(first.issue(1L, "a@b.com")));
    }
}
