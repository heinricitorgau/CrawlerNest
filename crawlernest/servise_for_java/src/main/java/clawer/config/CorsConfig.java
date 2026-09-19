package clawer.config;

import java.util.Arrays;
import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;

/**
 * Which browser origins may call this API directly with credentials.
 *
 * <p>The origin was {@code http://localhost:3000}, compiled in. A deployment could
 * not add its own without a rebuild, and anyone reading the source learned only
 * where the developer's frontend ran. It now comes from
 * {@code CRAWLERNEST_CORS_ALLOWED_ORIGINS} (comma-separated), defaulting to that
 * same localhost origin so a local checkout behaves as before.
 *
 * <p>Credentials are allowed, so {@code *} is not: the browser refuses that
 * combination, and {@code allowedOriginPatterns} with a wildcard would let any site
 * make credentialed calls. An origin that should be trusted is named.
 */
@Configuration
public class CorsConfig {

    static final String DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000";

    private final String allowedOrigins;

    public CorsConfig(
            @Value("${crawlernest.cors.allowed-origins:" + DEFAULT_ALLOWED_ORIGINS + "}") String allowedOrigins
    ) {
        this.allowedOrigins = allowedOrigins;
    }

    /** The configured origins, trimmed, blanks dropped. */
    static List<String> parseOrigins(String configured) {
        List<String> origins = Arrays.stream(String.valueOf(configured).split(","))
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .toList();
        if (origins.contains("*")) {
            throw new IllegalArgumentException(
                    "crawlernest.cors.allowed-origins cannot be '*': this API allows credentials, "
                            + "so every origin must be named.");
        }
        return origins;
    }

    /** Separate from the filter, which exposes no accessor for what it was given. */
    UrlBasedCorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        parseOrigins(allowedOrigins).forEach(config::addAllowedOrigin);
        config.addAllowedMethod("*");
        config.addAllowedHeader("*");
        config.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }

    @Bean
    public CorsFilter corsFilter() {
        return new CorsFilter(corsConfigurationSource());
    }
}
