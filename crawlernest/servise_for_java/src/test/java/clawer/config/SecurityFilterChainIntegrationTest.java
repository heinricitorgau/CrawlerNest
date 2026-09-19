package clawer.config;

import jakarta.servlet.http.Cookie;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Which doors the filter chain leaves open, and which it closes before a
 * controller ever runs.
 *
 * <p>The split is the point: this platform's value is a public, read-only view of
 * ranking data, so closing the analytics API would be a regression, not
 * hardening. Only what belongs to a person or an operator is behind the token.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256",
        // Nobody is a reviewer here, so the admin endpoint's own 403 is
        // distinguishable from the chain's 401.
        "crawlernest.reviewer.emails="
})
class SecurityFilterChainIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtService jwtService;

    private Cookie tokenFor(long userId, String email) {
        return new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, jwtService.issue(userId, email));
    }

    // ─── The public read API stays public ─────────────────────────────────────

    @Test
    void healthAnswersWithoutAToken() throws Exception {
        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk());
    }

    @Test
    void theRankingsEndpointAnswersWithoutAToken() throws Exception {
        // Any status but 401/403 would do; 200 is what the frontend's
        // server-side render depends on.
        mockMvc.perform(get("/api/v1/rankings").param("page", "1").param("pageSize", "1"))
                .andExpect(status().isOk());
    }

    // ─── User endpoints are closed ────────────────────────────────────────────

    @Test
    void aUserEndpointIsRefusedWithoutAToken() throws Exception {
        mockMvc.perform(get("/api/v1/user/saved-recommendations"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void aUserEndpointAnswersWithAValidTokenCookie() throws Exception {
        mockMvc.perform(get("/api/v1/user/saved-recommendations")
                        .cookie(tokenFor(987654321L, "nobody@example.com")))
                .andExpect(status().isOk())
                // An account with nothing saved: the identity was accepted, and the
                // query was scoped to it rather than returning someone else's rows.
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.length()").value(0));
    }

    @Test
    void aTamperedTokenIsTreatedAsNoTokenAtAll() throws Exception {
        String token = jwtService.issue(1L, "someone@example.com");
        Cookie tampered = new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, token.substring(0, token.length() - 2) + "xy");

        mockMvc.perform(get("/api/v1/user/saved-recommendations").cookie(tampered))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void anUnknownPathUnderTheUserPrefixIsClosedToo() throws Exception {
        // The prefix is what closes the door, not a per-controller check, so an
        // endpoint added under it later is closed before anyone remembers to.
        mockMvc.perform(get("/api/v1/user/not-a-real-endpoint"))
                .andExpect(status().isUnauthorized());
    }

    // ─── Admin endpoints are closed, then separately authorized ───────────────

    @Test
    void theAdminEndpointIsRefusedWithoutAToken() throws Exception {
        mockMvc.perform(get("/api/v1/admin/mapping-reviews"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void aSignedInNonReviewerIsForbiddenRatherThanUnauthorized() throws Exception {
        // Authentication got them through the chain; the reviewer allowlist is a
        // second, independent gate, and with none configured it fails closed.
        mockMvc.perform(get("/api/v1/admin/mapping-reviews")
                        .cookie(tokenFor(987654321L, "nobody@example.com")))
                .andExpect(status().isForbidden());
    }

    // ─── /auth/me answers for itself ──────────────────────────────────────────

    @Test
    void meIsOpenAndReportsThatNobodyIsSignedIn() throws Exception {
        // Deliberately not behind the chain: the frontend calls it to find out
        // whether there is a session, and needs the JSON body, not a bare 401.
        mockMvc.perform(get("/api/v1/auth/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void meNamesTheUserTheTokenWasIssuedFor() throws Exception {
        mockMvc.perform(get("/api/v1/auth/me").cookie(tokenFor(4242L, "someone@example.com")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(4242))
                .andExpect(jsonPath("$.data.email").value("someone@example.com"));
    }

    @Test
    void aBearerHeaderWorksForCallersThatAreNotBrowsers() throws Exception {
        mockMvc.perform(get("/api/v1/auth/me")
                        .header("Authorization", "Bearer " + jwtService.issue(7L, "cli@example.com")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(7));
    }
}
