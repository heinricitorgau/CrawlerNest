package clawer.auth.reset;

import com.icegreen.greenmail.junit5.GreenMailExtension;
import com.icegreen.greenmail.util.GreenMailUtil;
import com.icegreen.greenmail.util.ServerSetupTest;
import jakarta.mail.internet.MimeMessage;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * "smtp" delivery against a real SMTP server running in the test (GreenMail):
 * the email is actually sent, read back, and its link used.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256",
        "crawlernest.password-reset.delivery=smtp",
        "crawlernest.mail.host=127.0.0.1",
        "crawlernest.mail.port=3025",
        "crawlernest.mail.from=CrawlerNest <no-reply@crawlernest.test>",
        "crawlernest.mail.starttls=false",
        "crawlernest.password-reset.link-base=https://crawlernest.example/"
})
class PasswordResetMailIntegrationTest {

    @RegisterExtension
    static final GreenMailExtension smtp = new GreenMailExtension(ServerSetupTest.SMTP);

    private static final long USER = 990601L;
    private static final String EMAIL = "reset-mail@integration.test";

    @Autowired private MockMvc mvc;
    @Autowired private JdbcTemplate jdbc;
    @Autowired private PasswordEncoder encoder;

    @BeforeEach
    void seed() {
        cleanup();
        jdbc.update("INSERT INTO warehouse.app_user (id, email, password_hash) VALUES (?, ?, ?)",
                USER, EMAIL, encoder.encode("old-password-1"));
    }

    @AfterEach
    void cleanup() {
        jdbc.update("DELETE FROM warehouse.app_user WHERE id = ?", USER);
    }

    private ResultActions postJson(String path, String body) throws Exception {
        return mvc.perform(post(path).contentType(MediaType.APPLICATION_JSON).content(body));
    }

    @Test
    void theLinkArrivesByEmailAndWorks() throws Exception {
        postJson("/api/v1/auth/password-reset/request", "{\"email\": \"" + EMAIL + "\"}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.delivery").value("smtp"))
                .andExpect(jsonPath("$.data.message").value(org.hamcrest.Matchers.startsWith(
                        "If an account exists for that email, we've sent a link")));

        assertTrue(smtp.waitForIncomingEmail(5000, 1), "no email arrived");
        MimeMessage mail = smtp.getReceivedMessages()[0];
        assertEquals(EMAIL, mail.getAllRecipients()[0].toString());
        assertEquals("CrawlerNest <no-reply@crawlernest.test>", mail.getFrom()[0].toString());
        assertEquals("Reset your CrawlerNest password", mail.getSubject());

        String body = GreenMailUtil.getBody(mail);
        assertTrue(body.contains("works once, for 30 minutes"), body);
        assertTrue(body.contains("If you did not ask for this, you can ignore this email"), body);
        // The base URL's trailing slash is not doubled.
        Matcher link = Pattern.compile("https://crawlernest\\.example/reset-password\\?token=([A-Za-z0-9_-]{43})").matcher(body);
        assertTrue(link.find(), body);

        postJson("/api/v1/auth/password-reset/confirm",
                "{\"token\": \"" + link.group(1) + "\", \"newPassword\": \"new-password-2\"}")
                .andExpect(status().isOk());
        postJson("/api/v1/auth/signin", "{\"email\": \"" + EMAIL + "\", \"password\": \"new-password-2\"}")
                .andExpect(status().isOk());
    }

    @Test
    void anUnknownEmailGetsNoMail() throws Exception {
        postJson("/api/v1/auth/password-reset/request", "{\"email\": \"nobody-here@integration.test\"}")
                .andExpect(status().isOk());
        assertTrue(!smtp.waitForIncomingEmail(1500, 1), "an email went to an address with no account");
    }
}
