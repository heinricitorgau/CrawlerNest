package clawer.desk.story;

import clawer.auth.jwt.AuthenticatedUser;
import clawer.desk.controller.NarrativeController;
import clawer.desk.support.DeskException;
import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

/**
 * NarrativeController's contract, without a database or a model: which service
 * call each path makes, that the user id is the token's and nothing else, and
 * that no call reaches the service without a signed-in user.
 */
class NarrativeControllerTest {

    private static final long USER = 42L;

    private NarrativeService service;
    private NarrativeController controller;

    @BeforeEach
    void setUp() {
        service = mock(NarrativeService.class);
        controller = new NarrativeController(service);
        SecurityContextHolder.clearContext();
    }

    @AfterEach
    void tearDown() {
        // The context is thread-local: one left behind signs the next test in.
        SecurityContextHolder.clearContext();
    }

    private void signedIn(long userId) {
        SecurityContextHolder.getContext().setAuthentication(new UsernamePasswordAuthenticationToken(
                new AuthenticatedUser(userId, "user" + userId + "@example.com"), null, List.of()));
    }

    private static Object data(ResponseEntity<?> response) {
        assertEquals(HttpStatus.OK, response.getStatusCode());
        ApiResponse<?> body = (ApiResponse<?>) response.getBody();
        assertEquals(true, body.isSuccess());
        return body.getData();
    }

    @Test
    void getThemesReturnsTheServicesThemesForTheSignedInUser() {
        signedIn(USER);
        Map<String, Object> themes = Map.of("themes", List.of(), "caveats", List.of("c"));
        when(service.themes(USER, false)).thenReturn(themes);
        assertSame(themes, data(controller.themes(false)));
        verify(service).themes(USER, false);
    }

    @Test
    void getThemesPassesIncludeDismissedThrough() {
        signedIn(USER);
        controller.themes(true);
        verify(service).themes(USER, true);
    }

    @Test
    void getResonanceReturnsTheServicesResonance() {
        signedIn(USER);
        Map<String, Object> resonance = Map.of("resonance", List.of(), "scale", Map.of("min", 1, "max", 5));
        when(service.resonance(USER)).thenReturn(resonance);
        assertSame(resonance, data(controller.resonance()));
    }

    @Test
    void postGenerateDrawsThemesForTheSignedInUser() {
        signedIn(USER);
        Map<String, Object> narrative = Map.of("themes", List.of());
        when(service.generateThemes(USER)).thenReturn(narrative);
        assertSame(narrative, data(controller.generateThemes()));
    }

    @Test
    void patchPassesTheBodyAndThePathId() throws Exception {
        signedIn(USER);
        JsonNode body = new ObjectMapper().readTree("{\"status\": \"accepted\"}");
        controller.decide(17L, body);
        verify(service).decideTheme(USER, 17L, body);
    }

    @Test
    void theUserIsAlwaysTheTokensNeverAnotherOne() {
        signedIn(7L);
        controller.resonance();
        verify(service).resonance(7L);
    }

    @Test
    void withoutASignedInUserNothingReachesTheService() {
        for (Runnable call : List.<Runnable>of(
                () -> controller.themes(false),
                controller::resonance,
                controller::generateThemes,
                controller::generateResonance,
                () -> controller.get(false))) {
            DeskException refused = assertThrows(DeskException.class, call::run);
            assertEquals(HttpStatus.UNAUTHORIZED, refused.status());
        }
        verifyNoInteractions(service);
    }

    @Test
    void theServicesOwnRefusalPassesThrough() {
        signedIn(USER);
        when(service.generateThemes(anyLong())).thenThrow(DeskException.badRequest("Have at least one essay draft reviewed first."));
        DeskException refused = assertThrows(DeskException.class, controller::generateThemes);
        assertEquals(HttpStatus.BAD_REQUEST, refused.status());
    }
}
