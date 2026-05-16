package clawer.user.service;

import clawer.user.controller.UserController;
import clawer.user.dto.SaveRecommendationRequest;
import clawer.user.dto.SavedRecommendationDetail;
import clawer.user.dto.SavedRecommendationSummary;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class SavedRecommendationServiceTest {

    @Mock
    private SavedUniversityService savedUniversityService;

    @Mock
    private SavedRecommendationService savedRecommendationService;

    @InjectMocks
    private UserController userController;

    @Mock
    private HttpServletRequest httpRequest;

    @Mock
    private HttpSession httpSession;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void saveRecommendation_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.saveRecommendation(buildValidRequest(), httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withValidSession_returns201() throws Exception {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);
        when(savedRecommendationService.save(eq(1L), anyString(), any(), any())).thenReturn(99L);

        ResponseEntity<?> response = userController.saveRecommendation(buildValidRequest(), httpRequest);

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        verify(savedRecommendationService).save(eq(1L), eq("My Plan"), any(), any());
    }

    @Test
    void listRecommendations_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.listRecommendations(httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).findSummariesByUserId(anyLong());
    }

    @Test
    void listRecommendations_onlyCurrentUserItems() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(7L);
        when(savedRecommendationService.findSummariesByUserId(7L)).thenReturn(List.of(new SavedRecommendationSummary()));

        ResponseEntity<?> response = userController.listRecommendations(httpRequest);

        assertEquals(HttpStatus.OK, response.getStatusCode());
        verify(savedRecommendationService).findSummariesByUserId(7L);
        verify(savedRecommendationService, never()).findSummariesByUserId(longThat(id -> id != 7L));
    }

    @Test
    void deleteRecommendation_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.deleteRecommendation(1L, httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).deleteByIdAndUserId(anyLong(), anyLong());
    }

    @Test
    void deleteRecommendation_ownItem_returnsOk() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(5L);
        when(savedRecommendationService.deleteByIdAndUserId(42L, 5L)).thenReturn(true);

        ResponseEntity<?> response = userController.deleteRecommendation(42L, httpRequest);

        assertEquals(HttpStatus.OK, response.getStatusCode());
    }

    @Test
    void deleteRecommendation_anotherUsersItem_returns404() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(5L);
        // Service returns false: row not found (either doesn't exist or belongs to another user)
        when(savedRecommendationService.deleteByIdAndUserId(42L, 5L)).thenReturn(false);

        ResponseEntity<?> response = userController.deleteRecommendation(42L, httpRequest);

        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
    }

    @Test
    void getRecommendation_withNoSession_returns401() {
        when(httpRequest.getSession(false)).thenReturn(null);

        ResponseEntity<?> response = userController.getRecommendation(1L, httpRequest);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
    }

    @Test
    void getRecommendation_anotherUsersItem_returns404() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(3L);
        when(savedRecommendationService.findDetailByIdAndUserId(99L, 3L))
                .thenReturn(Optional.empty());

        ResponseEntity<?> response = userController.getRecommendation(99L, httpRequest);

        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
    }

    @Test
    void saveRecommendation_withTitleTooLong_returns400() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setTitle("A".repeat(201));

        ResponseEntity<?> response = userController.saveRecommendation(req, httpRequest);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withNullRequestJson_returns400() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setRequestJson(null);

        ResponseEntity<?> response = userController.saveRecommendation(req, httpRequest);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withNullResultJson_returns400() {
        when(httpRequest.getSession(false)).thenReturn(httpSession);
        when(httpSession.getAttribute("user_id")).thenReturn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setResultJson(null);

        ResponseEntity<?> response = userController.saveRecommendation(req, httpRequest);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    private SaveRecommendationRequest buildValidRequest() {
        SaveRecommendationRequest req = new SaveRecommendationRequest();
        req.setTitle("My Plan");
        try {
            req.setRequestJson(objectMapper.readTree("{\"country\":\"UK\"}"));
            req.setResultJson(objectMapper.readTree("{\"success\":true,\"data\":{\"reach\":[],\"target\":[],\"safety\":[]}}"));
        } catch (Exception ignored) {}
        return req;
    }
}
