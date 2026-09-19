package clawer.config;

import org.junit.jupiter.api.Test;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * The allowed origins are configuration, not source.
 *
 * <p>They were compiled in as {@code http://localhost:3000}, so a deployment could
 * not name its own site without a rebuild, and the source told a reader only where
 * one developer's frontend ran.
 */
class CorsConfigTest {

    @Test
    void severalOriginsAreReadFromOneSetting() {
        assertEquals(
                List.of("https://crawlernest.example", "https://staging.crawlernest.example"),
                CorsConfig.parseOrigins("https://crawlernest.example, https://staging.crawlernest.example"));
    }

    @Test
    void blanksAndEmptyEntriesAreDropped() {
        assertEquals(List.of("https://one.example"), CorsConfig.parseOrigins("  https://one.example ,, "));
    }

    @Test
    void aWildcardIsRefusedRatherThanSentToABrowserThatWouldRejectIt() {
        // allowCredentials(true) with "*" is refused by every browser, and an
        // origin pattern wildcard would let any site make credentialed calls.
        IllegalArgumentException refused =
                assertThrows(IllegalArgumentException.class, () -> CorsConfig.parseOrigins("*"));
        assertTrue(refused.getMessage().contains("allowed-origins"), refused.getMessage());
        assertThrows(IllegalArgumentException.class, () -> CorsConfig.parseOrigins("https://one.example,*"));
    }

    @Test
    void theDefaultIsTheLocalFrontend() {
        assertEquals(List.of("http://localhost:3000"), CorsConfig.parseOrigins(CorsConfig.DEFAULT_ALLOWED_ORIGINS));
    }

    @Test
    void theFilterCarriesTheConfiguredOriginsAndStillAllowsCredentials() {
        CorsConfig config = new CorsConfig("https://crawlernest.example");
        UrlBasedCorsConfigurationSource source = config.corsConfigurationSource();
        CorsConfiguration cors = source.getCorsConfigurations().get("/**");

        assertEquals(List.of("https://crawlernest.example"), cors.getAllowedOrigins());
        assertEquals(Boolean.TRUE, cors.getAllowCredentials());
        // The filter is built from exactly this source.
        assertNotNull(config.corsFilter());
    }
}
