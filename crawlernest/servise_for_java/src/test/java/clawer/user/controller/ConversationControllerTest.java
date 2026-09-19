package clawer.user.controller;

import clawer.auth.jwt.AuthenticatedUser;
import clawer.user.dto.SaveConversationRequest;
import clawer.user.dto.SavedConversationDetail;
import clawer.user.service.ConversationService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Auth and input validation for the conversation write path.
 *
 * <p>The recurring assertion is that nothing reaches the service before the
 * request's token has produced a user id: a write path that validates the body
 * first and checks identity later would happily store an anonymous caller's
 * transcript. The filter chain refuses these paths outright, but the controller
 * keeps its own check, so a routing change cannot quietly open one.
 */
class ConversationControllerTest {

    @Mock
    private ConversationService conversationService;

    @InjectMocks
    private ConversationController controller;

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

    private JsonNode turns(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private SaveConversationRequest validRequest() {
        SaveConversationRequest request = new SaveConversationRequest();
        request.setSessionId("session-abc");
        request.setTitle("How do rankings work");
        request.setTurnsJson(turns("""
                [
                  {"role": "user", "content": "How is the aggregated rank computed?"},
                  {"role": "assistant", "content": "It combines the available sources."}
                ]
                """));
        return request;
    }

    // ─── Authentication ───────────────────────────────────────────────────────

    @Test
    void save_withNoToken_returns401AndNeverReachesTheService() {
        ResponseEntity<?> response = controller.save(validRequest());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withAnAuthenticationThatIsNotOneOfOurs_returns401() {
        // A principal that is not an AuthenticatedUser is not an identity: it must
        // not be read as user 0, or as whatever the principal's toString says.
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken("someone", null, List.of()));

        ResponseEntity<?> response = controller.save(validRequest());

        assertEquals(HttpStatus.UNAUTHORIZED, response.getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void list_withNoToken_returns401() {
        assertEquals(HttpStatus.UNAUTHORIZED, controller.list().getStatusCode());
        verify(conversationService, never()).findSummariesByUserId(anyLong());
    }

    @Test
    void get_withNoToken_returns401() {
        assertEquals(HttpStatus.UNAUTHORIZED, controller.get(1L).getStatusCode());
        verify(conversationService, never()).findDetailByIdAndUserId(anyLong(), anyLong());
    }

    @Test
    void delete_withNoToken_returns401() {
        assertEquals(HttpStatus.UNAUTHORIZED, controller.delete(1L).getStatusCode());
        verify(conversationService, never()).deleteByIdAndUserId(anyLong(), anyLong());
    }

    // ─── Ownership ────────────────────────────────────────────────────────────

    @Test
    void get_passesTheTokenUserIdToTheQuery() {
        signedIn(7L);
        when(conversationService.findDetailByIdAndUserId(42L, 7L))
                .thenReturn(Optional.of(new SavedConversationDetail()));

        assertEquals(HttpStatus.OK, controller.get(42L).getStatusCode());
        // The id filter is (row id, token user id); a row belonging to someone
        // else cannot match, which is what makes the 404 below a real boundary.
        verify(conversationService).findDetailByIdAndUserId(42L, 7L);
    }

    @Test
    void get_anotherUsersRowLooksMissingRatherThanForbidden() {
        signedIn(7L);
        when(conversationService.findDetailByIdAndUserId(42L, 7L)).thenReturn(Optional.empty());

        assertEquals(HttpStatus.NOT_FOUND, controller.get(42L).getStatusCode());
    }

    @Test
    void delete_anotherUsersRowReturns404AndDeletesNothing() {
        signedIn(7L);
        when(conversationService.deleteByIdAndUserId(42L, 7L)).thenReturn(false);

        assertEquals(HttpStatus.NOT_FOUND, controller.delete(42L).getStatusCode());
    }

    // ─── Validation ───────────────────────────────────────────────────────────

    @Test
    void save_withValidRequest_returns201() {
        signedIn(1L);
        when(conversationService.save(eq(1L), eq("session-abc"), anyString(), any())).thenReturn(99L);

        ResponseEntity<?> response = controller.save(validRequest());

        assertEquals(HttpStatus.CREATED, response.getStatusCode());
        verify(conversationService).save(eq(1L), eq("session-abc"), eq("How do rankings work"), any());
    }

    @Test
    void save_withBlankSessionId_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setSessionId("   ");

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withOverlongSessionId_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setSessionId("s".repeat(ConversationService.MAX_SESSION_ID_LENGTH + 1));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withOverlongTitle_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTitle("t".repeat(ConversationService.MAX_TITLE_LENGTH + 1));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withBlankTitle_isAcceptedSoTheServiceCanDeriveOne() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTitle("");
        when(conversationService.save(anyLong(), anyString(), any(), any())).thenReturn(5L);

        assertEquals(HttpStatus.CREATED, controller.save(request).getStatusCode());
    }

    @Test
    void save_withMissingTurns_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(null);

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withEmptyTurns_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(turns("[]"));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withTurnsThatAreNotAnArray_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(turns("{\"role\": \"user\", \"content\": \"hi\"}"));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withATurnMissingItsRole_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(turns("[{\"content\": \"no role here\"}]"));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withNonStringContent_returns400() {
        signedIn(1L);
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(turns("[{\"role\": \"user\", \"content\": 42}]"));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_withTooManyTurns_returns400() {
        signedIn(1L);
        StringBuilder json = new StringBuilder("[");
        for (int i = 0; i <= ConversationService.MAX_TURNS; i++) {
            json.append(i > 0 ? "," : "").append("{\"role\":\"user\",\"content\":\"x\"}");
        }
        json.append("]");
        SaveConversationRequest request = validRequest();
        request.setTurnsJson(turns(json.toString()));

        assertEquals(HttpStatus.BAD_REQUEST, controller.save(request).getStatusCode());
        verify(conversationService, never()).save(anyLong(), anyString(), any(), any());
    }

    @Test
    void save_whenTheServiceRejectsTheSize_returns400RatherThan500() {
        signedIn(1L);
        when(conversationService.save(anyLong(), anyString(), any(), any()))
                .thenThrow(new IllegalArgumentException("Conversation is too large."));

        assertEquals(HttpStatus.BAD_REQUEST,
                controller.save(validRequest()).getStatusCode());
    }
}
