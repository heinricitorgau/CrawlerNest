package clawer.auth.controller;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import jakarta.servlet.http.Cookie;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * A token can be ended before it expires: sign-out-everywhere and deactivation end it, a new sign-in
 * gets a working one, and too many failed sign-ins to one account are refused whatever the password.
 * Through the real filter chain and PostgreSQL.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256")
class TokenRevocationIntegrationTest {

    private static final long USER = 990601L;
    private static final String EMAIL = "revocation-owner@integration.test";
    private static final String PASSWORD = "a-password-1";

    @Autowired private MockMvc mvc;
    @Autowired private JdbcTemplate jdbc;
    @Autowired private PasswordEncoder encoder;
    @Autowired private JwtService jwtService;

    @BeforeEach
    void seed() {
        cleanup();
        jdbc.update("INSERT INTO warehouse.app_user (id, email, password_hash) VALUES (?, ?, ?)",
                USER, EMAIL, encoder.encode(PASSWORD));
    }

    @AfterEach
    void cleanup() {
        jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", USER);
    }

    private Cookie signin(String email, String password, int expectedStatus) throws Exception {
        var result = mvc.perform(post("/api/v1/auth/signin").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\": \"" + email + "\", \"password\": \"" + password + "\"}"))
                .andExpect(status().is(expectedStatus))
                .andReturn();
        return result.getResponse().getCookie(JwtCookieAuthenticationFilter.COOKIE_NAME);
    }

    private int me(Cookie cookie) throws Exception {
        return mvc.perform(get("/api/v1/auth/me").cookie(cookie)).andReturn().getResponse().getStatus();
    }

    @Test
    void signingOutEverywhereEndsEveryTokenAndANewSigninWorks() throws Exception {
        Cookie first = signin(EMAIL, PASSWORD, 200);
        Cookie second = signin(EMAIL, PASSWORD, 200);
        assertNotNull(first);
        if (me(first) != 200 || me(second) != 200) {
            throw new AssertionError("fresh tokens should be accepted");
        }

        mvc.perform(post("/api/v1/auth/signout-everywhere").cookie(first)).andExpect(status().isOk())
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.containsString("Max-Age=0")));

        if (me(first) != 401 || me(second) != 401) {
            throw new AssertionError("tokens issued before sign-out-everywhere must be refused");
        }
        mvc.perform(get("/api/v1/user/saved-universities").cookie(second)).andExpect(status().isUnauthorized());

        Cookie third = signin(EMAIL, PASSWORD, 200);
        if (me(third) != 200) {
            throw new AssertionError("a token issued after sign-out-everywhere should work");
        }
    }

    @Test
    void signupAnswersTheSameForATakenEmailAsForANewOne() throws Exception {
        String fresh = "signup-fresh@integration.test";
        jdbc.update("DELETE FROM warehouse.app_user WHERE email = ?", fresh);
        try {
            String newOne = mvc.perform(post("/api/v1/auth/signup").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\": \"" + fresh + "\", \"password\": \"another-password\"}"))
                    .andExpect(status().isAccepted()).andReturn().getResponse().getContentAsString();
            String taken = mvc.perform(post("/api/v1/auth/signup").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\": \"" + EMAIL + "\", \"password\": \"another-password\"}"))
                    .andExpect(status().isAccepted()).andReturn().getResponse().getContentAsString();
            String strip = "\"timestamp\":\"[^\"]*\"";
            org.junit.jupiter.api.Assertions.assertEquals(newOne.replaceAll(strip, ""), taken.replaceAll(strip, ""));

            // The taken account's password is unchanged, and the new account works.
            signin(EMAIL, PASSWORD, 200);
            signin(EMAIL, "another-password", 401);
            signin(fresh, "another-password", 200);
        } finally {
            jdbc.update("DELETE FROM warehouse.app_user WHERE email = ?", fresh);
        }
    }

    @Test
    void signingOutEverywhereNeedsASignedInCaller() throws Exception {
        mvc.perform(post("/api/v1/auth/signout-everywhere")).andExpect(status().isUnauthorized());
    }

    @Test
    void aTokenFromBeforeGenerationsExistedStillWorksUntilTheFirstRevocation() throws Exception {
        // issue(id, email) is generation 0, which is what every pre-V009 token reads as.
        Cookie legacy = new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, jwtService.issue(USER, EMAIL));
        if (me(legacy) != 200) {
            throw new AssertionError("a generation-0 token should be accepted at generation 0");
        }
        jdbc.update("UPDATE warehouse.app_user SET token_version = token_version + 1 WHERE id = ?", USER);
        if (me(legacy) != 401) {
            throw new AssertionError("a generation-0 token must be refused after a revocation");
        }
    }

    @Test
    void aDeactivatedAccountsTokensAreRefused() throws Exception {
        Cookie cookie = signin(EMAIL, PASSWORD, 200);
        jdbc.update("UPDATE warehouse.app_user SET is_active = false WHERE id = ?", USER);
        if (me(cookie) != 401) {
            throw new AssertionError("a deactivated account's token must be refused");
        }
    }

    @Test
    void tooManyFailedSigninsLockTheAccountWhateverThePassword() throws Exception {
        // Its own account: the lock outlives this test in the shared context and must not touch the others.
        long lockedUser = 990602L;
        String lockedEmail = "locked-owner@integration.test";
        jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", lockedUser);
        jdbc.update("INSERT INTO warehouse.app_user (id, email, password_hash) VALUES (?, ?, ?)",
                lockedUser, lockedEmail, encoder.encode(PASSWORD));
        try {
            for (int i = 0; i < 10; i++) {
                signin(lockedEmail, "wrong-password-" + i, 401);
            }
            mvc.perform(post("/api/v1/auth/signin").contentType(MediaType.APPLICATION_JSON)
                            .content("{\"email\": \"" + lockedEmail.toUpperCase() + "\", \"password\": \"" + PASSWORD + "\"}"))
                    .andExpect(status().isTooManyRequests())
                    .andExpect(header().exists("Retry-After"));
        } finally {
            jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", lockedUser);
        }
    }
}
