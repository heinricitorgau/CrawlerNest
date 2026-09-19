package clawer.user.service;

import clawer.user.controller.UserController;
import clawer.user.dto.SaveRecommendationRequest;
import clawer.user.dto.SavedRecommendationDetail;
import clawer.user.dto.SavedRecommendationSummary;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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

    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        SecurityContextHolder.clearContext();
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
    void saveRecommendation_withNoToken_returns401() {
        ResponseEntity<?> response = userController.saveRecommendation(buildValidRequest());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withAToken_returns201() throws Exception {
        signedIn(1L);
        when(savedRecommendationService.save(eq(1L), anyString(), any(), any())).thenReturn(99L);

        ResponseEntity<?> response = userController.saveRecommendation(buildValidRequest());

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        verify(savedRecommendationService).save(eq(1L), eq("My Plan"), any(), any());
    }

    @Test
    void listRecommendations_withNoToken_returns401() {
        ResponseEntity<?> response = userController.listRecommendations();

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).findSummariesByUserId(anyLong());
    }

    @Test
    void listRecommendations_onlyCurrentUserItems() {
        signedIn(7L);
        when(savedRecommendationService.findSummariesByUserId(7L)).thenReturn(List.of(new SavedRecommendationSummary()));

        ResponseEntity<?> response = userController.listRecommendations();

        assertEquals(HttpStatus.OK, response.getStatusCode());
        verify(savedRecommendationService).findSummariesByUserId(7L);
        verify(savedRecommendationService, never()).findSummariesByUserId(longThat(id -> id != 7L));
    }

    @Test
    void deleteRecommendation_withNoToken_returns401() {
        ResponseEntity<?> response = userController.deleteRecommendation(1L);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(savedRecommendationService, never()).deleteByIdAndUserId(anyLong(), anyLong());
    }

    @Test
    void deleteRecommendation_ownItem_returnsOk() {
        signedIn(5L);
        when(savedRecommendationService.deleteByIdAndUserId(42L, 5L)).thenReturn(true);

        ResponseEntity<?> response = userController.deleteRecommendation(42L);

        assertEquals(HttpStatus.OK, response.getStatusCode());
    }

    @Test
    void deleteRecommendation_anotherUsersItem_returns404() {
        signedIn(5L);
        // Service returns false: row not found (either doesn't exist or belongs to another user)
        when(savedRecommendationService.deleteByIdAndUserId(42L, 5L)).thenReturn(false);

        ResponseEntity<?> response = userController.deleteRecommendation(42L);

        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
    }

    @Test
    void getRecommendation_withNoToken_returns401() {
        ResponseEntity<?> response = userController.getRecommendation(1L);

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
    }

    @Test
    void getRecommendation_anotherUsersItem_returns404() {
        signedIn(3L);
        when(savedRecommendationService.findDetailByIdAndUserId(99L, 3L))
                .thenReturn(Optional.empty());

        ResponseEntity<?> response = userController.getRecommendation(99L);

        assertEquals(HttpStatus.NOT_FOUND, response.getStatusCode());
    }

    @Test
    void saveRecommendation_withTitleTooLong_returns400() {
        signedIn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setTitle("A".repeat(201));

        ResponseEntity<?> response = userController.saveRecommendation(req);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withNullRequestJson_returns400() {
        signedIn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setRequestJson(null);

        ResponseEntity<?> response = userController.saveRecommendation(req);

        assertEquals(HttpStatus.BAD_REQUEST, response.getStatusCode());
        verify(savedRecommendationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void saveRecommendation_withNullResultJson_returns400() {
        signedIn(1L);

        SaveRecommendationRequest req = buildValidRequest();
        req.setResultJson(null);

        ResponseEntity<?> response = userController.saveRecommendation(req);

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
