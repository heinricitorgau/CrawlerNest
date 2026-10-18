package clawer.auth.reset;

import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.MailException;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSenderImpl;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.Locale;
import java.util.Properties;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * Where a password reset link goes ({@code crawlernest.password-reset.delivery}).
 *
 * <ul>
 *   <li>{@code smtp}: emailed through the SMTP server in {@code crawlernest.mail.*}
 *       (any provider: Gmail with an app password, Resend, SendGrid, Brevo...).</li>
 *   <li>{@code log}: written to the server log. Development only -- anyone who can
 *       read the log can use the link.</li>
 *   <li>{@code none} (the default): nothing is delivered and no token is made.</li>
 * </ul>
 *
 * <p>Mail is sent on a background thread, never inside the request. An SMTP
 * round trip takes seconds, and only a registered email causes one: done inline,
 * the response time alone would tell a stranger which emails have accounts.
 *
 * <p>{@code smtp} without a host or a from address is a configuration mistake, and
 * the server says so at startup and behaves as {@code none} -- so the page tells
 * people no link was sent, rather than promising an email that never leaves.
 */
@Component
public class PasswordResetDelivery {

    private static final Logger log = LoggerFactory.getLogger(PasswordResetDelivery.class);

    private final String mode;
    private final JavaMailSenderImpl mailSender;
    private final String from;
    private final ExecutorService sender;

    @Autowired
    public PasswordResetDelivery(
            @Value("${crawlernest.password-reset.delivery:none}") String mode,
            @Value("${crawlernest.mail.host:}") String host,
            @Value("${crawlernest.mail.port:587}") int port,
            @Value("${crawlernest.mail.username:}") String username,
            @Value("${crawlernest.mail.password:}") String password,
            @Value("${crawlernest.mail.from:}") String from,
            @Value("${crawlernest.mail.starttls:true}") boolean starttls,
            @Value("${crawlernest.mail.timeout:PT10S}") Duration timeout) {
        String requested = mode.trim().toLowerCase(Locale.ROOT);
        this.from = from.trim();
        if (requested.equals("smtp") && (host.isBlank() || this.from.isBlank())) {
            log.error("crawlernest.password-reset.delivery=smtp needs crawlernest.mail.host and crawlernest.mail.from "
                    + "(CRAWLERNEST_SMTP_HOST, CRAWLERNEST_MAIL_FROM). Password reset links will not be sent.");
            requested = "none";
        }
        this.mode = requested;
        if (this.mode.equals("smtp")) {
            this.mailSender = mailSender(host.trim(), port, username.trim(), password, starttls, timeout);
            this.sender = Executors.newSingleThreadExecutor(r -> {
                Thread t = new Thread(r, "password-reset-mail");
                t.setDaemon(true);
                return t;
            });
            log.info("Password reset links are emailed through {}:{} from {}.", host.trim(), port, this.from);
        } else {
            this.mailSender = null;
            this.sender = null;
        }
        if (this.mode.equals("log")) {
            log.warn("Password reset links are written to this log (crawlernest.password-reset.delivery=log). "
                    + "Development only: anyone who can read the log can reset any account that requests a link.");
        }
    }

    /** For the tests: no SMTP settings. */
    PasswordResetDelivery(String mode) {
        this(mode, "", 587, "", "", "", true, Duration.ofSeconds(10));
    }

    /** The mode in effect: "smtp" that is missing its settings reports "none". */
    String mode() {
        return mode;
    }

    void deliver(String email, String link, Duration ttl) {
        switch (mode) {
            case "smtp" -> sender.execute(() -> send(email, link, ttl));
            case "log" -> log.warn("DEV ONLY password reset link for {} (valid {} minutes): {}", email, ttl.toMinutes(), link);
            case "none" -> log.info("A password reset was requested, but no delivery is configured "
                    + "(crawlernest.password-reset.delivery=none), so no link was sent.");
            default -> log.error("Unknown crawlernest.password-reset.delivery '{}'; no link was sent.", mode);
        }
    }

    private void send(String email, String link, Duration ttl) {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setFrom(from);
        message.setTo(email);
        message.setSubject("Reset your CrawlerNest password");
        message.setText(body(link, ttl));
        try {
            mailSender.send(message);
            log.info("Password reset email sent.");
        } catch (MailException e) {
            // Neither the address nor the link goes in the log: the failure is ours to fix,
            // and a link in a log is a link anyone with the log can use.
            log.error("A password reset email could not be sent: {}", e.getClass().getSimpleName());
        }
    }

    static String body(String link, Duration ttl) {
        return """
                Someone asked to reset the password for this CrawlerNest account.

                To choose a new password, open this link:
                %s

                It works once, for %d minutes. If it expires, ask for a new one from the sign-in page.

                If you did not ask for this, you can ignore this email: your password stays as it is.
                """.formatted(link, ttl.toMinutes());
    }

    private static JavaMailSenderImpl mailSender(String host, int port, String username, String password,
                                                 boolean starttls, Duration timeout) {
        JavaMailSenderImpl sender = new JavaMailSenderImpl();
        sender.setHost(host);
        sender.setPort(port);
        if (!username.isEmpty()) {
            sender.setUsername(username);
            sender.setPassword(password);
        }
        Properties props = sender.getJavaMailProperties();
        props.put("mail.smtp.auth", String.valueOf(!username.isEmpty()));
        props.put("mail.smtp.starttls.enable", String.valueOf(starttls));
        props.put("mail.smtp.starttls.required", String.valueOf(starttls));
        String ms = String.valueOf(timeout.toMillis());
        props.put("mail.smtp.connectiontimeout", ms);
        props.put("mail.smtp.timeout", ms);
        props.put("mail.smtp.writetimeout", ms);
        return sender;
    }

    @PreDestroy
    void stop() throws InterruptedException {
        if (sender != null) {
            sender.shutdown();
            sender.awaitTermination(15, TimeUnit.SECONDS);
        }
    }
}
