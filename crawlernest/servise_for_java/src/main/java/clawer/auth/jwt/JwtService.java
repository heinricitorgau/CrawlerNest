package clawer.auth.jwt;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.Optional;

import javax.crypto.SecretKey;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

/**
 * Issues and verifies the signed token that identifies a signed-in user.
 *
 * <p>Sessions kept that identity in the servlet container's memory, which is fine
 * for one process and wrong for the container stack: a second API replica has no
 * copy of it, so a user is signed in or out depending on which instance answers.
 * A signed token carries the identity instead, and nothing per-user is stored
 * server-side.
 *
 * <p>The secret comes from {@code CRAWLERNEST_JWT_SECRET} and must be at least 32
 * bytes, the minimum for HS256. When it is unset the service generates a random key
 * and says so: a checkout runs without configuration, and everyone is signed out
 * whenever the process restarts -- which is the right nuisance, because the
 * alternative is a default secret that would let anyone mint a token for any user.
 */
@Service
public class JwtService {

    private static final Logger LOGGER = LoggerFactory.getLogger(JwtService.class);

    /** HS256 needs a 256-bit key; a shorter secret is refused rather than padded. */
    static final int MINIMUM_SECRET_BYTES = 32;
    public static final String CLAIM_EMAIL = "email";

    private final SecretKey key;
    private final Duration tokenTtl;
    private final boolean ephemeralSecret;

    public JwtService(
            @Value("${crawlernest.jwt.secret:}") String secret,
            @Value("${crawlernest.jwt.ttl:PT12H}") Duration tokenTtl
    ) {
        this.tokenTtl = tokenTtl;
        String configured = secret == null ? "" : secret.trim();
        if (configured.isEmpty()) {
            this.key = randomKey();
            this.ephemeralSecret = true;
            LOGGER.warn("CRAWLERNEST_JWT_SECRET is not set: signing with a key generated for this "
                    + "process. Tokens stop working when it restarts, and a second instance will not "
                    + "accept them. Set the variable for anything but a local run.");
        } else {
            byte[] material = configured.getBytes(StandardCharsets.UTF_8);
            if (material.length < MINIMUM_SECRET_BYTES) {
                throw new IllegalStateException("crawlernest.jwt.secret must be at least "
                        + MINIMUM_SECRET_BYTES + " bytes; got " + material.length
                        + ". Generate one with: openssl rand -base64 32");
            }
            this.key = Keys.hmacShaKeyFor(material);
            this.ephemeralSecret = false;
        }
    }

    /** True when the signing key was generated at startup rather than configured. */
    public boolean isEphemeralSecret() {
        return ephemeralSecret;
    }

    public Duration tokenTtl() {
        return tokenTtl;
    }

    /** A token naming this user, valid for {@link #tokenTtl()}. */
    public String issue(long userId, String email) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(Long.toString(userId))
                .claim(CLAIM_EMAIL, email)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(tokenTtl)))
                .signWith(key)
                .compact();
    }

    /**
     * The user a token names, or empty when it is missing, malformed, expired, or
     * signed with another key. Callers get no detail: a request either carries a
     * usable identity or it does not.
     */
    public Optional<AuthenticatedUser> verify(String token) {
        if (token == null || token.isBlank()) {
            return Optional.empty();
        }
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
            String email = claims.get(CLAIM_EMAIL, String.class);
            if (email == null || email.isBlank()) {
                return Optional.empty();
            }
            return Optional.of(new AuthenticatedUser(Long.parseLong(claims.getSubject()), email));
        } catch (JwtException | IllegalArgumentException ex) {
            LOGGER.debug("rejected a token: {}", ex.getClass().getSimpleName());
            return Optional.empty();
        }
    }

    private static SecretKey randomKey() {
        byte[] material = new byte[MINIMUM_SECRET_BYTES];
        new SecureRandom().nextBytes(material);
        return Keys.hmacShaKeyFor(Base64.getEncoder().encode(material));
    }
}
