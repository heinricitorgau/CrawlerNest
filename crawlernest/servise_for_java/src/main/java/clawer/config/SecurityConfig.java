package clawer.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;

/**
 * What needs a signed-in user, and what does not.
 *
 * <p>Most of this API is a public read-only view of published ranking data, and it
 * stays that way: putting a login in front of it would break the frontend's
 * server-side reads and change what the platform is, not harden it. Only the
 * endpoints that belong to a person or an operator are closed:
 *
 * <ul>
 *   <li>{@code /api/v1/user/**} -- saved plans, saved universities, conversations.
 *       These already refused an anonymous caller in the controller; now the filter
 *       chain refuses one first, so a new endpoint under that prefix is closed by
 *       default rather than by remembering to check.</li>
 *   <li>{@code /api/v1/admin/**} -- mapping review decisions, which rewrite entity
 *       resolution.</li>
 * </ul>
 *
 * <p>Sessions are off entirely ({@link SessionCreationPolicy#STATELESS}): the token
 * carries the identity, so a second API instance accepts it without shared session
 * state. CSRF protection is disabled because there is no session to ride on and the
 * token cookie is SameSite=Strict, so a cross-site form post carries no credential.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final JwtService jwtService;

    public SecurityConfig(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // CorsConfig's filter still decides the origins.
                .cors(Customizer.withDefaults())
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(requests -> requests
                        .requestMatchers("/api/v1/user/**").authenticated()
                        .requestMatchers("/api/v1/admin/**").authenticated()
                        // Everything else is the public read API, plus the sign-in
                        // routes themselves. /api/v1/auth/me is deliberately open:
                        // it answers 401 with a JSON body of its own, which is how
                        // the frontend asks "is anyone signed in?".
                        .anyRequest().permitAll())
                // An unauthenticated call to a closed endpoint gets 401, not a
                // redirect to a login page that does not exist here.
                .exceptionHandling(handling -> handling
                        .authenticationEntryPoint(new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                .logout(logout -> logout.disable())
                // Constructed here rather than injected: a Filter bean would be
                // registered with the servlet container as well, running outside
                // this chain for every request.
                .addFilterBefore(new JwtCookieAuthenticationFilter(jwtService),
                        UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
