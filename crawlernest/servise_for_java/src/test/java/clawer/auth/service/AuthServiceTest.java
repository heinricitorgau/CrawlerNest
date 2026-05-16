package clawer.auth.service;

import clawer.auth.dto.AuthUserResponse;
import clawer.auth.dto.SigninRequest;
import clawer.auth.dto.SignupRequest;
import clawer.auth.model.AppUser;
import clawer.auth.repository.AppUserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.time.Instant;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class AuthServiceTest {

    @Mock
    private AppUserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @InjectMocks
    private AuthService authService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void signup_duplicateEmail_throwsDuplicateEmailException() {
        when(userRepository.existsByEmail("duplicate@example.com")).thenReturn(true);

        SignupRequest request = new SignupRequest("duplicate@example.com", "password123");

        assertThrows(DuplicateEmailException.class, () -> authService.signup(request));
        verify(userRepository, never()).save(any());
    }

    @Test
    void signin_wrongPassword_throwsInvalidCredentialsException() {
        AppUser user = new AppUser();
        user.setId(1L);
        user.setEmail("user@example.com");
        user.setPasswordHash("$2a$10$hashedvalue");
        user.setCreatedAt(Instant.now());

        when(userRepository.findByEmail("user@example.com")).thenReturn(Optional.of(user));
        when(passwordEncoder.matches("wrongpassword", "$2a$10$hashedvalue")).thenReturn(false);

        SigninRequest request = new SigninRequest("user@example.com", "wrongpassword");

        assertThrows(InvalidCredentialsException.class, () -> authService.signin(request));
        verify(userRepository, never()).save(any());
    }

    @Test
    void passwordHash_notEqualToRawPassword() {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        String raw = "mySecretPassword";
        String hash = encoder.encode(raw);

        assertNotEquals(raw, hash);
        assertTrue(encoder.matches(raw, hash));
        assertFalse(encoder.matches("wrongpassword", hash));
    }

    @Test
    void signup_success_returnsUserWithoutPassword() {
        when(userRepository.existsByEmail("new@example.com")).thenReturn(false);
        when(passwordEncoder.encode("password123")).thenReturn("$2a$10$hashed");

        AppUser saved = new AppUser();
        saved.setId(42L);
        saved.setEmail("new@example.com");
        saved.setPasswordHash("$2a$10$hashed");
        saved.setCreatedAt(Instant.now());

        when(userRepository.save(any(AppUser.class))).thenReturn(saved);

        SignupRequest request = new SignupRequest("new@example.com", "password123");
        AuthUserResponse response = authService.signup(request);

        assertNotNull(response);
        assertEquals("new@example.com", response.getEmail());
        assertEquals(42L, response.getId());
    }
}
