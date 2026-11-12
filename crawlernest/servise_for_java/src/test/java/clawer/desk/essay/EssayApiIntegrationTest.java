package clawer.desk.essay;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import clawer.desk.model.DeskModelClient;
import clawer.service.AnalyticsService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * POST /api/v1/user/desk/essays/evaluate and the review reads, through the filter
 * chain to PostgreSQL, with the model replaced by a mock.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256",
        // These tests call the (stubbed) model endpoints many times a minute as one user. The model budget is
        // tested on its own in ModelCallBudgetFilterTest and ModelCallBudgetIntegrationTest.
        "crawlernest.rate-limit.model-calls-per-minute=100000",
        "crawlernest.rate-limit.model-calls-per-day=100000"
})
@SqlGroup({
        @Sql(scripts = {"classpath:sql/desk_integration_setup.sql", "classpath:sql/desk_integration_seed.sql"},
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD),
        @Sql(scripts = "classpath:sql/desk_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
})
class EssayApiIntegrationTest {

    private static final long OWNER = 990401L;
    private static final long OTHER_USER = 990402L;
    private static final String DRAFT = "The first time the robot arm failed, I blamed the motor. "
            + "I learned that failure is part of engineering.";

    @Autowired
    private MockMvc mvc;

    @Autowired
    private JwtService jwtService;

    @Autowired
    private JdbcTemplate jdbc;

    @MockBean
    private DeskModelClient model;

    private final ObjectMapper json = new ObjectMapper();

    private static String modelReply(int impact) {
        return """
                {"dimensions": {
                  "impact": {"score": %d, "rationale": "Concrete stakes.", "evidence": ["I blamed the motor."]},
                  "introspection": {"score": 64, "rationale": "States the lesson.", "evidence": []},
                  "passion": {"score": 78, "rationale": "Time spent.", "evidence": []},
                  "originality": {"score": 71, "rationale": "Specific.", "evidence": []}
                },
                "suggestions": [{"original": "I learned that failure is part of engineering.",
                  "suggested": "I stopped hiding the broken prototypes.", "dimension": "introspection", "reason": "Show it."}]}
                """.formatted(impact);
    }

    private ResultActions evaluate(long userId, String body) throws Exception {
        return mvc.perform(post("/api/v1/user/desk/essays/evaluate")
                .cookie(new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, jwtService.issue(userId, userId + "@t.test")))
                .contentType(MediaType.APPLICATION_JSON).content(body));
    }

    private ResultActions send(long userId, org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request)
            throws Exception {
        return mvc.perform(request.cookie(new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME,
                jwtService.issue(userId, userId + "@t.test"))));
    }

    private static String body(String draft) {
        return "{\"essayTitle\": \"Personal statement\", \"draftText\": " + quote(draft) + "}";
    }

    private static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private long reviewCount(long userId) {
        return jdbc.queryForObject("SELECT count(*) FROM desk.essay_review WHERE user_id = ?", Long.class, userId);
    }

    @Test
    void scoresStoresAndDisclosesAReview() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply(modelReply(82), "test-model"));

        evaluate(OWNER, body(DRAFT))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.cached").value(false))
                .andExpect(jsonPath("$.data.rubricVersion").value("essay-rubric-2026.1"))
                .andExpect(jsonPath("$.data.overall.score").value(73.8))
                .andExpect(jsonPath("$.data.overall.method").value("weighted_mean"))
                .andExpect(jsonPath("$.data.dimensions[*].key").value(contains("impact", "introspection", "passion", "originality")))
                .andExpect(jsonPath("$.data.dimensions[0].evidence[0].start").value(DRAFT.indexOf("I blamed the motor.")))
                .andExpect(jsonPath("$.data.suggestions", hasSize(1)))
                .andExpect(jsonPath("$.data.isEstimated").value(true))
                .andExpect(jsonPath("$.data.provenance.model").value("test-model"))
                .andExpect(jsonPath("$.data.caveats").value(contains(
                        AnalyticsService.ESSAY_SCORE_ESTIMATE_CAVEAT, AnalyticsService.ESSAY_OVERALL_METHOD_CAVEAT)));
        assertEquals(1, reviewCount(OWNER));
    }

    @Test
    void anUnchangedDraftIsNotSentToTheModelAgain() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply(modelReply(82), "test-model"));
        evaluate(OWNER, body(DRAFT)).andExpect(jsonPath("$.data.cached").value(false));
        evaluate(OWNER, body(DRAFT)).andExpect(status().isOk()).andExpect(jsonPath("$.data.cached").value(true));
        verify(model, times(1)).complete(anyString(), anyString());
        assertEquals(1, reviewCount(OWNER));
    }

    @Test
    void aRevisionReportsItsScoreChanges() throws Exception {
        when(model.complete(anyString(), anyString()))
                .thenReturn(new DeskModelClient.Reply(modelReply(70), "test-model"))
                .thenReturn(new DeskModelClient.Reply(modelReply(86), "test-model"));
        JsonNode first = json.readTree(evaluate(OWNER, body(DRAFT)).andReturn().getResponse().getContentAsString());
        long firstId = first.path("data").path("id").asLong();

        evaluate(OWNER, "{\"essayTitle\": \"Personal statement\", \"revisionOfId\": " + firstId
                + ", \"draftText\": " + quote(DRAFT + " Now I run a club.") + "}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.comparedToRevision.id").value(firstId))
                .andExpect(jsonPath("$.data.comparedToRevision.dimensionDeltas.impact").value(16))
                .andExpect(jsonPath("$.data.comparedToRevision.overallDelta").value(4.0));
    }

    @Test
    void anotherUsersDraftCannotBeRevisedOrRead() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply(modelReply(82), "test-model"));
        long id = json.readTree(evaluate(OWNER, body(DRAFT)).andReturn().getResponse().getContentAsString())
                .path("data").path("id").asLong();

        evaluate(OTHER_USER, "{\"essayTitle\": \"x\", \"revisionOfId\": " + id + ", \"draftText\": \"Mine.\"}")
                .andExpect(status().isBadRequest());
        send(OTHER_USER, get("/api/v1/user/desk/essays/" + id)).andExpect(status().isNotFound());
        send(OTHER_USER, delete("/api/v1/user/desk/essays/" + id)).andExpect(status().isNotFound());
        send(OTHER_USER, get("/api/v1/user/desk/essays")).andExpect(jsonPath("$.data", hasSize(0)));
        send(OWNER, get("/api/v1/user/desk/essays")).andExpect(jsonPath("$.data", hasSize(1)));
    }

    @Test
    void aCallerCannotSupplyScores() throws Exception {
        evaluate(OWNER, "{\"essayTitle\": \"x\", \"draftText\": \"Mine.\", \"dimensionScores\": {\"impact\": {\"score\": 100}}}")
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Unknown field: dimensionScores."));
        verify(model, never()).complete(anyString(), anyString());
    }

    @Test
    void withNoModelItRefusesAndStoresNothing() throws Exception {
        when(model.complete(anyString(), anyString()))
                .thenThrow(new DeskModelClient.UnavailableException("No model is configured, so this cannot run. Nothing was stored."));
        evaluate(OWNER, body(DRAFT))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.code").value("MODEL_UNAVAILABLE"));
        assertEquals(0, reviewCount(OWNER));
    }

    @Test
    void anUnreadableReplyStoresNothing() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply("Looks great, 9/10!", "test-model"));
        evaluate(OWNER, body(DRAFT))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.code").value("MODEL_REPLY_UNREADABLE"));
        verify(model, times(2)).complete(anyString(), anyString());
        assertEquals(0, reviewCount(OWNER));
    }

    @Test
    void keepsTheWordLimitAndUpdatesItWithoutRescoring() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply(modelReply(82), "test-model"));
        evaluate(OWNER, "{\"essayTitle\": \"x\", \"wordLimit\": 650, \"draftText\": " + quote(DRAFT) + "}")
                .andExpect(jsonPath("$.data.wordLimit").value(650));
        evaluate(OWNER, "{\"essayTitle\": \"x\", \"wordLimit\": 250, \"draftText\": " + quote(DRAFT) + "}")
                .andExpect(jsonPath("$.data.cached").value(true))
                .andExpect(jsonPath("$.data.wordLimit").value(250));
        verify(model, times(1)).complete(anyString(), anyString());
        evaluate(OWNER, "{\"essayTitle\": \"x\", \"wordLimit\": 0, \"draftText\": \"Other.\"}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void refusesBadDrafts() throws Exception {
        evaluate(OWNER, "{\"essayTitle\": \"x\", \"draftText\": \"   \"}").andExpect(status().isBadRequest());
        evaluate(OWNER, "{\"draftText\": \"Mine.\"}").andExpect(status().isBadRequest());
        evaluate(OWNER, body("x".repeat(20001))).andExpect(status().isBadRequest());
        verify(model, never()).complete(anyString(), anyString());
    }

    @Test
    void needsAToken() throws Exception {
        mvc.perform(post("/api/v1/user/desk/essays/evaluate").contentType(MediaType.APPLICATION_JSON).content(body(DRAFT)))
                .andExpect(status().isUnauthorized());
        verify(model, never()).complete(anyString(), anyString());
    }
}
