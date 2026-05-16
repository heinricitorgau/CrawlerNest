package clawer.user.service;

import clawer.user.controller.UserController;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
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

    @Mock
    private HttpServletRequest httpRequest;

    @Mock
    private HttpSession httpSession;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        savedUniversityService = new SavedUniversityService(jdbcTemplate);
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
    void save_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.save(42L, httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).save(anyLong(), anyLong());
    }

    @Test
    void save_withValidSession_returns201() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);

        ResponseEntity<?> response = userController.save(42L, httpRequest);

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        verify(mockService).save(1L, 42L);
    }

    @Test
    void delete_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.delete(42L, httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).delete(anyLong(), anyLong());
    }

    @Test
    void list_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.list(httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(mockService, never()).findByUserId(anyLong());
    }

    @Test
    void list_withValidSession_returnsOk() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);
        when(mockService.findByUserId(1L)).thenReturn(List.of());

        ResponseEntity<?> response = userController.list(httpRequest);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        verify(mockService).findByUserId(1L);
    }
}
