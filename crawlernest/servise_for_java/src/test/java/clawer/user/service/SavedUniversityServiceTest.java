package clawer.user.service;

import clawer.user.controller.UserController;
import clawer.auth.jwt.AuthenticatedUser;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class SavedUniversityServiceTest {

    // ─── Service tests ────────────────────────────────────────────────────────

    @Mock
    private JdbcTemplate jdbcTemplate;

    private SavedUniversityService savedUniversityService;

    // ─── Controller auth tests ────────────────────────────────────────────────

    @Mock
    private SavedUniversityService mockService;

    @InjectMocks
    private UserController userController;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        SecurityContextHolder.clearContext();
        savedUniversityService = new SavedUniversityService(jdbcTemplate);
    }

    @AfterEach
    void tearDown() {
        // The context is thread-local: one left behind signs the next test in.
        SecurityContextHolder.clearContext();
    }

    /** What the JWT filter leaves behind once a token verifies. */
    private void signedIn(long userId) {
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(
                        new AuthenticatedUser(userId, "user" + userId + "@example.com"),
                        null,
                        List.of()));
    }

    @Test
    void save_callsInsertWithCorrectArgs() {
        savedUniversityService.save(1L, 42L);
        verify(jdbcTemplate).update(anyString(), eq(1L), eq(42L));
    }

    @Test
    void save_duplicate_noExceptionThrown() {
        when(jdbcTemplate.update(anyString(), any(Object[].class))).thenReturn(0);
        savedUniversityService.save(1L, 42L);
        verify(jdbcTemplate).update(anyString(), eq(1L), eq(42L));
    }

    @Test
    void save_withNoToken_returns401() {
        ResponseEntity<?> response = userController.save(42L);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).save(anyLong(), anyLong());
    }

    @Test
    void save_withAToken_returns201() {
        signedIn(1L);

        ResponseEntity<?> response = userController.save(42L);

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        verify(mockService).save(1L, 42L);
    }

    @Test
    void delete_withNoToken_returns401() {
        ResponseEntity<?> response = userController.delete(42L);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).delete(anyLong(), anyLong());
    }

    @Test
    void list_withNoToken_returns401() {
        ResponseEntity<?> response = userController.list();

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).findByUserId(anyLong());
    }

    @Test
    void list_withAToken_returnsOk() {
        signedIn(1L);
        when(mockService.findByUserId(1L)).thenReturn(List.of());

        ResponseEntity<?> response = userController.list();

        assertEquals(HttpStatus.OK, response.getStatusCode());
        verify(mockService).findByUserId(1L);
    }
}
