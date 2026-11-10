package clawer.auth.controller;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** crawlernest.jwt.cookie-secure: on by itself behind https, never off there by accident. */
class CookieSecureSettingTest {

    @Test
    void autoFollowsThePublicAddress() {
        assertTrue(AuthController.resolveCookieSecure("auto", "https://crawlernest.example"));
        assertTrue(AuthController.resolveCookieSecure("", "HTTPS://crawlernest.example"));
        assertFalse(AuthController.resolveCookieSecure("auto", "http://localhost:3000"));
        assertFalse(AuthController.resolveCookieSecure(null, null));
    }

    @Test
    void explicitValuesAreHonouredExceptOffBehindHttps() {
        assertTrue(AuthController.resolveCookieSecure("true", "http://localhost:3000"));
        assertFalse(AuthController.resolveCookieSecure("false", "http://localhost:3000"));
        assertThrows(IllegalStateException.class,
                () -> AuthController.resolveCookieSecure("false", "https://crawlernest.example"));
        assertThrows(IllegalStateException.class,
                () -> AuthController.resolveCookieSecure("yes", "http://localhost:3000"));
    }
}
