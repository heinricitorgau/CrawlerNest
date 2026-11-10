package clawer.auth.reset;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The forgot-password flow through the real endpoints and PostgreSQL, with the
 * delivery spied on so each test can read the link it would have sent.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256",
        "crawlernest.password-reset.delivery=log"
})
class PasswordResetIntegrationTest {

    private static final long USER = 990501L;
    private static final String EMAIL = "reset-owner@integration.test";
    private static final String OLD_PASSWORD = "old-password-1";

    @Autowired private MockMvc mvc;
    @Autowired private JdbcTemplate jdbc;
    @Autowired private PasswordEncoder encoder;
    @SpyBean private PasswordResetDelivery delivery;

    @BeforeEach
    void seed() {
        cleanup();
        jdbc.update("INSERT INTO warehouse.app_user (id, email, password_hash) VALUES (?, ?, ?)",
                USER, EMAIL, encoder.encode(OLD_PASSWORD));
        clearInvocations(delivery);
    }

    @AfterEach
    void cleanup() {
        jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", USER);
    }

    private ResultActions postJson(String path, String body) throws Exception {
        return mvc.perform(post(path).contentType(MediaType.APPLICATION_JSON).content(body));
    }

    private ResultActions requestLink(String email) throws Exception {
        return postJson("/api/v1/auth/password-reset/request", "{\"email\": \"" + email + "\"}");
    }

    /** Asks for a link and returns the token from the link the delivery was handed. */
    private String tokenFromNewLink() throws Exception {
        clearInvocations(delivery);
        requestLink(EMAIL).andExpect(status().isOk());
        ArgumentCaptor<String> link = ArgumentCaptor.forClass(String.class);
        verify(delivery).deliver(eq(EMAIL), link.capture(), any());
        assertTrue(link.getValue().startsWith("http://localhost:3000/reset-password?token="), link.getValue());
        return link.getValue().substring(link.getValue().indexOf("token=") + 6);
    }

    private ResultActions confirm(String token, String password) throws Exception {
        return postJson("/api/v1/auth/password-reset/confirm",
                "{\"token\": \"" + token + "\", \"newPassword\": \"" + password + "\"}");
    }

    private ResultActions signin(String password) throws Exception {
        return postJson("/api/v1/auth/signin", "{\"email\": \"" + EMAIL + "\", \"password\": \"" + password + "\"}");
    }

    private int openTokens() {
        return jdbc.queryForObject(
                "SELECT count(*) FROM warehouse.password_reset_token WHERE user_id = ? AND used_at IS NULL", Integer.class, USER);
    }

    @Test
    void aLinkResetsThePasswordOnceAndOnlyOnce() throws Exception {
        String token = tokenFromNewLink();
        confirm(token, "new-password-2")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.message").value(PasswordResetController.CHANGED));
        signin("new-password-2").andExpect(status().isOk());
        signin(OLD_PASSWORD).andExpect(status().isUnauthorized());

        confirm(token, "another-password-3").andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("This reset link is invalid or has expired. Ask for a new one."));
        signin("new-password-2").andExpect(status().isOk());
    }

    @Test
    void aResetSignsOutEveryTokenIssuedBeforeIt() throws Exception {
        jakarta.servlet.http.Cookie before = signin(OLD_PASSWORD).andExpect(status().isOk()).andReturn()
                .getResponse().getCookie(clawer.auth.jwt.JwtCookieAuthenticationFilter.COOKIE_NAME);
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/api/v1/auth/me").cookie(before))
                .andExpect(status().isOk());

        confirm(tokenFromNewLink(), "new-password-2").andExpect(status().isOk());

        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/api/v1/auth/me").cookie(before))
                .andExpect(status().isUnauthorized());
        jakarta.servlet.http.Cookie after = signin("new-password-2").andExpect(status().isOk()).andReturn()
                .getResponse().getCookie(clawer.auth.jwt.JwtCookieAuthenticationFilter.COOKIE_NAME);
        mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/api/v1/auth/me").cookie(after))
                .andExpect(status().isOk());
    }

    @Test
    void anUnknownEmailGetsTheSameAnswerAndNothingIsSent() throws Exception {
        String known = requestLink(EMAIL).andReturn().getResponse().getContentAsString();
        clearInvocations(delivery);
        String unknown = requestLink("nobody-here@integration.test").andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        assertEquals(known.replaceAll("\"timestamp\":\"[^\"]*\"", ""), unknown.replaceAll("\"timestamp\":\"[^\"]*\"", ""));
        verify(delivery, never()).deliver(anyString(), anyString(), any());
    }

    @Test
    void onlyTheHashIsStored() throws Exception {
        String token = tokenFromNewLink();
        String stored = jdbc.queryForObject(
                "SELECT token_hash FROM warehouse.password_reset_token WHERE user_id = ?", String.class, USER);
        assertNotEquals(token, stored);
        assertEquals(PasswordResetService.sha256(token), stored);
    }

    @Test
    void aNewLinkEndsTheOldOne() throws Exception {
        String first = tokenFromNewLink();
        String second = tokenFromNewLink();
        assertEquals(1, openTokens());
        confirm(first, "new-password-2").andExpect(status().isBadRequest());
        confirm(second, "new-password-2").andExpect(status().isOk());
        assertEquals(0, openTokens());
    }

    @Test
    void anExpiredLinkIsRefused() throws Exception {
        String token = tokenFromNewLink();
        jdbc.update("""
                UPDATE warehouse.password_reset_token
                SET created_at = now() - interval '2 hours', expires_at = now() - interval '1 hour' WHERE user_id = ?
                """, USER);
        confirm(token, "new-password-2").andExpect(status().isBadRequest());
        signin(OLD_PASSWORD).andExpect(status().isOk());
    }

    @Test
    void aShortPasswordIsRefusedAndTheLinkStillWorks() throws Exception {
        String token = tokenFromNewLink();
        confirm(token, "short").andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Password must be at least 8 characters."));
        confirm(token, "long-enough-now").andExpect(status().isOk());
    }

    @Test
    void aMalformedOrMadeUpTokenIsRefused() throws Exception {
        confirm("not-a-token", "new-password-2").andExpect(status().isBadRequest());
        confirm("A".repeat(43), "new-password-2").andExpect(status().isBadRequest());
        signin(OLD_PASSWORD).andExpect(status().isOk());
    }

    @Test
    void anAccountGetsAtMostThreeLinksAnHour() throws Exception {
        for (int i = 0; i < 5; i++) {
            requestLink(EMAIL).andExpect(status().isOk());
        }
        verify(delivery, times(PasswordResetService.MAX_REQUESTS_PER_HOUR)).deliver(eq(EMAIL), anyString(), any());
    }

    @Test
    void theEmailIsMatchedIgnoringCaseAndSpaces() throws Exception {
        clearInvocations(delivery);
        requestLink("  Reset-Owner@Integration.TEST ").andExpect(status().isOk());
        verify(delivery).deliver(eq(EMAIL), anyString(), any());
    }

    @Test
    void somethingThatIsNotAnEmailIsRefused() throws Exception {
        requestLink("not an email").andExpect(status().isBadRequest());
    }

    @Test
    void theAnswerSaysWhereTheLinkWent() throws Exception {
        requestLink(EMAIL)
                .andExpect(jsonPath("$.data.delivery").value("log"))
                .andExpect(jsonPath("$.data.message").value(org.hamcrest.Matchers.containsString("written to the server log")));
    }
}
