package clawer.auth.service;

import clawer.auth.dto.AuthUserResponse;
import clawer.auth.dto.SigninRequest;
import clawer.auth.dto.SignupRequest;
import clawer.auth.model.AppUser;
import clawer.auth.repository.AppUserRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.regex.Pattern;

@Service
public class AuthService {

    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    private static final int PASSWORD_MIN_LENGTH = 8;

    private final AppUserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public AuthService(AppUserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public AuthUserResponse signup(SignupRequest request) {
        String email = normalize(request.getEmail());
        String password = request.getPassword();

        validateEmail(email);
        validatePassword(password);

        if (userRepository.existsByEmail(email)) {
            throw new DuplicateEmailException();
        }

        AppUser user = new AppUser();
        user.setEmail(email);
        user.setPasswordHash(passwordEncoder.encode(password));
        AppUser saved = userRepository.save(user);

        return toResponse(saved);
    }

    @Transactional
    public AuthUserResponse signin(SigninRequest request) {
        String email = normalize(request.getEmail());
        String password = request.getPassword();

        AppUser user = userRepository.findByEmail(email)
                .orElseThrow(InvalidCredentialsException::new);

        if (!passwordEncoder.matches(password, user.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }

        user.setLastLoginAt(Instant.now());
        userRepository.save(user);

        return toResponse(user);
    }

    private static String normalize(String email) {
        if (email == null) return "";
        return email.trim().toLowerCase();
    }

    private static void validateEmail(String email) {
        if (email.isEmpty() || !EMAIL_PATTERN.matcher(email).matches()) {
            throw new IllegalArgumentException("A valid email address is required.");
        }
    }

    private static void validatePassword(String password) {
        if (password == null || password.length() < PASSWORD_MIN_LENGTH) {
            throw new IllegalArgumentException(
                    "Password must be at least " + PASSWORD_MIN_LENGTH + " characters.");
        }
    }

    private static AuthUserResponse toResponse(AppUser user) {
        return new AuthUserResponse(
                user.getId(),
                user.getEmail(),
                user.getCreatedAt(),
                user.getLastLoginAt()
        );
    }
}
