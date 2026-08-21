package clawer.review.service;

import clawer.auth.model.AppUser;
import clawer.auth.repository.AppUserRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Who is allowed to overrule the resolver.
 *
 * <p>An allowlist of e-mail addresses rather than a role column: this is an
 * internal tool for a handful of people, and warehouse.app_user is a
 * public-signup table, so a role flag there would be one bad default away from
 * handing a visitor write access to ranking data.
 *
 * <p><strong>Fails closed.</strong> With the property unset nobody is a
 * reviewer, so forgetting to configure it costs a locked door rather than an
 * open one.
 */
@Service
public class ReviewerAuthorization {

    private final Set<String> allowedEmails;
    private final AppUserRepository appUserRepository;

    public ReviewerAuthorization(
            @Value("${crawlernest.reviewer.emails:}") String configuredEmails,
            AppUserRepository appUserRepository) {
        this.appUserRepository = appUserRepository;
        this.allowedEmails = Arrays.stream(configuredEmails.split(","))
                .map(String::trim)
                .filter(email -> !email.isEmpty())
                .map(email -> email.toLowerCase(Locale.ROOT))
                .collect(Collectors.toUnmodifiableSet());
    }

    public boolean isConfigured() {
        return !allowedEmails.isEmpty();
    }

    /** The reviewer's e-mail, or empty when this user may not review. */
    public Optional<String> reviewerEmail(Long userId) {
        if (userId == null || allowedEmails.isEmpty()) {
            return Optional.empty();
        }
        return appUserRepository.findById(userId)
                .map(AppUser::getEmail)
                .filter(email -> email != null && !email.isBlank())
                .filter(email -> allowedEmails.contains(email.toLowerCase(Locale.ROOT)));
    }
}
